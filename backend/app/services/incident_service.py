"""PLAT-09 事件、状态页与统一学校通知。

受众计算复用 PLAT-08 的 service_catalog_service.compute_service_impact
（同一套"谁受影响"判定，不另建一套）；站内通知直接写 t_unified_message
（不走 message_event_outbox_service 的 _EVENT_TEMPLATES 硬编码事件表——
那个文件不在本卡白名单内，不能新增事件码）。

外部更新（external_message，学校侧看到的）与内部时间线（internal_note，
只有事件指挥/运维自己看）分字段存储，序列化输出时永远分开返回，
避免把内部排查细节、IP、其它租户信息带出去。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.incident import Incident, IncidentTenant, IncidentUpdate

STATUS_ORDER = ["DETECTED", "ACKNOWLEDGED", "MITIGATING", "MONITORING", "RESOLVED"]


def _session():
    return get_sessionmaker()()


def _actor_id(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or "").removeprefix("db-")
    return int(raw) if raw.isdigit() else None


def _incident_dto(incident: Incident, tenants: list[IncidentTenant] | None = None,
                  updates: list[IncidentUpdate] | None = None, *, include_internal: bool = True) -> dict:
    dto = {
        "incidentId": str(incident.id), "title": incident.title, "severity": incident.severity,
        "status": incident.status, "affectedServiceCodes": incident.affected_service_codes_json or [],
        "commanderName": incident.commander_name,
        "detectedAt": incident.detected_at.isoformat() if incident.detected_at else None,
        "resolvedAt": incident.resolved_at.isoformat() if incident.resolved_at else None,
        "problemConversionRequestedAt": (
            incident.problem_conversion_requested_at.isoformat()
            if incident.problem_conversion_requested_at else None),
        "version": int(incident.version or 0),
    }
    if tenants is not None:
        dto["affectedTenants"] = [{"tenantId": str(t.tenant_id), "impactType": t.impact_type}
                                  for t in tenants]
    if updates is not None:
        dto["updates"] = [_update_dto(u, include_internal=include_internal) for u in
                          sorted(updates, key=lambda x: x.update_seq)]
    return dto


def _update_dto(update: IncidentUpdate, *, include_internal: bool) -> dict:
    dto = {
        "updateId": str(update.id), "updateSeq": update.update_seq,
        "statusAtUpdate": update.status_at_update, "externalMessage": update.external_message,
        "templateVersion": update.template_version, "published": update.published,
        "publishedAt": update.published_at.isoformat() if update.published_at else None,
        "notificationResult": update.notification_result_json,
    }
    if include_internal:
        dto["internalNote"] = update.internal_note
    return dto


def create_incident(user: dict, body: dict) -> dict:
    from app.services import service_catalog_service as svcat

    title = str(body.get("title") or "").strip()
    if len(title) < 2:
        raise AppException("VALIDATION_ERROR", "事件标题必填", http_status=422)
    severity = str(body.get("severity") or "P2").upper()
    if severity not in ("P0", "P1", "P2", "P3"):
        raise AppException("VALIDATION_ERROR", "severity 必须是 P0/P1/P2/P3", http_status=422)
    service_codes = [str(c).strip() for c in (body.get("affectedServiceCodes") or []) if str(c).strip()]
    if not service_codes:
        raise AppException("VALIDATION_ERROR", "至少登记一个受影响服务", http_status=422)

    direct: set[str] = set()
    indirect: set[str] = set()
    for code in service_codes:
        impact = svcat.compute_service_impact(code)
        direct.update(impact["directTenants"])
        indirect.update(impact["indirectTenants"])
    indirect -= direct

    with _session() as db:
        incident = Incident(
            title=title, severity=severity, status="DETECTED",
            affected_service_codes_json=service_codes,
            commander_user_id=_actor_id(user), commander_name=(user or {}).get("realName"),
            detected_at=datetime.utcnow())
        db.add(incident)
        db.flush()
        # 受众快照：创建这一刻冻结，后续依赖图变化不会改写这次事件通知过谁
        for tid in sorted(direct):
            db.add(IncidentTenant(incident_id=incident.id, tenant_id=int(tid), impact_type="DIRECT"))
        for tid in sorted(indirect):
            db.add(IncidentTenant(incident_id=incident.id, tenant_id=int(tid), impact_type="INDIRECT"))
        db.commit()
        tenants = db.scalars(select(IncidentTenant).where(
            IncidentTenant.incident_id == incident.id)).all()
        return _incident_dto(incident, list(tenants), [])


def get_incident(incident_id: int, *, include_internal: bool = True) -> dict:
    with _session() as db:
        incident = db.get(Incident, int(incident_id))
        if not incident or incident.is_deleted:
            raise AppException("DATA_NOT_FOUND", "事件不存在", http_status=404)
        tenants = db.scalars(select(IncidentTenant).where(
            IncidentTenant.incident_id == incident.id, IncidentTenant.is_deleted.is_(False))).all()
        updates = db.scalars(select(IncidentUpdate).where(
            IncidentUpdate.incident_id == incident.id, IncidentUpdate.is_deleted.is_(False))).all()
        return _incident_dto(incident, list(tenants), list(updates), include_internal=include_internal)


def list_incidents(*, status: str | None = None) -> list[dict]:
    with _session() as db:
        q = select(Incident).where(Incident.is_deleted.is_(False))
        if status:
            q = q.where(Incident.status == status)
        rows = db.scalars(q.order_by(Incident.id.desc())).all()
        return [_incident_dto(r) for r in rows]


def transition_status(incident_id: int, new_status: str, *, user: dict | None = None) -> dict:
    if new_status not in STATUS_ORDER:
        raise AppException("VALIDATION_ERROR", "非法事件状态", http_status=422)
    with _session() as db:
        incident = db.get(Incident, int(incident_id))
        if not incident or incident.is_deleted:
            raise AppException("DATA_NOT_FOUND", "事件不存在", http_status=404)
        cur_idx = STATUS_ORDER.index(incident.status)
        new_idx = STATUS_ORDER.index(new_status)
        if new_idx < cur_idx:
            raise AppException("DATA_CONFLICT", "事件状态不能倒退", http_status=409)
        incident.status = new_status
        incident.version = int(incident.version or 0) + 1
        if new_status == "RESOLVED":
            incident.resolved_at = datetime.utcnow()
        db.commit()
        return _incident_dto(incident)


def add_update(incident_id: int, body: dict, *, user: dict | None = None) -> dict:
    external_message = str(body.get("externalMessage") or "").strip()
    if len(external_message) < 2:
        raise AppException("VALIDATION_ERROR", "对外更新内容必填", http_status=422)
    with _session() as db:
        incident = db.get(Incident, int(incident_id))
        if not incident or incident.is_deleted:
            raise AppException("DATA_NOT_FOUND", "事件不存在", http_status=404)
        max_seq = db.scalar(select(IncidentUpdate.update_seq).where(
            IncidentUpdate.incident_id == incident.id).order_by(IncidentUpdate.update_seq.desc()))
        update = IncidentUpdate(
            incident_id=incident.id, update_seq=int(max_seq or 0) + 1,
            status_at_update=incident.status, internal_note=body.get("internalNote") or None,
            external_message=external_message, template_version=body.get("templateVersion") or "v1",
            published=False)
        db.add(update)
        db.commit()
        return _update_dto(update, include_internal=True)


def publish_update(incident_id: int, update_id: int, *, user: dict | None = None) -> dict:
    """只通知这次事件创建时冻结的受众快照，不重新计算当前依赖图（PLAT09-T01）；
    对每个租户的通知写入用 select-then-insert 判断是否已经发过，重试不会产生第二条
    站内消息（PLAT09-T02）。"""
    from app.models import User
    from app.models.message import UnifiedMessage

    with _session() as db:
        incident = db.get(Incident, int(incident_id))
        if not incident or incident.is_deleted:
            raise AppException("DATA_NOT_FOUND", "事件不存在", http_status=404)
        update = db.get(IncidentUpdate, int(update_id))
        if not update or update.incident_id != incident.id:
            raise AppException("DATA_NOT_FOUND", "该更新不存在", http_status=404)

        tenants = db.scalars(select(IncidentTenant).where(
            IncidentTenant.incident_id == incident.id, IncidentTenant.is_deleted.is_(False))).all()
        prior_result = dict(update.notification_result_json or {})
        result: dict[str, dict] = dict(prior_result)
        for it in tenants:
            tid = int(it.tenant_id)
            key = str(tid)
            if result.get(key, {}).get("status") == "SUCCEEDED":
                continue  # 之前已经成功送达，重试不重复发
            admins = db.scalars(select(User).where(
                User.tenant_id == tid, User.user_type == "SCHOOL_ADMIN",
                User.is_deleted.is_(False), User.status == "ACTIVE")).all()
            if not admins:
                result[key] = {"status": "FAILED", "reason": "该校无有效管理员账号可接收通知"}
                continue
            delivered = 0
            for admin in admins:
                ctx_key = f"incident:{incident.id}:{update.update_seq}"
                existed = db.scalars(select(UnifiedMessage).where(
                    UnifiedMessage.tenant_id == tid, UnifiedMessage.receiver_user_id == admin.id,
                    UnifiedMessage.receiver_context_key == ctx_key,
                    UnifiedMessage.is_deleted.is_(False))).first()
                if existed:
                    delivered += 1
                    continue
                db.add(UnifiedMessage(
                    tenant_id=tid, receiver_id=admin.id, receiver_user_id=admin.id,
                    receiver_context_key=ctx_key, source_module="platform-incident",
                    source_biz_id=incident.id, title=f"[{incident.severity}] {incident.title}",
                    content=update.external_message, message_type="EMERGENCY", status="UNREAD"))
                delivered += 1
            result[key] = {"status": "SUCCEEDED", "deliveredCount": delivered}

        update.notification_result_json = result
        update.published = True
        update.published_at = datetime.utcnow()
        update.template_version = update.template_version or "v1"
        db.commit()
        return _update_dto(update, include_internal=True)


def request_problem_conversion(incident_id: int, *, user: dict | None = None) -> dict:
    """PLAT-10（问题管理）尚未建卡，这里不新建 Problem 实体，只做资格判定与请求标记：
    只有 RESOLVED 状态的事件才允许发起转 Problem。"""
    with _session() as db:
        incident = db.get(Incident, int(incident_id))
        if not incident or incident.is_deleted:
            raise AppException("DATA_NOT_FOUND", "事件不存在", http_status=404)
        if incident.status != "RESOLVED":
            raise AppException("DATA_CONFLICT", "只有 RESOLVED 状态的事件才能转 Problem", http_status=409)
        incident.problem_conversion_requested_at = datetime.utcnow()
        incident.problem_conversion_requested_by = _actor_id(user)
        db.commit()
        return _incident_dto(incident)


def governance_overview() -> dict:
    with _session() as db:
        incidents = db.scalars(select(Incident).where(Incident.is_deleted.is_(False))).all()
        active = [i for i in incidents if i.status != "RESOLVED"]
        p0p1_active = [i for i in active if i.severity in ("P0", "P1")]
        unacked = [i for i in active if i.status == "DETECTED"]
        latest_updates: dict[int, datetime] = {}
        coverage: dict[int, bool] = {}
        for inc in active:
            updates = db.scalars(select(IncidentUpdate).where(
                IncidentUpdate.incident_id == inc.id, IncidentUpdate.is_deleted.is_(False)
            ).order_by(IncidentUpdate.update_seq.desc())).all()
            if updates:
                latest_updates[inc.id] = updates[0].updated_at
                coverage[inc.id] = bool(updates[0].published)
            else:
                coverage[inc.id] = False
        return {
            "activeCount": len(active), "p0p1ActiveCount": len(p0p1_active),
            "unacknowledgedCount": len(unacked),
            "notificationCoverage": {str(k): v for k, v in coverage.items()},
            "activeIncidents": [_incident_dto(i) for i in active],
        }
