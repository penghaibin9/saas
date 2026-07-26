"""V2-04 补考/清考正式成绩身份最终层。

补考和清考属于同一次修读的后续考试尝试，不增加 attempt_no。新成绩必须从唯一原失败成绩继承
course_id/course_code/course_version/attempt_no 以及教学班、名单版本回链；历史身份欠账或同名课程歧义
一律 fail-closed。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException

from . import academic_affairs_makeup_identity_facade as _base
from . import academic_affairs_makeup_term_facade as _term
from . import academic_affairs_grade_identity_facade as _grade
from .academic_affairs_grade_identity_service import source_attempt_no

_legacy = _base._legacy


def __getattr__(name):
    return getattr(_base, name)


def _origin_failed_grade(db, makeup_row):
    from app.models import AcademicGrade

    candidates = db.scalars(select(AcademicGrade).where(
        AcademicGrade.tenant_id == _legacy._tid(),
        AcademicGrade.acad_student_id == int(makeup_row.acad_student_id),
        AcademicGrade.course_name == makeup_row.course_name,
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    )).all()
    effective = [
        row for row in _grade.effective_grade_rows(candidates)
        if str(row.pass_status or "").upper() in {"FAIL", "FAILED"}
    ]
    if len(effective) != 1:
        raise AppException(
            "DATA_CONFLICT",
            (
                "无法唯一定位补考对应的原失败成绩："
                f"课程名={makeup_row.course_name}，有效失败记录={len(effective)}。"
                "请先完成课程身份治理或从原成绩ID重新纳入补考。"
            ),
            details={"candidateGradeIds": [str(row.id) for row in effective]},
            http_status=409,
        )
    origin = effective[0]
    if not origin.course_id or not origin.course_code or not origin.course_version:
        raise AppException(
            "DATA_CONFLICT",
            "原失败成绩缺少courseId/课程版本，禁止生成补考或清考正式成绩",
            details={"originGradeId": str(origin.id)},
            http_status=409,
        )
    source_attempt_no(origin)
    return origin


def finish_makeup_batch(user, batch_id):
    """REVIEWED→FINISHED：按原成绩稳定身份幂等写补考/清考成绩。"""
    from app.models import AcademicGrade, AcademicMakeup, AcademicStudent

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _legacy._get_mb(db, int(batch_id))
        _term._guard_batch(db, batch)
        if batch.status == _legacy._MB_FINISHED:
            return _legacy._mb_dto(batch)
        if batch.status != _legacy._MB_REVIEWED:
            raise _legacy._invalid("仅学院审核通过(REVIEWED)的批次可教务发布回写")

        records = db.query(AcademicMakeup).filter(
            AcademicMakeup.batch_id == batch.id,
            AcademicMakeup.tenant_id == _legacy._tid(),
            AcademicMakeup.status == "SCORED",
        ).order_by(AcademicMakeup.id).all()
        cap = 60 if batch.score_rule == "CAP60" else 100
        source = "CLEARANCE" if (getattr(batch, "kind", None) == "CLEARANCE") else "MAKEUP"
        affected = set()
        projected = 0

        for makeup in records:
            origin = _origin_failed_grade(db, makeup)
            final_score = makeup.final_score or 0
            passed = final_score >= 60
            recorded_score = min(final_score, cap) if passed else final_score
            attempt_no = source_attempt_no(origin)

            grade = db.query(AcademicGrade).filter(
                AcademicGrade.tenant_id == _legacy._tid(),
                AcademicGrade.acad_student_id == makeup.acad_student_id,
                AcademicGrade.course_id == origin.course_id,
                AcademicGrade.attempt_no == attempt_no,
                AcademicGrade.source == source,
                AcademicGrade.is_deleted.is_(False),
            ).with_for_update().first()
            if not grade:
                grade = AcademicGrade(
                    tenant_id=_legacy._tid(),
                    acad_student_id=makeup.acad_student_id,
                    course_id=origin.course_id,
                    course_code=origin.course_code,
                    course_version=origin.course_version,
                    attempt_no=attempt_no,
                    grade_task_id=origin.grade_task_id,
                    grade_record_id=None,
                    teaching_task_id=origin.teaching_task_id,
                    teaching_class_id=origin.teaching_class_id,
                    roster_version_id=origin.roster_version_id,
                    course_name=origin.course_name,
                    term=batch.term_code,
                    nature=origin.nature,
                    credit_value=origin.credit_value,
                    score=recorded_score,
                    pass_status="PASSED" if passed else "FAILED",
                    exam_type=source,
                    source=source,
                    record_status="ACTIVE",
                )
                db.add(grade)
            else:
                # 同一批次网络重试幂等更新，不创建第二条同来源成绩。
                grade.course_code = origin.course_code
                grade.course_version = origin.course_version
                grade.course_name = origin.course_name
                grade.term = batch.term_code
                grade.nature = origin.nature
                grade.credit_value = origin.credit_value
                grade.score = recorded_score
                grade.pass_status = "PASSED" if passed else "FAILED"
                grade.exam_type = source
                grade.record_status = "ACTIVE"
            projected += 1
            affected.add(int(makeup.acad_student_id))
            _legacy._audit(
                db,
                "AA_MAKEUP",
                makeup.id,
                "MAKEUP_GRADE_IDENTITY",
                (
                    f"originGradeId={origin.id};courseId={origin.course_id};"
                    f"courseVersion={origin.course_version};attemptNo={attempt_no};source={source}"
                ),
            )

        db.flush()
        for academic_student_id in affected:
            academic_student = db.get(AcademicStudent, academic_student_id)
            if academic_student and not academic_student.is_deleted:
                _grade._legacy._refresh_aggregates(db, academic_student)

        batch.status = _legacy._MB_FINISHED
        _legacy._audit(
            db,
            "AA_MAKEUP",
            batch.id,
            "MAKEUP_BATCH_FINISH",
            f"identityProjected={projected};source={source};students={len(affected)}",
        )
        db.commit()
        return {
            **_legacy._mb_dto(batch),
            "identityProjected": projected,
            "source": source,
        }


# 公开链与历史完整路径统一替换。
_base.finish_makeup_batch = finish_makeup_batch
_term.finish_makeup_batch = finish_makeup_batch
_legacy.finish_makeup_batch = finish_makeup_batch
