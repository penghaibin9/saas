"""C-W3 考场异常只读工作台。

现有异常写 Authority 已经能够登记、缺考风险联动、处分线索移交、关闭和作废；旧
``list_incidents`` 却只返回 ``status=ACTIVE`` 的少数字段，使已移交/已关闭/已作废事实在工作台
消失。本 provider 只消费 ``AaExamIncident`` 当前事实和 ``AaExamAuditTrail`` append-only 闭环
证据，保留完整历史；不修改 record/resolve/archive Authority，也不为读取补写任何状态。

C-W3 scale guard：闭环分类由持久化 incident facts 决定，因此 ALL/OPEN/CLOSED/VOIDED 过滤、
总量和三类计数全部下推 SQL；审计证据只读取当前页 incident IDs，不再整范围 ``.all()`` 后
Python 切片。
"""
from __future__ import annotations

import importlib

from sqlalchemy import case, func, or_, select

from app.core.affairs_security import _derive_keys, no_data_scope
from app.services.db_service import _iso, _tid

_legacy = importlib.import_module(
    "app.modules.academic_affairs.services.academic_affairs_exam_service"
)

_CLOSURE_ACTIONS = {
    "EXAM_INCIDENT_HANDOFF": "CASE_LINKED",
    "EXAM_INCIDENT_CLOSE": "RISK_TRANSFERRED",
    "EXAM_INCIDENT_VOID": "VOIDED",
}
_FORMAL_BATCH_STATUSES = {"PUBLISHED", "FINISHED", "ARCHIVED"}


def _closure_from_facts(incident) -> str:
    if str(incident.status or "").upper() == "VOIDED":
        return "VOIDED"
    if str(incident.discipline_case_ref or "").strip():
        return "CASE_LINKED"
    if str(incident.incident_type or "").upper() == "ABSENT" and bool(incident.risk_alert_sent):
        return "RISK_TRANSFERRED"
    return "OPEN"


def _closure_sql(AaExamIncident):
    """Same precedence as ``_closure_from_facts`` for SQL filtering/counts."""
    return case(
        (func.upper(func.coalesce(AaExamIncident.status, "")) == "VOIDED", "VOIDED"),
        (func.length(func.trim(func.coalesce(AaExamIncident.discipline_case_ref, ""))) > 0, "CASE_LINKED"),
        (
            (func.upper(func.coalesce(AaExamIncident.incident_type, "")) == "ABSENT")
            & (AaExamIncident.risk_alert_sent.is_(True)),
            "RISK_TRANSFERRED",
        ),
        else_="OPEN",
    )


def _audit_detail(detail: str | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for segment in str(detail or "").split(";"):
        key, sep, value = segment.partition("=")
        if sep and key.strip():
            parsed[key.strip()] = value.strip()
    return parsed


def _invigilated_course_ids(db, teacher_keys: set[str]) -> set[int]:
    from app.models import AaExamInvigilator, AaExamRoom

    keys = {str(value or "").strip() for value in teacher_keys if str(value or "").strip()}
    if not keys:
        return set()
    rows = db.execute(
        select(AaExamRoom.exam_course_id)
        .join(AaExamInvigilator, AaExamInvigilator.exam_room_id == AaExamRoom.id)
        .where(
            AaExamRoom.tenant_id == _tid(),
            AaExamRoom.status == "ACTIVE",
            AaExamRoom.is_deleted.is_(False),
            AaExamInvigilator.tenant_id == _tid(),
            AaExamInvigilator.teacher_key.in_(sorted(keys)),
            AaExamInvigilator.is_deleted.is_(False),
        )
    ).all()
    return {int(course_id) for (course_id,) in rows if course_id}


def _scoped_query(db, user, *, batch_id=None):
    from app.models import AaExamBatch, AaExamCourse, AaExamIncident, AaExamRoom

    if str((user or {}).get("userType") or "").upper() == "STUDENT":
        raise no_data_scope("学生无权访问考场异常工作台")

    context = _legacy._ctx(user, db)
    query = (
        select(AaExamIncident, AaExamCourse, AaExamBatch, AaExamRoom)
        .join(AaExamCourse, AaExamCourse.id == AaExamIncident.exam_course_id)
        .join(AaExamBatch, AaExamBatch.id == AaExamCourse.batch_id)
        .outerjoin(AaExamRoom, AaExamRoom.id == AaExamIncident.exam_room_id)
        .where(
            AaExamIncident.tenant_id == _tid(),
            AaExamIncident.is_deleted.is_(False),
            AaExamCourse.tenant_id == _tid(),
            AaExamCourse.status == "CONFIRMED",
            AaExamCourse.is_deleted.is_(False),
            AaExamBatch.tenant_id == _tid(),
            AaExamBatch.status.in_(sorted(_FORMAL_BATCH_STATUSES)),
            AaExamBatch.is_deleted.is_(False),
        )
    )
    if batch_id is not None:
        query = query.where(AaExamBatch.id == int(batch_id))

    if not _legacy._is_school(context):
        allowed_colleges = {int(value) for value in (getattr(context, "college_ids", None) or set())}
        teacher_courses = _invigilated_course_ids(db, _derive_keys(user or {}))
        scope_terms = []
        if allowed_colleges:
            scope_terms.append(AaExamCourse.college_id.in_(sorted(allowed_colleges)))
        if teacher_courses:
            scope_terms.append(AaExamCourse.id.in_(sorted(teacher_courses)))
        if not scope_terms:
            raise no_data_scope("当前账号没有可查看的考场异常范围")
        query = query.where(or_(*scope_terms))
    return query


def project_incident_workbench(
    db,
    user,
    *,
    batch_id: int | None = None,
    view: str = "ALL",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """返回当前权限范围内的考场异常全生命周期历史，SQL 真分页。"""
    from app.models import AaExamAuditTrail, AaExamIncident

    requested_view = str(view or "ALL").strip().upper()
    if requested_view not in {"ALL", "OPEN", "CLOSED", "VOIDED"}:
        requested_view = "ALL"
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 50)))

    scoped = _scoped_query(db, user, batch_id=batch_id)
    closure = _closure_sql(AaExamIncident)
    scoped_subquery = scoped.with_only_columns(
        AaExamIncident.id.label("incident_id"),
        closure.label("closure_status"),
    ).subquery()

    counts = db.execute(
        select(
            func.count(scoped_subquery.c.incident_id),
            func.coalesce(func.sum(case((scoped_subquery.c.closure_status == "OPEN", 1), else_=0)), 0),
            func.coalesce(func.sum(case((scoped_subquery.c.closure_status.in_(["CASE_LINKED", "RISK_TRANSFERRED"]), 1), else_=0)), 0),
            func.coalesce(func.sum(case((scoped_subquery.c.closure_status == "VOIDED", 1), else_=0)), 0),
        )
    ).one()
    all_total, open_count, closed_count, voided_count = [int(value or 0) for value in counts]

    list_query = scoped
    if requested_view == "OPEN":
        list_query = list_query.where(closure == "OPEN")
        total = open_count
    elif requested_view == "CLOSED":
        list_query = list_query.where(closure.in_(["CASE_LINKED", "RISK_TRANSFERRED"]))
        total = closed_count
    elif requested_view == "VOIDED":
        list_query = list_query.where(closure == "VOIDED")
        total = voided_count
    else:
        total = all_total

    rows = db.execute(
        list_query.order_by(AaExamIncident.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    incident_ids = [int(incident.id) for incident, _course, _batch, _room in rows]
    audits = []
    if incident_ids:
        audits = db.scalars(select(AaExamAuditTrail).where(
            AaExamAuditTrail.tenant_id == _tid(),
            AaExamAuditTrail.biz_type == "EXAM_INCIDENT",
            AaExamAuditTrail.biz_id.in_(incident_ids),
            AaExamAuditTrail.action.in_(sorted(_CLOSURE_ACTIONS)),
        ).order_by(AaExamAuditTrail.id.desc())).all()
    latest_audit = {}
    for audit in audits:
        latest_audit.setdefault(int(audit.biz_id), audit)

    items = []
    for incident, course, batch, room in rows:
        closure_status = _closure_from_facts(incident)
        audit = latest_audit.get(int(incident.id))
        detail = _audit_detail(audit.detail if audit else "")
        audit_closure = _CLOSURE_ACTIONS.get(str(audit.action or ""), "") if audit else ""
        # Persisted facts are authoritative. Audit may only corroborate them; any disagreement is surfaced.
        evidence_consistent = not audit_closure or audit_closure == closure_status
        items.append({
            "incidentId": str(incident.id),
            "examRoomId": str(incident.exam_room_id) if incident.exam_room_id else None,
            "examCourseId": str(course.id),
            "batchId": str(batch.id),
            "batchName": batch.batch_name or "",
            "batchStatus": batch.status,
            "courseName": course.course_name or "",
            "className": course.class_name or "",
            "collegeId": str(course.college_id) if course.college_id else None,
            "examDate": course.exam_date or "",
            "startTime": course.start_time or "",
            "endTime": course.end_time or "",
            "classroom": (room.classroom_text if room else "") or "",
            "studentId": str(incident.student_id),
            "studentNo": incident.student_no or "",
            "studentName": incident.student_name or "",
            "incidentType": incident.incident_type,
            "description": incident.description or "",
            "recordedBy": incident.recorded_by or "",
            "recordedAt": _iso(incident.recorded_at),
            "status": incident.status,
            "riskAlertSent": bool(incident.risk_alert_sent),
            "disciplineCaseRef": incident.discipline_case_ref or "",
            "closureStatus": closure_status,
            "resolutionAction": str(audit.action or "").removeprefix("EXAM_INCIDENT_") if audit else "",
            "resolutionReason": detail.get("reason", ""),
            "resolvedBy": audit.operator if audit else "",
            "resolvedAt": _iso(audit.occurred_at) if audit else None,
            "closureEvidenceConsistent": evidence_consistent,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "openCount": open_count,
        "closedCount": closed_count,
        "voidedCount": voided_count,
        "source": "CANONICAL_EXAM_INCIDENT_FACTS",
    }
