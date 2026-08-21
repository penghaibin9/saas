"""W2 canonical lifecycle for post-exam incidents.

The observed incident row stays the occurrence fact. Formal resolution is an
append-only ``AaExamAuditTrail`` event (HANDOFF/CLOSE/VOID) written in the same
transaction as the minimal incident projection update (discipline ref / VOID marker).
This keeps the existing schema while making OPEN -> terminal transitions explicit,
idempotent and concurrency-safe.
"""
from __future__ import annotations

import importlib
from datetime import datetime

from sqlalchemy import case, exists, func, select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid

from . import academic_affairs_exam_incident_workbench_service as legacy_workbench

# ``services.__init__`` publishes ``academic_affairs_exam_service`` as the facade.
# This W2 module needs the raw helpers (_ctx/_get_course/_audit/session) just like the
# existing workbench does, so resolve the concrete submodule explicitly.
legacy_service = importlib.import_module(
    "app.modules.academic_affairs.services.academic_affairs_exam_service"
)

_RESOLUTION_ACTIONS = {
    "EXAM_INCIDENT_HANDOFF": "CASE_LINKED",
    "EXAM_INCIDENT_CLOSE": "RISK_TRANSFERRED",
    "EXAM_INCIDENT_VOID": "VOIDED",
}
_WRITES_ALLOWED_BATCH_STATUSES = {"PUBLISHED", "FINISHED"}


def _resolution_reason(value: str) -> str:
    reason = str(value or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "处置原因必填且不少于5字")
    if len(reason) > 500:
        raise AppException("VALIDATION_ERROR", "处置原因最多500字")
    return reason


def _latest_resolution_query(db, incident_id: int, *, lock: bool = False):
    from app.models import AaExamAuditTrail

    query = db.query(AaExamAuditTrail).filter(
        AaExamAuditTrail.tenant_id == _tid(),
        AaExamAuditTrail.biz_type == "EXAM_INCIDENT",
        AaExamAuditTrail.biz_id == int(incident_id),
        AaExamAuditTrail.action.in_(sorted(_RESOLUTION_ACTIONS)),
    ).order_by(AaExamAuditTrail.id.desc())
    if lock:
        query = query.with_for_update()
    return query.first()


def _resolution_status(incident, audit=None) -> str:
    if audit is not None:
        return _RESOLUTION_ACTIONS.get(str(audit.action or ""), "OPEN")
    # A VOID projection without its audit is inconsistent, not a reusable OPEN fact.
    if str(incident.status or "").upper() == "VOIDED":
        return "INCONSISTENT"
    return "OPEN"


def _resolution_exists_expr(AaExamIncident, AaExamAuditTrail):
    return exists(select(1).where(
        AaExamAuditTrail.tenant_id == _tid(),
        AaExamAuditTrail.biz_type == "EXAM_INCIDENT",
        AaExamAuditTrail.biz_id == AaExamIncident.id,
        AaExamAuditTrail.action.in_(sorted(_RESOLUTION_ACTIONS)),
    ))


def _latest_action_expr(AaExamIncident, AaExamAuditTrail):
    return (
        select(AaExamAuditTrail.action)
        .where(
            AaExamAuditTrail.tenant_id == _tid(),
            AaExamAuditTrail.biz_type == "EXAM_INCIDENT",
            AaExamAuditTrail.biz_id == AaExamIncident.id,
            AaExamAuditTrail.action.in_(sorted(_RESOLUTION_ACTIONS)),
        )
        .order_by(AaExamAuditTrail.id.desc())
        .limit(1)
        .correlate(AaExamIncident)
        .scalar_subquery()
    )


def _closure_sql(AaExamIncident, AaExamAuditTrail):
    latest_action = _latest_action_expr(AaExamIncident, AaExamAuditTrail)
    return case(
        (latest_action == "EXAM_INCIDENT_VOID", "VOIDED"),
        (latest_action == "EXAM_INCIDENT_HANDOFF", "CASE_LINKED"),
        (latest_action == "EXAM_INCIDENT_CLOSE", "RISK_TRANSFERRED"),
        else_="OPEN",
    )


def _scoped_query(db, user, *, batch_id=None):
    """Reuse the existing production data-scope query; W2 does not invent new scope."""
    return legacy_workbench._scoped_query(db, user, batch_id=batch_id)


def project_incident_workbench(
    db,
    user,
    *,
    batch_id: int | None = None,
    view: str = "ALL",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Canonical workbench: only a persisted resolution event moves OPEN to terminal."""
    from app.models import AaExamAuditTrail, AaExamIncident

    requested_view = str(view or "ALL").strip().upper()
    if requested_view not in {"ALL", "OPEN", "CLOSED", "VOIDED"}:
        requested_view = "ALL"
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 50)))

    scoped = _scoped_query(db, user, batch_id=batch_id)
    closure = _closure_sql(AaExamIncident, AaExamAuditTrail)
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
            AaExamAuditTrail.action.in_(sorted(_RESOLUTION_ACTIONS)),
        ).order_by(AaExamAuditTrail.id.desc())).all()
    latest_audit = {}
    for audit in audits:
        latest_audit.setdefault(int(audit.biz_id), audit)

    items = []
    for incident, course, batch, room in rows:
        audit = latest_audit.get(int(incident.id))
        closure_status = _resolution_status(incident, audit)
        detail = legacy_workbench._audit_detail(audit.detail if audit else "")
        evidence_consistent = True
        if audit:
            if audit.action == "EXAM_INCIDENT_VOID":
                evidence_consistent = str(incident.status or "").upper() == "VOIDED"
            elif audit.action == "EXAM_INCIDENT_HANDOFF":
                evidence_consistent = bool(str(incident.discipline_case_ref or "").strip())
            elif audit.action == "EXAM_INCIDENT_CLOSE":
                evidence_consistent = (
                    str(incident.incident_type or "").upper() == "ABSENT"
                    and bool(incident.risk_alert_sent)
                )
        elif str(incident.status or "").upper() == "VOIDED":
            evidence_consistent = False

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
            "closureStatus": closure_status if closure_status != "INCONSISTENT" else "OPEN",
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
        "source": "CANONICAL_EXAM_INCIDENT_LIFECYCLE",
    }


def unresolved_incident_count(db, batch_id: int) -> int:
    """Finish/archive gate: only formal resolution events close an incident."""
    from app.models import AaExamAuditTrail, AaExamCourse, AaExamIncident

    resolved = _resolution_exists_expr(AaExamIncident, AaExamAuditTrail)
    return int(db.scalar(
        select(func.count(AaExamIncident.id))
        .join(AaExamCourse, AaExamCourse.id == AaExamIncident.exam_course_id)
        .where(
            AaExamIncident.tenant_id == _tid(),
            AaExamIncident.is_deleted.is_(False),
            AaExamCourse.tenant_id == _tid(),
            AaExamCourse.batch_id == int(batch_id),
            AaExamCourse.status != "REMOVED",
            AaExamCourse.is_deleted.is_(False),
            ~resolved,
        )
    ) or 0)


def resolve_incident(user, incident_id: int, action: str, reason: str = "", discipline_case_ref: str = "") -> dict:
    """Resolve exactly one OPEN incident under row lock; repeated/concurrent writes fail closed."""
    from app.models import AaExamIncident

    action = str(action or "").strip().upper()
    reason = _resolution_reason(reason)
    case_ref = str(discipline_case_ref or "").strip()
    if action not in {"HANDOFF", "CLOSE", "VOID"}:
        raise AppException("VALIDATION_ERROR", "action仅支持 HANDOFF/CLOSE/VOID")

    with legacy_service.session() as db:
        context = legacy_service._ctx(user, db)
        incident = db.query(AaExamIncident).filter(
            AaExamIncident.id == int(incident_id),
            AaExamIncident.tenant_id == _tid(),
            AaExamIncident.is_deleted.is_(False),
        ).with_for_update().first()
        if not incident:
            raise not_found("考场异常不存在")

        course = legacy_service._get_course(db, int(incident.exam_course_id))
        batch = legacy_service._get_batch(db, int(course.batch_id))
        if str(batch.status or "").upper() not in _WRITES_ALLOWED_BATCH_STATUSES:
            raise AppException(
                "DATA_CONFLICT",
                "仅 PUBLISHED/FINISHED 批次可处置考场异常；已归档历史永久只读",
                details={"batchStatus": batch.status},
                http_status=409,
            )
        if not legacy_service._is_school(context):
            legacy_service._check_college_scope(context, course.college_id)

        existing = _latest_resolution_query(db, int(incident.id), lock=True)
        if existing:
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "该考场异常已完成正式处置，请刷新工作台查看最新事实",
                details={
                    "incidentId": str(incident.id),
                    "closureStatus": _RESOLUTION_ACTIONS.get(existing.action, "CLOSED"),
                    "resolutionAction": str(existing.action or "").removeprefix("EXAM_INCIDENT_"),
                },
                http_status=409,
            )
        if str(incident.status or "").upper() == "VOIDED":
            raise AppException(
                "DATA_CONFLICT",
                "异常已标记 VOIDED 但缺少正式处置审计，数据不一致，禁止覆盖",
                http_status=409,
            )

        incident_type = str(incident.incident_type or "").strip().upper()
        before = "OPEN"
        if action == "VOID":
            incident.status = "VOIDED"
            closure = "VOIDED"
        elif action == "HANDOFF":
            if incident_type == "ABSENT":
                raise AppException("VALIDATION_ERROR", "缺考异常应执行 CLOSE，不使用处分线索移交")
            if len(case_ref) < 3:
                raise AppException("VALIDATION_ERROR", "处分/后续处理线索编号必填且不少于3字")
            incident.discipline_case_ref = case_ref
            closure = "CASE_LINKED"
        else:
            if incident_type != "ABSENT":
                raise AppException("VALIDATION_ERROR", "违纪/其他异常须移交处理线索或作废")
            if not incident.risk_alert_sent:
                raise AppException("DATA_CONFLICT", "缺考风险联动尚未成功，不可关闭", http_status=409)
            closure = "RISK_TRANSFERRED"

        legacy_service._audit(
            db,
            "EXAM_INCIDENT",
            incident.id,
            f"EXAM_INCIDENT_{action}",
            f"closure={closure};caseRef={case_ref};reason={' '.join(reason.split())}"[:990],
            before,
            closure,
        )
        db.commit()
        return {
            "incidentId": str(incident.id),
            "status": incident.status,
            "closureStatus": closure,
            "disciplineCaseRef": incident.discipline_case_ref or "",
            "resolvedAt": datetime.utcnow().isoformat(),
        }


def install() -> None:
    """Bind existing public facade finish/archive gates to the same lifecycle authority."""
    from . import academic_affairs_exam_facade as public_facade

    if not hasattr(public_facade, "_w2_original_batch_closure_issues"):
        public_facade._w2_original_batch_closure_issues = public_facade._batch_closure_issues

    original = public_facade._w2_original_batch_closure_issues

    def _batch_closure_issues(db, batch_id: int):
        issues = original(db, batch_id)
        issues["unresolvedIncidents"] = unresolved_incident_count(db, int(batch_id))
        return issues

    public_facade._batch_closure_issues = _batch_closure_issues
    public_facade.resolve_incident = resolve_incident
