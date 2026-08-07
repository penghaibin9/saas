"""包 4：毕业资格跨域正式事实安全门。

毕业资格不能把“某域存在一条未删除记录”解释为已经完成。实习、毕设必须同时命中
正式完成状态、已发布且通过的成绩，以及有效归档证据；就业当前不是毕业硬门槛，
只能返回可核验提示，禁止伪造 PASS。
"""
from __future__ import annotations

from sqlalchemy import select

from app.services.db_service import _tid

from . import academic_affairs_graduation_service as graduation_service


_ORIGINAL_DOMAIN_CHECK = getattr(
    graduation_service,
    "_package4_original_domain_check",
    graduation_service._check_domain_exists,
)

_FAIL_GRADE_LEVELS = {"不及格", "FAILED", "FAIL", "UNQUALIFIED"}


def _domain_result(item: str, result: str, owner: str, evidence: str, *, ref_id=None, **extra) -> dict:
    payload = {
        "item": item,
        "result": result,
        "owner": owner,
        "evidence": evidence,
        "refId": str(ref_id) if ref_id is not None else None,
    }
    payload.update(extra)
    return payload


def _is_valid_internship_archive(row) -> bool:
    if str(getattr(row, "status", "") or "").upper() != "ARCHIVED":
        return False
    if int(getattr(row, "completeness", 0) or 0) >= 100:
        return True
    evidence_ids = getattr(row, "force_evidence_file_ids", None) or []
    return bool(
        str(getattr(row, "force_reason", "") or "").strip()
        and evidence_ids
        and str(getattr(row, "force_approved_by", "") or "").strip()
        and str(getattr(row, "force_approved_role", "") or "").strip()
    )


def _is_passing_internship_score(row) -> bool:
    return bool(
        str(getattr(row, "status", "") or "").upper() in {"PUBLISHED", "ARCHIVED"}
        and getattr(row, "is_pass", False) is True
        and getattr(row, "incomplete", True) is False
    )


def _is_passing_graduation_grade(row) -> bool:
    if str(getattr(row, "status", "") or "").upper() != "PUBLISHED":
        return False
    level = str(getattr(row, "grade_level", "") or "").strip().upper()
    if level in _FAIL_GRADE_LEVELS:
        return False
    total = getattr(row, "total_score", None)
    try:
        return total is not None and float(total) >= 60.0
    except (TypeError, ValueError):
        return False


def _is_valid_graduation_archive(row) -> bool:
    return bool(
        str(getattr(row, "status", "") or "").upper() == "FILED"
        and str(getattr(row, "manifest_hash", "") or "").strip()
    )


def strict_domain_check(db, item, model, student_field, s, owner, done_check=None):
    """兼容旧调用，但禁止在没有权威完成规则时按“存在记录”判定 PASS。"""
    if done_check is not None:
        return _ORIGINAL_DOMAIN_CHECK(db, item, model, student_field, s, owner, done_check)
    try:
        rows = db.scalars(select(model).where(
            model.tenant_id == _tid(),
            getattr(model, student_field) == s.id,
            model.is_deleted.is_(False),
        )).all()
    except Exception as exc:  # noqa: BLE001
        return _domain_result(
            item,
            "UNKNOWN",
            owner,
            f"供数查询失败：{type(exc).__name__}",
        )
    if not rows:
        return _domain_result(item, "UNKNOWN", owner, "无该域记录")
    return _domain_result(
        item,
        "UNKNOWN",
        owner,
        f"发现 {len(rows)} 条记录，但未配置权威完成规则，禁止仅按记录存在判定通过",
        ref_id=rows[0].id,
    )


def _check_internship_completion(db, s) -> dict:
    from app.models import InternshipArchive, InternshipFinalScore, InternshipRecord

    rows = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.student_id == s.id,
        InternshipRecord.is_deleted.is_(False),
    ).order_by(InternshipRecord.id.desc())).all()
    if not rows:
        return _domain_result("INTERNSHIP", "UNKNOWN", "GD_MENTOR", "无岗位实习记录")

    checked = []
    for record in rows:
        record_status = str(record.status or "").upper()
        checked.append(f"{record.id}:{record_status}")
        if record_status != "ARCHIVED":
            continue

        score = db.scalars(select(InternshipFinalScore).where(
            InternshipFinalScore.tenant_id == _tid(),
            InternshipFinalScore.internship_id == record.id,
            InternshipFinalScore.student_id == s.id,
            InternshipFinalScore.is_deleted.is_(False),
        ).order_by(InternshipFinalScore.id.desc())).first()
        archives = db.scalars(select(InternshipArchive).where(
            InternshipArchive.tenant_id == _tid(),
            InternshipArchive.internship_id == record.id,
            InternshipArchive.student_id == s.id,
            InternshipArchive.is_deleted.is_(False),
        ).order_by(InternshipArchive.id.desc())).all()
        archive = next((row for row in archives if _is_valid_internship_archive(row)), None)

        if score and _is_passing_internship_score(score) and archive:
            return _domain_result(
                "INTERNSHIP",
                "PASS",
                "GD_MENTOR",
                "实习主档已归档，最终成绩已发布且通过，合规归档证据有效",
                ref_id=record.id,
                sourceObjectIds={
                    "internshipRecordId": str(record.id),
                    "finalScoreId": str(score.id),
                    "archiveId": str(archive.id),
                },
                sourceStatuses={
                    "record": record_status,
                    "score": str(score.status or "").upper(),
                    "archive": str(archive.status or "").upper(),
                },
            )

    return _domain_result(
        "INTERNSHIP",
        "FAIL",
        "GD_MENTOR",
        "存在实习记录，但未同时满足主档归档、已发布通过成绩和有效合规归档",
        ref_id=rows[0].id,
        sourceStatuses=checked,
    )


def _check_graduation_design_completion(db, s) -> dict:
    from app.models import GraduationArchiveRecord, GraduationGrade, GraduationStudent

    rows = db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.student_id == s.id,
        GraduationStudent.is_deleted.is_(False),
    ).order_by(GraduationStudent.id.desc())).all()
    if not rows:
        return _domain_result("GRADUATION_DESIGN", "UNKNOWN", "GD_MENTOR", "无毕业设计学生记录")

    checked = []
    for student in rows:
        stage = str(student.stage or "").upper()
        record_status = str(student.record_status or "").upper()
        checked.append(f"{student.id}:{stage}/{record_status}")
        if stage != "ARCHIVED" or record_status != "ACTIVE":
            continue

        grade = db.scalars(select(GraduationGrade).where(
            GraduationGrade.tenant_id == _tid(),
            GraduationGrade.gd_student_id == student.id,
            GraduationGrade.is_deleted.is_(False),
        ).order_by(GraduationGrade.id.desc())).first()
        archives = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == _tid(),
            GraduationArchiveRecord.gd_student_id == student.id,
            GraduationArchiveRecord.is_deleted.is_(False),
        ).order_by(GraduationArchiveRecord.id.desc())).all()
        archive = next((row for row in archives if _is_valid_graduation_archive(row)), None)

        if grade and _is_passing_graduation_grade(grade) and archive:
            return _domain_result(
                "GRADUATION_DESIGN",
                "PASS",
                "GD_MENTOR",
                "毕设学生已归档，正式成绩已发布且通过，FILED 归档清单有效",
                ref_id=student.id,
                sourceObjectIds={
                    "graduationStudentId": str(student.id),
                    "gradeId": str(grade.id),
                    "archiveId": str(archive.id),
                },
                sourceStatuses={
                    "stage": stage,
                    "grade": str(grade.status or "").upper(),
                    "archive": str(archive.status or "").upper(),
                },
                sourceManifestHash=archive.manifest_hash,
                sourceGradeHash=getattr(grade, "source_snapshot_hash", None),
            )

    return _domain_result(
        "GRADUATION_DESIGN",
        "FAIL",
        "GD_MENTOR",
        "存在毕设记录，但未同时满足学生归档、PUBLISHED 及格成绩和有效 FILED 归档",
        ref_id=rows[0].id,
        sourceStatuses=checked,
    )


def _check_employment_evidence(db, s) -> dict:
    """就业暂为非阻断提醒；不把学生台账存在误报为完成。"""
    from app.models import EmpStudent

    rows = db.scalars(select(EmpStudent).where(
        EmpStudent.tenant_id == _tid(),
        EmpStudent.student_id == s.id,
        EmpStudent.is_deleted.is_(False),
        EmpStudent.record_status == "ACTIVE",
    ).order_by(EmpStudent.id.desc())).all()
    if not rows:
        return _domain_result(
            "EMPLOYMENT",
            "UNKNOWN",
            "AA_STAFF",
            "无就业服务台账；当前学校规则未将就业设为毕业硬门槛，本项不阻断",
        )
    row = rows[0]
    return _domain_result(
        "EMPLOYMENT",
        "UNKNOWN",
        "AA_STAFF",
        "就业仅作非阻断提醒，需学校政策或人工复核；禁止仅因存在记录判定通过",
        ref_id=row.id,
        sourceStatuses={
            "destinationType": row.destination_type,
            "verifyStatus": row.verify_status,
            "materialStatus": row.material_status,
        },
    )


def strict_run_items(db, s) -> list:
    """用各域权威事实替换三个“有记录即通过”的跨域检查。"""
    return [
        graduation_service._check_status(db, s),
        graduation_service._check_credit(db, s),
        graduation_service._check_course_required(db, s),
        graduation_service._check_course_elective(db, s),
        graduation_service._check_practice(db, s),
        _check_internship_completion(db, s),
        _check_graduation_design_completion(db, s),
        graduation_service._check_discipline(db, s),
        _check_employment_evidence(db, s),
        graduation_service._check_archive(db, s),
        graduation_service._check_fee(db, s),
    ]


strict_run_items._graduation_truth_guard = True
strict_domain_check._graduation_truth_guard = True


def install() -> None:
    """幂等安装到毕业资格公开服务。"""
    if not hasattr(graduation_service, "_package4_original_domain_check"):
        graduation_service._package4_original_domain_check = graduation_service._check_domain_exists
    if not getattr(graduation_service._check_domain_exists, "_graduation_truth_guard", False):
        graduation_service._check_domain_exists = strict_domain_check
    if not getattr(graduation_service._run_items, "_graduation_truth_guard", False):
        graduation_service._run_items = strict_run_items
