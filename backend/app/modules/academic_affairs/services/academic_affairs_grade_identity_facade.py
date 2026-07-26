"""V2-04 成绩正式身份最终层。

在现有名单、归档、审核状态机之上叠加：
- 成绩任务绑定具体 AaCourse 版本；
- 发布时冻结 course_id/course_code/course_version；
- 正常教学任务每次发布生成新的修读次数；
- 冻结教学班与名单版本回链；
- 新正式成绩按 grade_record_id 唯一，禁止重复投影。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found

from . import academic_affairs_grade_term_facade as _base
from .academic_affairs_grade_identity_service import (
    course_snapshot,
    grade_identity_debt,
    next_study_attempt_no,
    resolve_grade_task_course,
    roster_snapshot,
)

_legacy = _base._legacy
_original_create_grade_task = _base.create_grade_task
_original_task_row = _legacy._task_row


def __getattr__(name):
    return getattr(_base, name)


def _validate_requested_course(user, body) -> None:
    """创建前校验稳定课程身份，避免先落一条无courseId任务再补失败。"""
    from app.models import AaCourse, AaTeachingTask

    teaching_task_id = getattr(body, "teachingTaskId", None)
    requested_course_id = getattr(body, "courseId", None)
    with _legacy.session() as db:
        if teaching_task_id:
            task = db.query(AaTeachingTask).filter(
                AaTeachingTask.id == int(teaching_task_id),
                AaTeachingTask.tenant_id == _legacy._tid(),
                AaTeachingTask.is_deleted.is_(False),
            ).first()
            if not task:
                raise not_found("教学任务不存在或不在当前租户范围")
            requested_course_id = task.course_id
        if requested_course_id in (None, ""):
            raise AppException(
                "VALIDATION_ERROR",
                "成绩任务必须绑定课程库具体版本；管理员补录也必须选择courseId",
            )
        course = db.query(AaCourse).filter(
            AaCourse.id == int(requested_course_id),
            AaCourse.tenant_id == _legacy._tid(),
            AaCourse.is_deleted.is_(False),
        ).first()
        if not course:
            raise not_found("选择的课程版本不存在")


def create_grade_task(body, user) -> dict:
    _validate_requested_course(user, body)
    result = _original_create_grade_task(body, user)

    from app.models import AaGradeTask

    with _legacy.session() as db:
        task = db.query(AaGradeTask).filter(
            AaGradeTask.id == int(result["gradeTaskId"]),
            AaGradeTask.tenant_id == _legacy._tid(),
            AaGradeTask.is_deleted.is_(False),
        ).with_for_update().first()
        if not task:
            raise not_found("成绩任务创建后未找到")
        if not task.course_id and getattr(body, "courseId", None):
            task.course_id = int(body.courseId)
        course = resolve_grade_task_course(db, task)
        snap = course_snapshot(course)
        _legacy._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "COURSE_IDENTITY_BIND",
            f"courseId={snap['courseId']};code={snap['courseCode']};version={snap['courseVersion']}",
        )
        db.commit()
        result.update(snap)
        return result


def _task_row(task) -> dict:
    result = _original_task_row(task)
    result["courseId"] = str(task.course_id or "")
    return result


def _require_publish_roster(db, task, records) -> tuple[dict, dict]:
    roster_data = _base._require_ready_roster(db, task)
    roster_ids = {int(value) for value in roster_data.get("studentIds") or []}
    record_ids = {int(record.student_id) for record in records}
    missing = sorted(roster_ids - record_ids)
    extra = sorted(record_ids - roster_ids)
    if missing or extra:
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            f"发布前正式名单已变化：缺少 {len(missing)} 人、名单外 {len(extra)} 人，请退回重新核对",
            details={
                "rosterSource": roster_data.get("source"),
                "missingStudentIds": [str(value) for value in missing],
                "extraStudentIds": [str(value) for value in extra],
            },
            http_status=409,
        )
    meta = roster_snapshot(roster_data)
    if task.teaching_task_id and (not meta["teachingClassId"] or not meta["rosterVersionId"]):
        raise AppException(
            "DATA_CONFLICT",
            "教学任务尚未投影独立教学班和正式名单版本，禁止发布成绩；请先完成V2教学班回填",
            details={"rosterSource": meta["rosterSource"]},
            http_status=409,
        )
    return roster_data, meta


def publish_grades(task_id, user) -> dict:
    """教务终审发布：课程版本、修读次数、教学班和名单版本与成绩同事务冻结。"""
    _legacy._require_review_role(user)
    with _legacy.session() as db:
        from app.models import (
            AaGradeRecord,
            AaGradeTask,
            AcademicGrade,
            AffairsRiskRecord,
            StudentProfile,
        )
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

        task = db.query(AaGradeTask).filter(
            AaGradeTask.id == int(task_id),
            AaGradeTask.tenant_id == _legacy._tid(),
            AaGradeTask.is_deleted.is_(False),
        ).with_for_update().first()
        if not task:
            raise not_found("成绩录入任务不存在")
        guard_term_writable(db, task.term_id)
        if task.status == "PUBLISHED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "成绩已发布")
        if task.status != "ACADEMIC_REVIEW":
            raise AppException("DATA_CONFLICT", "仅学院审核通过（教务终审中）的任务可发布")

        records = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _legacy._tid(),
            AaGradeRecord.task_id == task.id,
            AaGradeRecord.is_deleted.is_(False),
        ).order_by(AaGradeRecord.id)).all()
        incomplete = [
            record for record in records
            if record.total_score is None and (record.exception_flag or "NORMAL") == "NORMAL"
        ]
        if not records or incomplete:
            raise AppException("DATA_CONFLICT", f"仍有 {len(incomplete)} 名学生成绩未录全，不可发布")

        _roster_data, roster_meta = _require_publish_roster(db, task, records)
        course = resolve_grade_task_course(db, task)
        course_meta = course_snapshot(course)

        duplicate_source = db.scalars(select(AcademicGrade.grade_record_id).where(
            AcademicGrade.tenant_id == _legacy._tid(),
            AcademicGrade.grade_record_id.in_([int(record.id) for record in records]),
            AcademicGrade.is_deleted.is_(False),
        )).first()
        if duplicate_source is not None:
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "成绩明细已存在正式投影，禁止重复发布；请检查历史任务状态",
                http_status=409,
            )

        claimed = db.query(AaGradeTask).filter(
            AaGradeTask.id == task.id,
            AaGradeTask.tenant_id == _legacy._tid(),
            AaGradeTask.status == "ACADEMIC_REVIEW",
        ).update({AaGradeTask.status: "PUBLISHED"}, synchronize_session=False)
        if not claimed:
            db.rollback()
            raise AppException("APPROVAL_VERSION_CONFLICT", "成绩已发布或任务状态已变化")
        task.status = "PUBLISHED"

        projected = 0
        fail_count = 0
        attempts: dict[int, int] = {}
        for record in records:
            profile = db.get(StudentProfile, int(record.student_id))
            academic_student = _legacy._acad_student_id(
                db,
                record.student_id,
                profile.real_name if profile else "",
            )
            attempt_no = next_study_attempt_no(
                db,
                academic_student.id,
                course_meta["courseCode"],
            )
            attempts[int(academic_student.id)] = attempt_no
            grade = AcademicGrade(
                tenant_id=_legacy._tid(),
                acad_student_id=academic_student.id,
                course_id=course_meta["courseId"],
                course_code=course_meta["courseCode"],
                course_version=course_meta["courseVersion"],
                attempt_no=attempt_no,
                grade_task_id=task.id,
                grade_record_id=record.id,
                teaching_task_id=task.teaching_task_id,
                teaching_class_id=roster_meta["teachingClassId"],
                roster_version_id=roster_meta["rosterVersionId"],
                course_name=course_meta["courseName"],
                term=task.term_code,
                nature=course_meta["nature"],
                credit_value=course_meta["credit"],
                score=record.total_score,
                pass_status=record.pass_status or "PENDING",
                exam_type="FINAL",
                record_status="ACTIVE",
                source="PUBLISH",
            )
            db.add(grade)
            db.flush()
            record.acad_grade_id = grade.id
            record.source = "PUBLISH"
            projected += 1
            _legacy._refresh_aggregates(db, academic_student)
            if record.pass_status == "FAILED":
                fail_count += 1
                duplicate_risk = db.scalars(select(AffairsRiskRecord).where(
                    AffairsRiskRecord.tenant_id == _legacy._tid(),
                    AffairsRiskRecord.source == "ACADEMIC_WARNING",
                    AffairsRiskRecord.source_ref_id == record.id,
                )).first()
                if not duplicate_risk:
                    db.add(AffairsRiskRecord(
                        tenant_id=_legacy._tid(),
                        student_id=record.student_id,
                        source="ACADEMIC_WARNING",
                        source_ref_id=record.id,
                        risk_level="MEDIUM",
                        title=f"{course_meta['courseName']} 课程不及格",
                        detail=f"总评 {record.total_score}，及格线 {task.pass_line}",
                        status="NEW",
                    ))

        task.publish_at = datetime.utcnow()
        task.academic_reviewed_at = datetime.utcnow()
        _name, _role, user_id = _legacy._op()
        task.academic_reviewer_id = int(user_id) if user_id.isdigit() else None
        _legacy._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "PUBLISH",
            (
                f"projected={projected};fail={fail_count};courseId={course_meta['courseId']};"
                f"courseVersion={course_meta['courseVersion']};teachingClassId={roster_meta['teachingClassId']};"
                f"rosterVersionId={roster_meta['rosterVersionId']}"
            ),
        )
        db.commit()

    warning_scan_ok = True
    warning_scan_error = None
    try:
        from app.modules.academic_affairs.services.academic_affairs_warning_service import scan_warnings
        scan_warnings(user)
    except Exception as exc:  # 发布主事务成功，预警失败显式返回
        import logging
        warning_scan_ok = False
        warning_scan_error = str(exc)[:200]
        logging.getLogger(__name__).exception("grade publish → scan_warnings failed")

    return {
        "gradeTaskId": str(task_id),
        "status": "PUBLISHED",
        "projected": projected,
        "failCount": fail_count,
        "courseId": str(course_meta["courseId"]),
        "courseCode": course_meta["courseCode"],
        "courseVersion": course_meta["courseVersion"],
        "teachingClassId": str(roster_meta["teachingClassId"] or ""),
        "rosterVersionId": str(roster_meta["rosterVersionId"] or ""),
        "warningScanOk": warning_scan_ok,
        "warningScanError": warning_scan_error,
    }


def identity_debt(user, term=None) -> dict:
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role not in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"} and (user or {}).get("userType") != "PLATFORM_SUPER_ADMIN":
        raise AppException("NO_PERMISSION", "仅教务处可查看正式成绩身份欠账", http_status=403)
    with _legacy.session() as db:
        return grade_identity_debt(db, term=term)


# 所有旧导入路径与内部globals统一命中新发布策略。
_legacy._task_row = _task_row
_legacy.create_grade_task = create_grade_task
_legacy.publish_grades = publish_grades
_base.create_grade_task = create_grade_task
_base.publish_grades = publish_grades
