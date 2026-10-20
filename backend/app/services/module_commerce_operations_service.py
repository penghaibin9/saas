"""M8 customer-success bridge, SLA observation and actual service-cost governance.

The existing customer-success tables remain authoritative for ticket/training/renewal
state.  This service only creates a SupportTicket atomically with a settled-refund link
when an operator explicitly requests follow-up.  It never revokes entitlement.

SLA compliance is evaluated only when an explicit COMMERCIAL_SLA_POLICY /
SUPPORT_TICKET config exists.  No default target is invented.  Service costs are
operator-recorded actual facts and are summarized per currency; currencies are never
converted or summed together.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker
from app.services.commercial_catalog_contract import ContractError, money

_COST_TYPES = {"SUPPORT", "DELIVERY", "TRAINING", "REFUND_FEE", "OTHER"}
_ACTIVE_SOURCE_STATES = ("ACTIVE", "SCHEDULED", "CANCEL_SCHEDULED")
_SLA_CONFIG_TYPE = "COMMERCIAL_SLA_POLICY"
_SLA_CONFIG_KEY = "SUPPORT_TICKET"


def _require_db() -> None:
    if not db_enabled():
        raise AppException("SERVER_ERROR", "商业运营治理需要数据库", http_status=503)


def _int_id(value, field: str) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        result = int(value)
        if result <= 0:
            raise ValueError
        return result
    except (TypeError, ValueError, OverflowError):
        raise AppException("VALIDATION_ERROR", f"{field} 无效", http_status=422) from None


def _optional_id(value, field: str) -> int | None:
    if value in (None, ""):
        return None
    return _int_id(value, field)


def _actor_id(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or (user or {}).get("id") or "").removeprefix("db-")
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


def _text(value, field: str, *, minimum: int = 0, maximum: int = 500) -> str:
    result = str(value or "").strip()
    if len(result) < minimum or len(result) > maximum:
        raise AppException("VALIDATION_ERROR", f"{field} 长度必须为 {minimum}~{maximum} 字符", http_status=422)
    return result


def _currency(value) -> str:
    result = str(value or "").strip().upper()
    if len(result) != 3 or not result.isascii() or not result.isalpha():
        raise AppException("VALIDATION_ERROR", "currency 必须是3位字母币种代码", http_status=422)
    return result


def _amount(value) -> Decimal:
    try:
        result = money(value, "amount")
    except ContractError as exc:
        raise AppException("VALIDATION_ERROR", str(exc), http_status=422) from exc
    if result <= Decimal("0.00"):
        raise AppException("VALIDATION_ERROR", "amount 必须大于0", http_status=422)
    return result


def _utc_naive(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw:
            raise AppException("VALIDATION_ERROR", "occurredAt 必填", http_status=422)
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AppException("VALIDATION_ERROR", "occurredAt 必须是ISO日期时间", http_status=422) from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.replace(microsecond=0)


def _hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _request_hash(tenant_id: int, key: str) -> str:
    text = str(key or "").strip()
    if not 8 <= len(text) <= 200:
        raise AppException("VALIDATION_ERROR", "Idempotency-Key 长度必须为8~200", http_status=422)
    return hashlib.sha256(f"service-cost:{int(tenant_id)}:{text}".encode("utf-8")).hexdigest()


def _active_entitlement_modules(db, tenant_id: int, order_id: int) -> list[dict[str, Any]]:
    from app.models import CommercialOrderItem, TenantModuleSubscriptionSource

    rows = db.execute(select(
        TenantModuleSubscriptionSource.module_key,
        func.count(TenantModuleSubscriptionSource.id),
    ).select_from(TenantModuleSubscriptionSource).join(
        CommercialOrderItem,
        (CommercialOrderItem.id == TenantModuleSubscriptionSource.order_item_id)
        & (CommercialOrderItem.tenant_id == TenantModuleSubscriptionSource.tenant_id),
    ).where(
        CommercialOrderItem.tenant_id == int(tenant_id),
        CommercialOrderItem.order_id == int(order_id),
        CommercialOrderItem.is_deleted.is_(False),
        TenantModuleSubscriptionSource.is_deleted.is_(False),
        TenantModuleSubscriptionSource.status.in_(_ACTIVE_SOURCE_STATES),
    ).group_by(TenantModuleSubscriptionSource.module_key).order_by(TenantModuleSubscriptionSource.module_key)).all()
    return [{"moduleKey": str(module), "sourceCount": int(count or 0)} for module, count in rows]


def _after_sales_dto(db, link, ticket, *, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.utcnow()
    policy = _sla_policy(db, int(link.tenant_id))
    created = ticket.created_at or link.linked_at or current
    end = ticket.resolved_at or current
    elapsed_hours = max((end - created).total_seconds(), 0.0) / 3600.0
    target = policy.get("targetsHours", {}).get(str(ticket.severity or "").upper()) if policy.get("configured") else None
    if target is None:
        sla_status = "UNASSESSED"
    else:
        sla_status = "BREACHED" if elapsed_hours > float(target) else "WITHIN_TARGET"
    return {
        "linkId": str(link.id), "tenantId": str(link.tenant_id),
        "refundCaseId": str(link.refund_case_id), "orderId": str(link.order_id),
        "supportTicketId": str(link.support_ticket_id), "linkType": link.link_type,
        "moduleSnapshot": list(link.module_snapshot_json or []),
        "settlementRef": link.settlement_ref_snapshot,
        "linkedAt": link.linked_at.isoformat(timespec="seconds") if link.linked_at else None,
        "ticket": {
            "id": str(ticket.id), "title": ticket.title, "severity": ticket.severity,
            "status": ticket.status, "assigneeName": ticket.assignee_name or "",
            "createdAt": ticket.created_at.isoformat(timespec="seconds") if ticket.created_at else None,
            "resolvedAt": ticket.resolved_at.isoformat(timespec="seconds") if ticket.resolved_at else None,
            "version": int(ticket.version or 0),
        },
        "sla": {
            "elapsedHours": round(elapsed_hours, 2),
            "targetHours": target,
            "status": sla_status,
            "policyConfigured": bool(policy.get("configured")),
            "policyVersion": policy.get("version"),
            "policySource": policy.get("source"),
            "policyInvalid": bool(policy.get("invalid")),
        },
        "entitlementChangeApplied": False,
    }


def _sla_policy(db, tenant_id: int) -> dict[str, Any]:
    from app.models import PlatformConfig

    rows = list(db.scalars(select(PlatformConfig).where(
        PlatformConfig.tenant_id.in_((0, int(tenant_id))),
        PlatformConfig.config_type == _SLA_CONFIG_TYPE,
        PlatformConfig.config_key == _SLA_CONFIG_KEY,
        PlatformConfig.enabled.is_(True),
        PlatformConfig.status == "ACTIVE",
        PlatformConfig.is_deleted.is_(False),
    ).order_by(PlatformConfig.id.desc())).all())
    selected = next((row for row in rows if int(row.tenant_id) == int(tenant_id)), None)
    selected = selected or next((row for row in rows if int(row.tenant_id) == 0), None)
    if selected is None:
        return {"configured": False, "invalid": False, "version": None, "source": None, "targetsHours": {}}
    data = dict(selected.config_json or {})
    raw_targets = data.get("targetsHours") if isinstance(data.get("targetsHours"), dict) else {}
    targets: dict[str, float] = {}
    invalid = False
    for severity in ("P0", "P1", "P2", "P3"):
        value = raw_targets.get(severity)
        if value is None:
            continue
        try:
            hours = float(value)
        except (TypeError, ValueError, OverflowError):
            invalid = True; continue
        if not (0 < hours <= 87600):
            invalid = True; continue
        targets[severity] = hours
    version = str(data.get("version") or "").strip() or None
    return {
        "configured": bool(version and targets and not invalid),
        "invalid": bool(invalid or not version or not targets),
        "version": version,
        "source": "TENANT" if int(selected.tenant_id) else "PLATFORM_DEFAULT",
        "targetsHours": targets,
    }


def ensure_refund_after_sales_ticket(
    user: dict | None, tenant_id: int, refund_case_id: int, *, severity: str, reason: str,
) -> dict[str, Any]:
    """Atomically create/replay the ticket link for one settled refund.

    Locking the refund row serializes concurrent retries.  Ticket + link + both audit
    facts commit in one transaction, so a request cannot leave an orphan support ticket.
    """
    _require_db()
    from app.models import CommercialAfterSalesLink, CommercialRefundCase
    from app.models.customer_success import SupportTicket
    from app.services import audit_log

    tid = _int_id(tenant_id, "tenantId"); case_id = _int_id(refund_case_id, "refundCaseId")
    level = str(severity or "").strip().upper()
    if level not in {"P0", "P1", "P2", "P3"}:
        raise AppException("VALIDATION_ERROR", "severity 必须明确选择 P0/P1/P2/P3", http_status=422)
    reason_text = _text(reason, "售后复核说明", minimum=5, maximum=500)
    db = get_sessionmaker()()
    try:
        refund = db.scalars(select(CommercialRefundCase).where(
            CommercialRefundCase.id == case_id,
            CommercialRefundCase.tenant_id == tid,
            CommercialRefundCase.is_deleted.is_(False),
        ).with_for_update()).first()
        if refund is None:
            raise AppException("DATA_NOT_FOUND", "退款记录不存在或不属于该学校", http_status=404)
        if str(refund.status or "").upper() != "SETTLED":
            raise AppException("DATA_CONFLICT", "只有已登记外部结算凭据的退款才能进入售后授权复核", http_status=409)

        existing = db.scalars(select(CommercialAfterSalesLink).where(
            CommercialAfterSalesLink.tenant_id == tid,
            CommercialAfterSalesLink.refund_case_id == case_id,
            CommercialAfterSalesLink.is_deleted.is_(False),
        ).with_for_update()).first()
        if existing is not None:
            ticket = db.get(SupportTicket, int(existing.support_ticket_id))
            if ticket is None or ticket.is_deleted:
                raise AppException("DATA_CONFLICT", "退款已有售后关联但工单事实缺失，请人工修复关联", http_status=409)
            return {**_after_sales_dto(db, existing, ticket), "replayed": True, "followUpRequired": True}

        modules = _active_entitlement_modules(db, tid, int(refund.order_id))
        if not modules:
            return {
                "tenantId": str(tid), "refundCaseId": str(case_id), "orderId": str(refund.order_id),
                "followUpRequired": False, "ticketCreated": False, "replayed": False,
                "entitlementChangeApplied": False,
                "message": "当前订单未发现有效模块授权来源，无需生成退款后授权复核工单。",
            }

        title = f"退款后授权复核 · {refund.case_no}"[:200]
        module_text = "、".join(f"{row['moduleKey']}({row['sourceCount']})" for row in modules)
        description = (
            f"商业退款已在外部渠道完成并登记凭据，需要人工复核对应模块授权。"
            f"退款单={refund.case_no}；订单ID={refund.order_id}；外部退款凭据={refund.settlement_ref or '-'}；"
            f"当前有效来源={module_text}；办理说明={reason_text}。"
            "本工单不会自动停权，必须按合同和商业授权事实另行处理。"
        )[:2000]
        ticket = SupportTicket(
            tenant_id=tid, title=title, description=description, severity=level,
            status="OPEN", reporter_name="商业财务工作区",
        )
        db.add(ticket); db.flush()
        audit_log.record_critical_in_session(
            db, "PLATFORM_SUPPORT_TICKET_CREATE", f"support-ticket:{ticket.id}",
            detail={"tenantId": str(tid), "severity": level, "title": title,
                    "actor": str((user or {}).get("userId") or ""), "source": "COMMERCIAL_REFUND"},
            tenant_id=tid, resource_id=str(ticket.id),
        )
        link = CommercialAfterSalesLink(
            tenant_id=tid, refund_case_id=case_id, order_id=int(refund.order_id),
            support_ticket_id=int(ticket.id), link_type="REFUND_ENTITLEMENT_REVIEW",
            module_snapshot_json=modules, settlement_ref_snapshot=refund.settlement_ref,
            linked_at=datetime.utcnow(), linked_by=_actor_id(user),
        )
        db.add(link); db.flush()
        audit_log.record_critical_in_session(
            db, "COMMERCIAL_REFUND_AFTERSALES_LINK", f"commercial-after-sales:{link.id}",
            detail={"tenantId": str(tid), "refundCaseId": str(case_id), "orderId": str(refund.order_id),
                    "supportTicketId": str(ticket.id), "modules": modules, "entitlementChangeApplied": False},
            tenant_id=tid, resource_id=str(link.id),
        )
        db.commit(); db.refresh(link); db.refresh(ticket)
        return {**_after_sales_dto(db, link, ticket), "replayed": False, "followUpRequired": True, "ticketCreated": True}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def list_after_sales(tenant_id: int, *, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    _require_db()
    from app.models import CommercialAfterSalesLink
    from app.models.customer_success import SupportTicket

    tid = _int_id(tenant_id, "tenantId"); page = _int_id(page, "page"); page_size = _int_id(page_size, "pageSize")
    if page_size > 100:
        raise AppException("VALIDATION_ERROR", "pageSize 最大100", http_status=422)
    db = get_sessionmaker()()
    try:
        base = (
            CommercialAfterSalesLink.tenant_id == tid,
            CommercialAfterSalesLink.is_deleted.is_(False),
        )
        total = int(db.scalar(select(func.count(CommercialAfterSalesLink.id)).where(*base)) or 0)
        pairs = db.execute(select(CommercialAfterSalesLink, SupportTicket).join(
            SupportTicket,
            (SupportTicket.id == CommercialAfterSalesLink.support_ticket_id)
            & (SupportTicket.tenant_id == CommercialAfterSalesLink.tenant_id),
        ).where(
            *base, SupportTicket.is_deleted.is_(False),
        ).order_by(CommercialAfterSalesLink.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        now = datetime.utcnow()
        return {"items": [_after_sales_dto(db, link, ticket, now=now) for link, ticket in pairs],
                "total": total, "page": page, "pageSize": page_size, "slaPolicy": _sla_policy(db, tid)}
    finally:
        db.close()


def _verify_cost_refs(db, tenant_id: int, *, support_ticket_id: int | None, refund_case_id: int | None,
                      order_id: int | None) -> None:
    from app.models import CommercialRefundCase, PlatformOrder
    from app.models.customer_success import SupportTicket

    if support_ticket_id is not None:
        row = db.scalars(select(SupportTicket.id).where(
            SupportTicket.id == support_ticket_id, SupportTicket.tenant_id == tenant_id,
            SupportTicket.is_deleted.is_(False),
        )).first()
        if row is None: raise AppException("DATA_NOT_FOUND", "supportTicketId 不属于该学校", http_status=404)
    if refund_case_id is not None:
        row = db.scalars(select(CommercialRefundCase.id).where(
            CommercialRefundCase.id == refund_case_id, CommercialRefundCase.tenant_id == tenant_id,
            CommercialRefundCase.is_deleted.is_(False),
        )).first()
        if row is None: raise AppException("DATA_NOT_FOUND", "refundCaseId 不属于该学校", http_status=404)
    if order_id is not None:
        row = db.scalars(select(PlatformOrder.id).where(
            PlatformOrder.id == order_id, PlatformOrder.tenant_id == tenant_id,
            PlatformOrder.is_deleted.is_(False),
        )).first()
        if row is None: raise AppException("DATA_NOT_FOUND", "orderId 不属于该学校", http_status=404)


def _cost_dto(row) -> dict[str, Any]:
    return {
        "costId": str(row.id), "tenantId": str(row.tenant_id), "costType": row.cost_type,
        "amount": format(Decimal(str(row.amount)), ".2f"), "currency": row.currency,
        "occurredAt": row.occurred_at.isoformat(timespec="seconds"),
        "supportTicketId": str(row.support_ticket_id) if row.support_ticket_id else None,
        "refundCaseId": str(row.refund_case_id) if row.refund_case_id else None,
        "orderId": str(row.order_id) if row.order_id else None,
        "externalRef": row.external_ref, "note": row.note,
        "actualFactOnly": True, "currencyConverted": False,
    }


def record_service_cost(user: dict | None, tenant_id: int, body: dict, *, idempotency_key: str) -> dict[str, Any]:
    _require_db()
    from app.models import CommercialServiceCostRecord
    from app.services import audit_log

    tid = _int_id(tenant_id, "tenantId")
    cost_type = str(body.get("costType") or "").strip().upper()
    if cost_type not in _COST_TYPES:
        raise AppException("VALIDATION_ERROR", f"costType 必须是 {sorted(_COST_TYPES)} 之一", http_status=422)
    amount = _amount(body.get("amount")); currency = _currency(body.get("currency"))
    occurred_at = _utc_naive(body.get("occurredAt"))
    ticket_id = _optional_id(body.get("supportTicketId"), "supportTicketId")
    refund_id = _optional_id(body.get("refundCaseId"), "refundCaseId")
    order_id = _optional_id(body.get("orderId"), "orderId")
    if not any((ticket_id, refund_id, order_id)):
        raise AppException("VALIDATION_ERROR", "实际成本必须关联工单、退款单或订单至少一个对象", http_status=422)
    external_ref = _text(body.get("externalRef"), "externalRef", maximum=160) or None
    note = _text(body.get("note"), "note", maximum=500) or None
    key_hash = _request_hash(tid, idempotency_key)
    payload = {
        "tenantId": str(tid), "costType": cost_type, "amount": format(amount, ".2f"), "currency": currency,
        "occurredAt": occurred_at.isoformat(timespec="seconds"), "supportTicketId": ticket_id,
        "refundCaseId": refund_id, "orderId": order_id, "externalRef": external_ref, "note": note,
    }
    payload_hash = _hash(payload)
    db = get_sessionmaker()()
    try:
        existing = db.scalars(select(CommercialServiceCostRecord).where(
            CommercialServiceCostRecord.tenant_id == tid,
            CommercialServiceCostRecord.request_key_hash == key_hash,
            CommercialServiceCostRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if existing is not None:
            if existing.request_payload_hash != payload_hash:
                raise AppException("DATA_CONFLICT", "同一幂等键对应不同成本事实，已拒绝", http_status=409)
            return {**_cost_dto(existing), "replayed": True}
        _verify_cost_refs(db, tid, support_ticket_id=ticket_id, refund_case_id=refund_id, order_id=order_id)
        row = CommercialServiceCostRecord(
            tenant_id=tid, request_key_hash=key_hash, request_payload_hash=payload_hash,
            cost_type=cost_type, amount=amount, currency=currency, occurred_at=occurred_at,
            support_ticket_id=ticket_id, refund_case_id=refund_id, order_id=order_id,
            external_ref=external_ref, note=note, recorded_by=_actor_id(user),
        )
        db.add(row); db.flush()
        audit_log.record_critical_in_session(
            db, "COMMERCIAL_SERVICE_COST_RECORD", f"commercial-service-cost:{row.id}",
            detail={**payload, "currencyConverted": False}, tenant_id=tid, resource_id=str(row.id),
        )
        db.commit(); db.refresh(row)
        return {**_cost_dto(row), "replayed": False}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def list_service_costs(tenant_id: int, *, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    _require_db()
    from app.models import CommercialServiceCostRecord

    tid = _int_id(tenant_id, "tenantId"); page = _int_id(page, "page"); page_size = _int_id(page_size, "pageSize")
    if page_size > 100: raise AppException("VALIDATION_ERROR", "pageSize 最大100", http_status=422)
    db = get_sessionmaker()()
    try:
        base = (CommercialServiceCostRecord.tenant_id == tid, CommercialServiceCostRecord.is_deleted.is_(False))
        total = int(db.scalar(select(func.count(CommercialServiceCostRecord.id)).where(*base)) or 0)
        rows = list(db.scalars(select(CommercialServiceCostRecord).where(*base).order_by(
            CommercialServiceCostRecord.occurred_at.desc(), CommercialServiceCostRecord.id.desc(),
        ).offset((page - 1) * page_size).limit(page_size)).all())
        sums = db.execute(select(
            CommercialServiceCostRecord.currency, CommercialServiceCostRecord.cost_type,
            func.sum(CommercialServiceCostRecord.amount), func.count(CommercialServiceCostRecord.id),
        ).where(*base).group_by(
            CommercialServiceCostRecord.currency, CommercialServiceCostRecord.cost_type,
        ).order_by(CommercialServiceCostRecord.currency, CommercialServiceCostRecord.cost_type)).all()
        summary: dict[str, list[dict[str, Any]]] = {}
        for currency, cost_type, amount, count in sums:
            summary.setdefault(str(currency), []).append({
                "costType": str(cost_type), "amount": format(Decimal(str(amount or 0)), ".2f"),
                "count": int(count or 0),
            })
        return {"items": [_cost_dto(row) for row in rows], "total": total, "page": page, "pageSize": page_size,
                "summaryByCurrency": summary, "currencyConverted": False}
    finally:
        db.close()


def operations_overview(tenant_id: int) -> dict[str, Any]:
    """Read-only continuous-governance projection from existing operational truths."""
    _require_db()
    from app.models import CommercialAfterSalesLink, CommercialOrderItem, CommercialRefundCase, PlatformConfig, TenantModuleSubscriptionSource
    from app.models.customer_success import RenewalTask, SupportTicket, TrainingRecord

    tid = _int_id(tenant_id, "tenantId")
    db = get_sessionmaker()()
    try:
        pending_refund_reviews = int(db.scalar(select(func.count(func.distinct(CommercialRefundCase.id))).select_from(
            CommercialRefundCase
        ).join(
            CommercialOrderItem,
            (CommercialOrderItem.order_id == CommercialRefundCase.order_id)
            & (CommercialOrderItem.tenant_id == CommercialRefundCase.tenant_id),
        ).join(
            TenantModuleSubscriptionSource,
            (TenantModuleSubscriptionSource.order_item_id == CommercialOrderItem.id)
            & (TenantModuleSubscriptionSource.tenant_id == CommercialOrderItem.tenant_id),
        ).outerjoin(
            CommercialAfterSalesLink,
            (CommercialAfterSalesLink.refund_case_id == CommercialRefundCase.id)
            & (CommercialAfterSalesLink.tenant_id == CommercialRefundCase.tenant_id)
            & (CommercialAfterSalesLink.is_deleted.is_(False)),
        ).where(
            CommercialRefundCase.tenant_id == tid,
            CommercialRefundCase.status == "SETTLED",
            CommercialRefundCase.is_deleted.is_(False),
            CommercialOrderItem.is_deleted.is_(False),
            TenantModuleSubscriptionSource.is_deleted.is_(False),
            TenantModuleSubscriptionSource.status.in_(_ACTIVE_SOURCE_STATES),
            CommercialAfterSalesLink.id.is_(None),
        )) or 0)
        open_after_sales = int(db.scalar(select(func.count(SupportTicket.id)).select_from(SupportTicket).join(
            CommercialAfterSalesLink,
            (CommercialAfterSalesLink.support_ticket_id == SupportTicket.id)
            & (CommercialAfterSalesLink.tenant_id == SupportTicket.tenant_id),
        ).where(
            SupportTicket.tenant_id == tid, SupportTicket.status.in_(("OPEN", "IN_PROGRESS")),
            SupportTicket.is_deleted.is_(False), CommercialAfterSalesLink.is_deleted.is_(False),
        )) or 0)
        scheduled_training = int(db.scalar(select(func.count(TrainingRecord.id)).where(
            TrainingRecord.tenant_id == tid, TrainingRecord.status == "SCHEDULED", TrainingRecord.is_deleted.is_(False),
        )) or 0)
        open_renewals = int(db.scalar(select(func.count(RenewalTask.id)).where(
            RenewalTask.tenant_id == tid, RenewalTask.status.in_(("PENDING", "CONTACTED", "COMMITTED")),
            RenewalTask.is_deleted.is_(False),
        )) or 0)
        delivery_acceptances = int(db.scalar(select(func.count(PlatformConfig.id)).where(
            PlatformConfig.tenant_id == tid, PlatformConfig.config_type == "MODULE_DELIVERY_ACCEPTANCE",
            PlatformConfig.enabled.is_(True), PlatformConfig.status == "ACTIVE", PlatformConfig.is_deleted.is_(False),
        )) or 0)
        policy = _sla_policy(db, tid)
        return {
            "tenantId": str(tid), "pendingRefundEntitlementReviews": pending_refund_reviews,
            "openRefundAfterSalesTickets": open_after_sales, "scheduledTrainings": scheduled_training,
            "openRenewalTasks": open_renewals, "moduleDeliveryAcceptanceFacts": delivery_acceptances,
            "slaPolicy": policy, "entitlementAutoMutation": False,
            "costCurrencyConversion": False,
        }
    finally:
        db.close()
