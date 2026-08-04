"""PLAT-05 客户健康、工单、培训与续费。

健康分是实时判定，直接复用 PLAT-09 受影响租户快照、platform_service 的
到期时间，加上本卡自己的工单积压/续费逾期——不落表、不重复判定各域已有的
结论（见 app/models/customer_success.py 顶部注释）。SYS-01 的上线检查阻断
不计入健康分：那是"建档是否完整"，跟"已上线客户是否健康"是两回事。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.customer_success import RenewalTask, SupportTicket, TrainingRecord

TICKET_STATUSES = ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED")
TRAINING_STATUSES = ("SCHEDULED", "COMPLETED", "CANCELLED")
RENEWAL_STATUSES = ("PENDING", "CONTACTED", "COMMITTED", "RENEWED", "CHURNED")

HEALTHY, AT_RISK, CRITICAL = "HEALTHY", "AT_RISK", "CRITICAL"


def _now() -> datetime:
    return datetime.utcnow()


def _session():
    return get_sessionmaker()()


def _ticket_dto(row: SupportTicket) -> dict:
    return {
        "id": str(row.id), "tenantId": str(row.tenant_id), "title": row.title,
        "description": row.description or "", "severity": row.severity, "status": row.status,
        "reporterName": row.reporter_name or "", "assigneeUserId": str(row.assignee_user_id or "") or None,
        "assigneeName": row.assignee_name or "", "resolvedAt": row.resolved_at.isoformat() if row.resolved_at else None,
        "resolutionNote": row.resolution_note or "", "version": int(row.version or 0),
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def create_ticket(*, tenant_id: int, title: str, description: str = "", severity: str = "P2",
                  reporter_name: str = "") -> dict:
    title = str(title or "").strip()
    if len(title) < 2:
        raise AppException("VALIDATION_ERROR", "工单标题不能为空")
    if severity not in ("P0", "P1", "P2", "P3"):
        raise AppException("VALIDATION_ERROR", f"不支持的优先级：{severity}")
    with _session() as db:
        row = SupportTicket(tenant_id=int(tenant_id), title=title, description=description,
                            severity=severity, status="OPEN", reporter_name=reporter_name)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _ticket_dto(row)


def list_tickets(*, tenant_id: int | None = None, status: str | None = None) -> list[dict]:
    with _session() as db:
        q = select(SupportTicket).where(SupportTicket.is_deleted.is_(False))
        if tenant_id:
            q = q.where(SupportTicket.tenant_id == int(tenant_id))
        if status:
            q = q.where(SupportTicket.status == status)
        rows = db.scalars(q.order_by(SupportTicket.id.desc())).all()
        return [_ticket_dto(r) for r in rows]


def transition_ticket(ticket_id: int, *, status: str, resolution_note: str = "",
                      expected_version: int) -> dict:
    if status not in TICKET_STATUSES:
        raise AppException("VALIDATION_ERROR", f"不支持的工单状态：{status}")
    with _session() as db:
        row = db.get(SupportTicket, int(ticket_id))
        if row is None or row.is_deleted:
            raise not_found("工单不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "工单已被修改，请刷新后重试", http_status=409,
                               details={"currentVersion": int(row.version or 0)})
        row.status = status
        row.version = int(row.version or 0) + 1
        if status in ("RESOLVED", "CLOSED"):
            row.resolved_at = _now()
            if resolution_note:
                row.resolution_note = resolution_note
        db.commit()
        db.refresh(row)
        return _ticket_dto(row)


def _training_dto(row: TrainingRecord) -> dict:
    return {
        "id": str(row.id), "tenantId": str(row.tenant_id), "topic": row.topic,
        "trainerName": row.trainer_name or "", "scheduledAt": row.scheduled_at.isoformat(),
        "status": row.status, "attendeeCount": int(row.attendee_count or 0),
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
        "note": row.note or "", "version": int(row.version or 0),
    }


def create_training(*, tenant_id: int, topic: str, scheduled_at: datetime,
                    trainer_name: str = "") -> dict:
    topic = str(topic or "").strip()
    if len(topic) < 2:
        raise AppException("VALIDATION_ERROR", "培训主题不能为空")
    with _session() as db:
        row = TrainingRecord(tenant_id=int(tenant_id), topic=topic, trainer_name=trainer_name,
                             scheduled_at=scheduled_at, status="SCHEDULED")
        db.add(row)
        db.commit()
        db.refresh(row)
        return _training_dto(row)


def list_trainings(*, tenant_id: int | None = None) -> list[dict]:
    with _session() as db:
        q = select(TrainingRecord).where(TrainingRecord.is_deleted.is_(False))
        if tenant_id:
            q = q.where(TrainingRecord.tenant_id == int(tenant_id))
        rows = db.scalars(q.order_by(TrainingRecord.scheduled_at.desc())).all()
        return [_training_dto(r) for r in rows]


def complete_training(training_id: int, *, attendee_count: int, note: str = "",
                      expected_version: int) -> dict:
    with _session() as db:
        row = db.get(TrainingRecord, int(training_id))
        if row is None or row.is_deleted:
            raise not_found("培训记录不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "培训记录已被修改，请刷新后重试", http_status=409,
                               details={"currentVersion": int(row.version or 0)})
        if row.status == "CANCELLED":
            raise AppException("STATE_TRANSITION_DENIED", "已取消的培训不能标记完成", http_status=409)
        row.status = "COMPLETED"
        row.attendee_count = max(0, int(attendee_count))
        row.completed_at = _now()
        if note:
            row.note = note
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        return _training_dto(row)


def _renewal_dto(row: RenewalTask) -> dict:
    return {
        "id": str(row.id), "tenantId": str(row.tenant_id), "dueAt": row.due_at.isoformat(),
        "status": row.status, "ownerUserId": str(row.owner_user_id or "") or None,
        "ownerName": row.owner_name or "", "note": row.note or "",
        "lastContactedAt": row.last_contacted_at.isoformat() if row.last_contacted_at else None,
        "closedAt": row.closed_at.isoformat() if row.closed_at else None,
        "version": int(row.version or 0),
    }


def create_renewal_task(*, tenant_id: int, due_at: datetime, owner_name: str = "",
                        note: str = "") -> dict:
    with _session() as db:
        row = RenewalTask(tenant_id=int(tenant_id), due_at=due_at, status="PENDING",
                          owner_name=owner_name, note=note)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _renewal_dto(row)


def list_renewal_tasks(*, tenant_id: int | None = None, status: str | None = None) -> list[dict]:
    with _session() as db:
        q = select(RenewalTask).where(RenewalTask.is_deleted.is_(False))
        if tenant_id:
            q = q.where(RenewalTask.tenant_id == int(tenant_id))
        if status:
            q = q.where(RenewalTask.status == status)
        rows = db.scalars(q.order_by(RenewalTask.due_at.asc())).all()
        return [_renewal_dto(r) for r in rows]


def update_renewal_task(task_id: int, *, status: str, note: str = "", expected_version: int) -> dict:
    if status not in RENEWAL_STATUSES:
        raise AppException("VALIDATION_ERROR", f"不支持的续费任务状态：{status}")
    with _session() as db:
        row = db.get(RenewalTask, int(task_id))
        if row is None or row.is_deleted:
            raise not_found("续费任务不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "续费任务已被修改，请刷新后重试", http_status=409,
                               details={"currentVersion": int(row.version or 0)})
        row.status = status
        row.version = int(row.version or 0) + 1
        if note:
            row.note = note
        if status == "CONTACTED":
            row.last_contacted_at = _now()
        if status in ("RENEWED", "CHURNED"):
            row.closed_at = _now()
        db.commit()
        db.refresh(row)
        return _renewal_dto(row)


def _active_incident_impact(db, tenant_id: int) -> str | None:
    """本校当前是否受活跃事件影响；返回最高严重级别（P0/P1/...）或 None。"""
    from app.models.incident import Incident, IncidentTenant

    rows = db.execute(
        select(Incident.severity)
        .join(IncidentTenant, IncidentTenant.incident_id == Incident.id)
        .where(IncidentTenant.tenant_id == tenant_id, IncidentTenant.is_deleted.is_(False),
               Incident.is_deleted.is_(False), Incident.status != "RESOLVED")
    ).all()
    severities = [r[0] for r in rows]
    for level in ("P0", "P1", "P2", "P3"):
        if level in severities:
            return level
    return None


def health_score(tenant_id: int) -> dict:
    """AT_RISK/CRITICAL 只看已上线学校的运营信号（活跃事件、工单积压、到期临近、
    续费逾期），不把 SYS-01 的上线检查阻断计进来——那是"是否建档完整"，不是
    "这个已经在用的客户是否健康"，混进来会让每个刚开通、还没建完组织架构的
    新学校都被误判成风险学校，噪音淹没真信号。"""
    from app.services.platform_service import tenant_meta

    tid = int(tenant_id)
    meta = tenant_meta(tid) or {}
    expire_at = meta.get("expireAt")
    days_left = None
    if expire_at:
        try:
            days_left = (datetime.fromisoformat(expire_at) - _now()).days
        except ValueError:
            days_left = None

    with _session() as db:
        incident_severity = _active_incident_impact(db, tid)
        open_tickets = db.scalar(select(func.count()).select_from(SupportTicket).where(
            SupportTicket.tenant_id == tid, SupportTicket.is_deleted.is_(False),
            SupportTicket.status.in_(("OPEN", "IN_PROGRESS")))) or 0
        open_p0_tickets = db.scalar(select(func.count()).select_from(SupportTicket).where(
            SupportTicket.tenant_id == tid, SupportTicket.is_deleted.is_(False),
            SupportTicket.status.in_(("OPEN", "IN_PROGRESS")), SupportTicket.severity == "P0")) or 0
        pending_renewal_overdue = db.scalar(select(func.count()).select_from(RenewalTask).where(
            RenewalTask.tenant_id == tid, RenewalTask.is_deleted.is_(False),
            RenewalTask.status.in_(("PENDING", "CONTACTED")), RenewalTask.due_at < _now())) or 0

    reasons: list[str] = []
    level = HEALTHY
    if incident_severity in ("P0", "P1") or open_p0_tickets or (days_left is not None and days_left <= 7 and days_left >= 0) or (days_left is not None and days_left < 0):
        level = CRITICAL
        if incident_severity in ("P0", "P1"):
            reasons.append(f"存在受影响的 {incident_severity} 事件")
        if open_p0_tickets:
            reasons.append(f"{open_p0_tickets} 个 P0 工单未关闭")
        if days_left is not None and days_left < 0:
            reasons.append("已超过到期时间")
        elif days_left is not None and days_left <= 7:
            reasons.append(f"距到期仅 {days_left} 天")
    elif open_tickets >= 3 or (days_left is not None and days_left <= 30) or pending_renewal_overdue:
        level = AT_RISK
        if open_tickets >= 3:
            reasons.append(f"{open_tickets} 个工单未关闭")
        if days_left is not None and days_left <= 30:
            reasons.append(f"距到期 {days_left} 天")
        if pending_renewal_overdue:
            reasons.append(f"{pending_renewal_overdue} 项续费跟进已逾期")

    return {
        "tenantId": str(tid), "level": level, "reasons": reasons,
        "openTickets": open_tickets, "openP0Tickets": open_p0_tickets,
        "activeIncidentSeverity": incident_severity, "daysToExpiry": days_left,
        "overdueRenewalTasks": pending_renewal_overdue,
    }


def governance_overview() -> dict:
    from sqlalchemy import select as sa_select

    from app.models import Tenant

    db = _session()
    try:
        tenants = db.scalars(sa_select(Tenant).where(Tenant.is_deleted.is_(False))).all()
    finally:
        db.close()

    scores = [health_score(t.id) for t in tenants]
    by_level = {HEALTHY: 0, AT_RISK: 0, CRITICAL: 0}
    critical_tenants = []
    for t, s in zip(tenants, scores):
        by_level[s["level"]] = by_level.get(s["level"], 0) + 1
        if s["level"] == CRITICAL:
            critical_tenants.append({"tenantId": s["tenantId"], "tenantName": t.school_name,
                                     "reasons": s["reasons"]})

    with _session() as db:
        open_tickets_total = db.scalar(select(func.count()).select_from(SupportTicket).where(
            SupportTicket.is_deleted.is_(False), SupportTicket.status.in_(("OPEN", "IN_PROGRESS")))) or 0
        upcoming_renewals = db.scalar(select(func.count()).select_from(RenewalTask).where(
            RenewalTask.is_deleted.is_(False), RenewalTask.status.in_(("PENDING", "CONTACTED")))) or 0
        scheduled_trainings = db.scalar(select(func.count()).select_from(TrainingRecord).where(
            TrainingRecord.is_deleted.is_(False), TrainingRecord.status == "SCHEDULED")) or 0

    return {
        "tenantCount": len(tenants),
        "healthDistribution": by_level,
        "criticalTenants": critical_tenants[:10],
        "openTicketsTotal": open_tickets_total,
        "upcomingRenewals": upcoming_renewals,
        "scheduledTrainings": scheduled_trainings,
    }
