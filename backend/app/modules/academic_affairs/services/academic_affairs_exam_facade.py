"""考务服务兼容入口。

不重写排考、发布、座位、监考和缓考状态机，只补三项生产门禁：
- 考试结束前必须完成考试课程确认、考生到考状态登记和缓考审批收口；
- 违纪/其他异常必须移交处分线索，误登记必须显式作废；缺考须已发送风险联动；
- 考务归档再次执行同一检查，禁止绕过结束门禁写入 ARCHIVED。
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException, not_found

from . import academic_affairs_exam_service as _legacy


def __getattr__(name):
    return getattr(_legacy, name)


def _status(value) -> str:
    return str(value or "").strip().upper()


def _batch_closure_issues(db, batch_id: int) -> dict:
    from app.models import (
        AaDeferredExam,
        AaExamCourse,
        AaExamIncident,
        AaExamRoomStudent,
    )

    courses = db.query(AaExamCourse).filter(
        AaExamCourse.tenant_id == _legacy._tid(),
        AaExamCourse.batch_id == int(batch_id),
        AaExamCourse.status != "REMOVED",
        AaExamCourse.is_deleted.is_(False),
    ).all()
    course_ids = [int(course.id) for course in courses]
    pending_courses = sum(1 for course in courses if _status(course.status) == "PENDING_CONFIRM")
    if not course_ids:
        return {
            "activeCourseCount": 0,
            "pendingCourses": pending_courses,
            "notStartedSeats": 0,
            "activeDefers": 0,
            "unresolvedIncidents": 0,
        }

    not_started = db.query(AaExamRoomStudent).filter(
        AaExamRoomStudent.tenant_id == _legacy._tid(),
        AaExamRoomStudent.exam_course_id.in_(course_ids),
        AaExamRoomStudent.attendance_status == "NOT_STARTED",
        AaExamRoomStudent.is_deleted.is_(False),
    ).count()
    active_defers = db.query(AaDeferredExam).filter(
        AaDeferredExam.tenant_id == _legacy._tid(),
        AaDeferredExam.exam_course_id.in_(course_ids),
        AaDeferredExam.status.notin_(["APPROVED", "REJECTED"]),
        AaDeferredExam.is_deleted.is_(False),
    ).count()
    incidents = db.query(AaExamIncident).filter(
        AaExamIncident.tenant_id == _legacy._tid(),
        AaExamIncident.exam_course_id.in_(course_ids),
        AaExamIncident.status == "ACTIVE",
        AaExamIncident.is_deleted.is_(False),
    ).all()
    unresolved = 0
    for incident in incidents:
        incident_type = _status(incident.incident_type)
        if incident_type == "ABSENT" and bool(incident.risk_alert_sent):
            continue
        if str(incident.discipline_case_ref or "").strip():
            continue
        unresolved += 1
    return {
        "activeCourseCount": len(courses),
        "pendingCourses": pending_courses,
        "notStartedSeats": int(not_started or 0),
        "activeDefers": int(active_defers or 0),
        "unresolvedIncidents": unresolved,
    }


def _closure_error(issues: dict) -> AppException | None:
    blockers = []
    if int(issues.get("activeCourseCount") or 0) <= 0:
        blockers.append("没有有效考试课程")
    if issues.get("pendingCourses"):
        blockers.append(f"待确认考试课程 {issues['pendingCourses']} 门")
    if issues.get("notStartedSeats"):
        blockers.append(f"未登记到考状态考生 {issues['notStartedSeats']} 人")
    if issues.get("activeDefers"):
        blockers.append(f"在途缓考申请 {issues['activeDefers']} 条")
    if issues.get("unresolvedIncidents"):
        blockers.append(f"未闭环考场异常 {issues['unresolvedIncidents']} 条")
    if not blockers:
        return None
    return AppException(
        "DATA_CONFLICT",
        "考务尚未收口：" + "；".join(blockers),
        details=issues,
        http_status=409,
    )


def finish_batch(user, bid):
    """PUBLISHED→FINISHED 前执行考生、缓考和异常闭环检查。"""
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _legacy._get_batch(db, int(bid))
        if batch.status != _legacy._B_PUBLISHED:
            raise _legacy._invalid("仅 PUBLISHED 批次可结束考试")
        issues = _batch_closure_issues(db, batch.id)
        error = _closure_error(issues)
        if error:
            raise error
        batch.status = _legacy._B_FINISHED
        _legacy._audit(db, "EXAM_BATCH", batch.id, "EXAM_BATCH_FINISH", "考试与异常均已收口")
        db.commit()
        return _legacy._batch_dto(batch)


def archive_batch(user, bid):
    """FINISHED→ARCHIVED 前再次校验，防止直接改库或历史漏检后绕过。"""
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _legacy._get_batch(db, int(bid))
        if batch.status == _legacy._B_ARCHIVED:
            return _legacy._batch_dto(batch)
        if batch.status != _legacy._B_FINISHED:
            raise _legacy._invalid("仅 FINISHED 批次可归档")
        issues = _batch_closure_issues(db, batch.id)
        error = _closure_error(issues)
        if error:
            raise error
        batch.status = _legacy._B_ARCHIVED
        _legacy._audit(db, "EXAM_BATCH", batch.id, "EXAM_BATCH_ARCHIVE", "考务闭环后归档")
        db.commit()
        return _legacy._batch_dto(batch)


def resolve_incident(user, incident_id: int, action: str, reason: str = "", discipline_case_ref: str = "") -> dict:
    """考场异常闭环。

    HANDOFF：违纪/其他异常移交处分或后续处理线索，保留 ACTIVE 事实记录；
    CLOSE：缺考风险联动已成功时确认闭环，不篡改事实状态；
    VOID：误登记作废，原因不少于5字。
    """
    from app.models import AaExamIncident

    action = _status(action)
    reason = str(reason or "").strip()
    case_ref = str(discipline_case_ref or "").strip()
    with _legacy.session() as db:
        context = _legacy._ctx(user, db)
        incident = db.query(AaExamIncident).filter(
            AaExamIncident.id == int(incident_id),
            AaExamIncident.tenant_id == _legacy._tid(),
            AaExamIncident.is_deleted.is_(False),
        ).first()
        if not incident:
            raise not_found("考场异常不存在")
        course = _legacy._get_course(db, int(incident.exam_course_id))
        batch = _legacy._get_batch(db, int(course.batch_id))
        _legacy._ensure_not_archived(batch)
        if not _legacy._is_school(context):
            _legacy._check_college_scope(context, course.college_id)

        if action == "VOID":
            if len(reason) < 5:
                raise AppException("VALIDATION_ERROR", "作废原因必填且不少于5字")
            incident.status = "VOIDED"
            closure = "VOIDED"
        elif action == "HANDOFF":
            if _status(incident.incident_type) == "ABSENT":
                raise AppException("VALIDATION_ERROR", "缺考异常应执行 CLOSE，不使用处分线索移交")
            if len(case_ref) < 3:
                raise AppException("VALIDATION_ERROR", "处分/后续处理线索编号必填")
            incident.discipline_case_ref = case_ref
            closure = "CASE_LINKED"
        elif action == "CLOSE":
            if _status(incident.incident_type) != "ABSENT":
                raise AppException("VALIDATION_ERROR", "违纪/其他异常须先移交处理线索或作废")
            if not incident.risk_alert_sent:
                raise AppException("DATA_CONFLICT", "缺考风险联动尚未成功，不可关闭", http_status=409)
            closure = "RISK_TRANSFERRED"
        else:
            raise AppException("VALIDATION_ERROR", "action仅支持 HANDOFF/CLOSE/VOID")

        _legacy._audit(
            db,
            "EXAM_INCIDENT",
            incident.id,
            f"EXAM_INCIDENT_{action}",
            f"closure={closure};caseRef={case_ref};reason={reason}"[:990],
        )
        db.commit()
        return {
            "incidentId": str(incident.id),
            "status": incident.status,
            "closureStatus": closure,
            "disciplineCaseRef": incident.discipline_case_ref,
            "resolvedAt": datetime.utcnow().isoformat(),
        }


# 原服务内部或完整路径导入仍应消费收口后的结束/归档实现。
_legacy.finish_batch = finish_batch
_legacy.archive_batch = archive_batch
