"""M8 commercial finance controls: receivable projection, manual refunds and invoices.

PlatformOrder remains the sale/payment authority. This service never calls a bank,
payment gateway or tax-invoice provider, never marks an order paid/refunded, and never
changes module entitlements. Refund SETTLED and invoice ISSUED mean an authorized
platform operator recorded externally completed evidence after server-side capacity
checks and critical audit in the same MySQL transaction.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import json
from typing import Any

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker
from app.services.commercial_catalog_contract import ContractError, money

_REFUND_ACTIVE = ("APPROVED", "SETTLED")
_INVOICE_ACTIVE = ("REQUESTED", "ISSUED")


def _require_db() -> None:
    if not db_enabled():
        raise AppException("SERVER_ERROR", "商业财务工作区需要数据库", http_status=503)


def _tid(value) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        result = int(value)
        if result <= 0:
            raise ValueError
        return result
    except (TypeError, ValueError, OverflowError):
        raise AppException("VALIDATION_ERROR", "tenantId 无效", http_status=422) from None


def _positive_id(value, field: str) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        result = int(value)
        if result <= 0:
            raise ValueError
        return result
    except (TypeError, ValueError, OverflowError):
        raise AppException("VALIDATION_ERROR", f"{field} 无效", http_status=422) from None


def _actor_id(value) -> int | None:
    try:
        if isinstance(value, bool):
            return None
        result = int(value)
        return result if result > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _amount(value, field: str = "amount") -> Decimal:
    try:
        result = money(value, field)
    except ContractError as exc:
        raise AppException("VALIDATION_ERROR", str(exc), http_status=422) from exc
    if result <= Decimal("0.00"):
        raise AppException("VALIDATION_ERROR", f"{field} 必须大于0", http_status=422)
    return result


def _currency(value) -> str:
    text = str(value or "").strip().upper()
    if len(text) != 3 or not text.isalpha() or not text.isascii():
        raise AppException("VALIDATION_ERROR", "currency 必须是3位字母币种代码", http_status=422)
    return text


def _reason(value, field: str = "reason", minimum: int = 10) -> str:
    text = str(value or "").strip()
    if not minimum <= len(text) <= 500:
        raise AppException("VALIDATION_ERROR", f"{field} 长度必须为{minimum}~500字符", http_status=422)
    return text


def _stable_hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _command_key(kind: str, tenant_id: int, idempotency_key: str) -> tuple[str, str]:
    key = str(idempotency_key or "").strip()
    if not 8 <= len(key) <= 200:
        raise AppException("VALIDATION_ERROR", "Idempotency-Key 长度必须为8~200", http_status=422)
    digest = hashlib.sha256(f"{kind}:{tenant_id}:{key}".encode("utf-8")).hexdigest()
    prefix = "RF" if kind == "refund" else "IV"
    return digest, f"{prefix}-{datetime.utcnow():%Y%m%d}-{digest[:18].upper()}"


def _order(db, tenant_id: int, order_id: int, *, lock: bool = False):
    from app.models import PlatformOrder

    query = select(PlatformOrder).where(
        PlatformOrder.id == int(order_id),
        PlatformOrder.tenant_id == int(tenant_id),
        PlatformOrder.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalars(query).first()
    if row is None:
        raise AppException("DATA_NOT_FOUND", "订单不存在或不属于该学校", http_status=404)
    return row


def _order_currency(db, tenant_id: int, order_id: int) -> str | None:
    from app.models import CommercialOrderItem

    values = [str(value).upper() for value in db.scalars(select(CommercialOrderItem.currency).where(
        CommercialOrderItem.tenant_id == int(tenant_id),
        CommercialOrderItem.order_id == int(order_id),
        CommercialOrderItem.currency.is_not(None),
        CommercialOrderItem.is_deleted.is_(False),
    ).distinct()).all() if value]
    if len(set(values)) > 1:
        raise AppException("DATA_CONFLICT", "订单分项存在多个币种，财务办理已停止", http_status=409)
    return values[0] if values else None


def _validate_order_currency(db, order, requested: str) -> str:
    expected = _order_currency(db, int(order.tenant_id), int(order.id))
    if expected and expected != requested:
        raise AppException(
            "DATA_CONFLICT", "财务办理币种与订单冻结分项不一致",
            details={"orderCurrency": expected, "requestedCurrency": requested}, http_status=409,
        )
    return expected or requested


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _case_totals(db, tenant_id: int, order_id: int, *, exclude_refund_id: int | None = None,
                 exclude_invoice_id: int | None = None) -> dict[str, Decimal]:
    from app.models import CommercialInvoiceCase, CommercialRefundCase

    refund_query = select(CommercialRefundCase.status, func.sum(CommercialRefundCase.amount)).where(
        CommercialRefundCase.tenant_id == int(tenant_id),
        CommercialRefundCase.order_id == int(order_id),
        CommercialRefundCase.is_deleted.is_(False),
    )
    if exclude_refund_id:
        refund_query = refund_query.where(CommercialRefundCase.id != int(exclude_refund_id))
    refund_rows = db.execute(refund_query.group_by(CommercialRefundCase.status)).all()

    invoice_query = select(CommercialInvoiceCase.status, func.sum(CommercialInvoiceCase.amount)).where(
        CommercialInvoiceCase.tenant_id == int(tenant_id),
        CommercialInvoiceCase.order_id == int(order_id),
        CommercialInvoiceCase.is_deleted.is_(False),
    )
    if exclude_invoice_id:
        invoice_query = invoice_query.where(CommercialInvoiceCase.id != int(exclude_invoice_id))
    invoice_rows = db.execute(invoice_query.group_by(CommercialInvoiceCase.status)).all()

    refunds = {str(status): _decimal(total) for status, total in refund_rows}
    invoices = {str(status): _decimal(total) for status, total in invoice_rows}
    return {
        "refundRequested": refunds.get("REQUESTED", Decimal("0.00")),
        "refundApproved": refunds.get("APPROVED", Decimal("0.00")),
        "refundSettled": refunds.get("SETTLED", Decimal("0.00")),
        "invoiceRequested": invoices.get("REQUESTED", Decimal("0.00")),
        "invoiceIssued": invoices.get("ISSUED", Decimal("0.00")),
    }


def _entitlement_impact(db, tenant_id: int, order_id: int) -> dict[str, Any]:
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
        TenantModuleSubscriptionSource.status.in_(("ACTIVE", "SCHEDULED", "CANCEL_SCHEDULED")),
    ).group_by(TenantModuleSubscriptionSource.module_key)).all()
    modules = [{"moduleKey": str(module), "sourceCount": int(count or 0)} for module, count in rows]
    return {
        "activeEntitlementSourceCount": sum(row["sourceCount"] for row in modules),
        "modules": modules,
        "entitlementChangeApplied": False,
        "followUpRequired": bool(modules),
    }


def _finance_snapshot(db, order, totals: dict[str, Decimal] | None = None) -> dict[str, Any]:
    sums = totals or _case_totals(db, int(order.tenant_id), int(order.id))
    amount = _decimal(order.amount)
    paid = _decimal(order.paid_amount)
    settled = sums["refundSettled"]
    approved = sums["refundApproved"]
    issued = sums["invoiceIssued"]
    requested_invoice = sums["invoiceRequested"]
    outstanding = max(amount - paid, Decimal("0.00"))
    finance_capacity = max(paid - settled - approved - issued - requested_invoice, Decimal("0.00"))
    return {
        "orderId": str(order.id), "tenantId": str(order.tenant_id), "orderNo": order.order_no,
        "orderStatus": order.status, "orderType": order.order_type,
        "amount": format(amount, ".2f"), "paidAmount": format(paid, ".2f"),
        "outstandingAmount": format(outstanding, ".2f"),
        "refundRequestedAmount": format(sums["refundRequested"], ".2f"),
        "refundApprovedAmount": format(approved, ".2f"),
        "refundSettledAmount": format(settled, ".2f"),
        "invoiceRequestedAmount": format(requested_invoice, ".2f"),
        "invoiceIssuedAmount": format(issued, ".2f"),
        "availableFinanceCapacity": format(finance_capacity, ".2f"),
        "netCashAfterSettledRefunds": format(max(paid - settled, Decimal("0.00")), ".2f"),
        "paymentAuthority": "PLATFORM_ORDER",
        "receivableDerivedNotDuplicated": True,
    }


def _aggregate_maps(db, tenant_id: int, order_ids: list[int]):
    from app.models import CommercialInvoiceCase, CommercialRefundCase

    if not order_ids:
        return {}, {}
    refund_rows = db.execute(select(
        CommercialRefundCase.order_id, CommercialRefundCase.status, func.sum(CommercialRefundCase.amount),
    ).where(
        CommercialRefundCase.tenant_id == int(tenant_id),
        CommercialRefundCase.order_id.in_(order_ids),
        CommercialRefundCase.is_deleted.is_(False),
    ).group_by(CommercialRefundCase.order_id, CommercialRefundCase.status)).all()
    invoice_rows = db.execute(select(
        CommercialInvoiceCase.order_id, CommercialInvoiceCase.status, func.sum(CommercialInvoiceCase.amount),
    ).where(
        CommercialInvoiceCase.tenant_id == int(tenant_id),
        CommercialInvoiceCase.order_id.in_(order_ids),
        CommercialInvoiceCase.is_deleted.is_(False),
    ).group_by(CommercialInvoiceCase.order_id, CommercialInvoiceCase.status)).all()
    refund_map: dict[int, dict[str, Decimal]] = {}
    invoice_map: dict[int, dict[str, Decimal]] = {}
    for order_id, status, total in refund_rows:
        refund_map.setdefault(int(order_id), {})[str(status)] = _decimal(total)
    for order_id, status, total in invoice_rows:
        invoice_map.setdefault(int(order_id), {})[str(status)] = _decimal(total)
    return refund_map, invoice_map


def list_finance_orders(tenant_id, *, page=1, page_size=20) -> dict[str, Any]:
    _require_db()
    from app.models import PlatformOrder

    tid = _tid(tenant_id)
    page = _positive_id(page, "page"); page_size = _positive_id(page_size, "pageSize")
    if page_size > 100:
        raise AppException("VALIDATION_ERROR", "pageSize 最大100", http_status=422)
    with get_sessionmaker()() as db:
        total = int(db.scalar(select(func.count(PlatformOrder.id)).where(
            PlatformOrder.tenant_id == tid, PlatformOrder.is_deleted.is_(False),
        )) or 0)
        orders = list(db.scalars(select(PlatformOrder).where(
            PlatformOrder.tenant_id == tid, PlatformOrder.is_deleted.is_(False),
        ).order_by(PlatformOrder.id.desc()).offset((page - 1) * page_size).limit(page_size)).all())
        refund_map, invoice_map = _aggregate_maps(db, tid, [int(row.id) for row in orders])
        items = []
        for row in orders:
            refunds = refund_map.get(int(row.id), {})
            invoices = invoice_map.get(int(row.id), {})
            totals = {
                "refundRequested": refunds.get("REQUESTED", Decimal("0.00")),
                "refundApproved": refunds.get("APPROVED", Decimal("0.00")),
                "refundSettled": refunds.get("SETTLED", Decimal("0.00")),
                "invoiceRequested": invoices.get("REQUESTED", Decimal("0.00")),
                "invoiceIssued": invoices.get("ISSUED", Decimal("0.00")),
            }
            items.append(_finance_snapshot(db, row, totals))
        return {"items": items, "total": total, "page": page, "pageSize": page_size}


def _refund_dict(row) -> dict[str, Any]:
    return {
        "caseId": str(row.id), "tenantId": str(row.tenant_id), "orderId": str(row.order_id),
        "caseNo": row.case_no, "amount": format(_decimal(row.amount), ".2f"), "currency": row.currency,
        "status": row.status, "reason": row.reason, "version": int(row.version or 0),
        "orderPaidAmountSnapshot": format(_decimal(row.order_paid_amount_snapshot), ".2f"),
        "requestedAt": row.requested_at.isoformat(timespec="seconds") if row.requested_at else None,
        "approvedAt": row.approved_at.isoformat(timespec="seconds") if row.approved_at else None,
        "approvalNote": row.approval_note, "rejectionReason": row.rejection_reason,
        "settlementRef": row.settlement_ref,
        "settledAt": row.settled_at.isoformat(timespec="seconds") if row.settled_at else None,
        "externalRefundExecutedBySystem": False,
    }


def _invoice_dict(row) -> dict[str, Any]:
    return {
        "invoiceCaseId": str(row.id), "tenantId": str(row.tenant_id), "orderId": str(row.order_id),
        "requestNo": row.request_no, "amount": format(_decimal(row.amount), ".2f"), "currency": row.currency,
        "invoiceTitle": row.invoice_title, "status": row.status, "version": int(row.version or 0),
        "requestedAt": row.requested_at.isoformat(timespec="seconds") if row.requested_at else None,
        "issuedAt": row.issued_at.isoformat(timespec="seconds") if row.issued_at else None,
        "externalInvoiceRef": row.external_invoice_ref,
        "invoiceFileId": str(row.invoice_file_id) if row.invoice_file_id else None,
        "voidReason": row.void_reason,
        "externalInvoiceIssuedBySystem": False,
    }


def list_refunds(tenant_id, *, status="", page=1, page_size=20) -> dict[str, Any]:
    _require_db()
    from app.models import CommercialRefundCase

    tid = _tid(tenant_id); page = _positive_id(page, "page"); page_size = _positive_id(page_size, "pageSize")
    if page_size > 100: raise AppException("VALIDATION_ERROR", "pageSize 最大100", http_status=422)
    filters = [CommercialRefundCase.tenant_id == tid, CommercialRefundCase.is_deleted.is_(False)]
    if status:
        value = str(status).upper()
        if value not in {"REQUESTED", "APPROVED", "REJECTED", "SETTLED"}:
            raise AppException("VALIDATION_ERROR", "退款状态无效", http_status=422)
        filters.append(CommercialRefundCase.status == value)
    with get_sessionmaker()() as db:
        total = int(db.scalar(select(func.count(CommercialRefundCase.id)).where(*filters)) or 0)
        rows = db.scalars(select(CommercialRefundCase).where(*filters).order_by(CommercialRefundCase.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        return {"items": [_refund_dict(row) for row in rows], "total": total, "page": page, "pageSize": page_size}


def list_invoices(tenant_id, *, status="", page=1, page_size=20) -> dict[str, Any]:
    _require_db()
    from app.models import CommercialInvoiceCase

    tid = _tid(tenant_id); page = _positive_id(page, "page"); page_size = _positive_id(page_size, "pageSize")
    if page_size > 100: raise AppException("VALIDATION_ERROR", "pageSize 最大100", http_status=422)
    filters = [CommercialInvoiceCase.tenant_id == tid, CommercialInvoiceCase.is_deleted.is_(False)]
    if status:
        value = str(status).upper()
        if value not in {"REQUESTED", "ISSUED", "VOIDED"}:
            raise AppException("VALIDATION_ERROR", "发票状态无效", http_status=422)
        filters.append(CommercialInvoiceCase.status == value)
    with get_sessionmaker()() as db:
        total = int(db.scalar(select(func.count(CommercialInvoiceCase.id)).where(*filters)) or 0)
        rows = db.scalars(select(CommercialInvoiceCase).where(*filters).order_by(CommercialInvoiceCase.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        return {"items": [_invoice_dict(row) for row in rows], "total": total, "page": page, "pageSize": page_size}


def request_refund(body: dict, *, idempotency_key: str, actor_id=None) -> dict[str, Any]:
    _require_db()
    from app.models import CommercialRefundCase
    from app.services import audit_log

    if not isinstance(body, dict) or set(body) != {"tenantId", "orderId", "amount", "currency", "reason"}:
        raise AppException("VALIDATION_ERROR", "退款申请参数不完整或包含未知字段", http_status=422)
    tid = _tid(body["tenantId"]); order_id = _positive_id(body["orderId"], "orderId")
    requested_amount = _amount(body["amount"]); requested_currency = _currency(body["currency"])
    reason = _reason(body["reason"]); key_hash, case_no = _command_key("refund", tid, idempotency_key)
    payload_hash = _stable_hash({"tenantId": str(tid), "orderId": str(order_id), "amount": format(requested_amount, ".2f"), "currency": requested_currency, "reason": reason})
    db = get_sessionmaker()()
    try:
        order = _order(db, tid, order_id, lock=True)
        existing = db.scalars(select(CommercialRefundCase).where(
            CommercialRefundCase.request_key_hash == key_hash,
            CommercialRefundCase.is_deleted.is_(False),
        ).with_for_update()).first()
        if existing is not None:
            if existing.request_payload_hash != payload_hash:
                raise AppException("DATA_CONFLICT", "同一退款命令键已用于不同申请", http_status=409)
            return {**_refund_dict(existing), "replayed": True}
        currency = _validate_order_currency(db, order, requested_currency)
        paid = _decimal(order.paid_amount)
        if paid <= 0 or str(order.status).lower() not in {"paid", "refunded"}:
            raise AppException("DATA_CONFLICT", "订单尚无可核验已收款，不能发起退款", http_status=409)
        totals = _case_totals(db, tid, order_id)
        capacity = max(paid - totals["refundSettled"] - totals["refundApproved"] - totals["invoiceIssued"] - totals["invoiceRequested"], Decimal("0.00"))
        if requested_amount > capacity:
            raise AppException("DATA_CONFLICT", "退款金额超过当前可办理余额；请先处理已批准退款或发票", details={"availableAmount": format(capacity, ".2f")}, http_status=409)
        row = CommercialRefundCase(
            tenant_id=tid, order_id=order_id, case_no=case_no,
            request_key_hash=key_hash, request_payload_hash=payload_hash,
            amount=requested_amount, currency=currency, order_paid_amount_snapshot=paid,
            reason=reason, status="REQUESTED", requested_by=_actor_id(actor_id), requested_at=datetime.utcnow(),
        )
        db.add(row); db.flush()
        audit_log.record_critical_in_session(db, "COMMERCIAL_REFUND_REQUEST", f"commercial-refund:{row.id}",
            detail={"tenantId": str(tid), "orderId": str(order_id), "caseNo": case_no, "amount": format(requested_amount, ".2f"), "currency": currency, "externalRefundExecutedBySystem": False},
            tenant_id=tid, resource_id=str(row.id))
        db.commit(); return {**_refund_dict(row), "replayed": False}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def approve_refund(tenant_id, case_id, *, expected_version: int, note: str, actor_id=None) -> dict[str, Any]:
    _require_db()
    from app.models import CommercialRefundCase
    from app.services import audit_log

    tid = _tid(tenant_id); cid = _positive_id(case_id, "caseId"); approval_note = _reason(note, "note", 5)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(CommercialRefundCase).where(
            CommercialRefundCase.id == cid, CommercialRefundCase.tenant_id == tid,
            CommercialRefundCase.is_deleted.is_(False),
        ).with_for_update()).first()
        if row is None: raise AppException("DATA_NOT_FOUND", "退款申请不存在", http_status=404)
        if int(row.version or 0) != int(expected_version): raise AppException("DATA_CONFLICT", "退款申请已变化，请刷新", http_status=409)
        if row.status != "REQUESTED": raise AppException("DATA_CONFLICT", f"当前退款状态 {row.status} 不能批准", http_status=409)
        order = _order(db, tid, int(row.order_id), lock=True); paid = _decimal(order.paid_amount)
        totals = _case_totals(db, tid, int(row.order_id), exclude_refund_id=cid)
        capacity = max(paid - totals["refundSettled"] - totals["refundApproved"] - totals["invoiceIssued"] - totals["invoiceRequested"], Decimal("0.00"))
        if _decimal(row.amount) > capacity:
            raise AppException("DATA_CONFLICT", "退款批准额度已被其他退款/发票占用，请重新核对", details={"availableAmount": format(capacity, ".2f")}, http_status=409)
        now = datetime.utcnow(); row.status = "APPROVED"; row.approved_by = _actor_id(actor_id); row.approved_at = now; row.approval_note = approval_note; row.version = int(row.version or 0) + 1
        audit_log.record_critical_in_session(db, "COMMERCIAL_REFUND_APPROVE", f"commercial-refund:{row.id}", detail={"tenantId": str(tid), "orderId": str(row.order_id), "amount": format(_decimal(row.amount), ".2f"), "externalRefundExecutedBySystem": False}, tenant_id=tid, resource_id=str(row.id))
        db.commit(); result = _refund_dict(row); result["entitlementImpact"] = _entitlement_impact(db, tid, int(row.order_id)); return result
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def reject_refund(tenant_id, case_id, *, expected_version: int, reason: str, actor_id=None) -> dict[str, Any]:
    _require_db()
    from app.models import CommercialRefundCase
    from app.services import audit_log

    tid = _tid(tenant_id); cid = _positive_id(case_id, "caseId"); rejection = _reason(reason)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(CommercialRefundCase).where(CommercialRefundCase.id == cid, CommercialRefundCase.tenant_id == tid, CommercialRefundCase.is_deleted.is_(False)).with_for_update()).first()
        if row is None: raise AppException("DATA_NOT_FOUND", "退款申请不存在", http_status=404)
        if int(row.version or 0) != int(expected_version): raise AppException("DATA_CONFLICT", "退款申请已变化，请刷新", http_status=409)
        if row.status != "REQUESTED": raise AppException("DATA_CONFLICT", f"当前退款状态 {row.status} 不能驳回", http_status=409)
        row.status = "REJECTED"; row.rejected_by = _actor_id(actor_id); row.rejected_at = datetime.utcnow(); row.rejection_reason = rejection; row.version = int(row.version or 0) + 1
        audit_log.record_critical_in_session(db, "COMMERCIAL_REFUND_REJECT", f"commercial-refund:{row.id}", detail={"tenantId": str(tid), "orderId": str(row.order_id), "reason": rejection}, tenant_id=tid, resource_id=str(row.id))
        db.commit(); return _refund_dict(row)
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def settle_refund(tenant_id, case_id, *, expected_version: int, settlement_ref: str, actor_id=None) -> dict[str, Any]:
    _require_db()
    from app.models import CommercialRefundCase
    from app.services import audit_log

    tid = _tid(tenant_id); cid = _positive_id(case_id, "caseId"); ref = str(settlement_ref or "").strip()
    if not 6 <= len(ref) <= 160: raise AppException("VALIDATION_ERROR", "外部退款凭据长度必须为6~160字符", http_status=422)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(CommercialRefundCase).where(CommercialRefundCase.id == cid, CommercialRefundCase.tenant_id == tid, CommercialRefundCase.is_deleted.is_(False)).with_for_update()).first()
        if row is None: raise AppException("DATA_NOT_FOUND", "退款申请不存在", http_status=404)
        if int(row.version or 0) != int(expected_version): raise AppException("DATA_CONFLICT", "退款申请已变化，请刷新", http_status=409)
        if row.status != "APPROVED": raise AppException("DATA_CONFLICT", "只有已批准退款才能登记外部结算", http_status=409)
        duplicate = db.scalars(select(CommercialRefundCase).where(
            CommercialRefundCase.tenant_id == tid, CommercialRefundCase.settlement_ref == ref,
            CommercialRefundCase.id != cid, CommercialRefundCase.is_deleted.is_(False),
        )).first()
        if duplicate is not None: raise AppException("DATA_CONFLICT", "该外部退款凭据已被其他退款记录使用", http_status=409)
        order = _order(db, tid, int(row.order_id), lock=True); paid = _decimal(order.paid_amount)
        totals = _case_totals(db, tid, int(row.order_id), exclude_refund_id=cid)
        if totals["refundSettled"] + totals["refundApproved"] + _decimal(row.amount) + totals["invoiceIssued"] + totals["invoiceRequested"] > paid:
            raise AppException("DATA_CONFLICT", "订单财务事实已变化，当前退款结算会超过已收款可用范围", http_status=409)
        row.status = "SETTLED"; row.settled_by = _actor_id(actor_id); row.settled_at = datetime.utcnow(); row.settlement_ref = ref; row.version = int(row.version or 0) + 1
        impact = _entitlement_impact(db, tid, int(row.order_id))
        audit_log.record_critical_in_session(db, "COMMERCIAL_REFUND_SETTLE", f"commercial-refund:{row.id}", detail={"tenantId": str(tid), "orderId": str(row.order_id), "settlementRef": ref, "amount": format(_decimal(row.amount), ".2f"), "orderStatusChanged": False, "entitlementChangeApplied": False, "activeEntitlementSourceCount": impact["activeEntitlementSourceCount"]}, tenant_id=tid, resource_id=str(row.id))
        db.commit(); result = _refund_dict(row); result["orderStatusChanged"] = False; result["entitlementImpact"] = impact; return result
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def request_invoice(body: dict, *, idempotency_key: str, actor_id=None) -> dict[str, Any]:
    _require_db()
    from app.models import CommercialInvoiceCase
    from app.services import audit_log

    if not isinstance(body, dict) or set(body) != {"tenantId", "orderId", "amount", "currency", "invoiceTitle"}:
        raise AppException("VALIDATION_ERROR", "发票申请参数不完整或包含未知字段", http_status=422)
    tid = _tid(body["tenantId"]); order_id = _positive_id(body["orderId"], "orderId")
    requested_amount = _amount(body["amount"]); requested_currency = _currency(body["currency"])
    title = str(body["invoiceTitle"] or "").strip()
    if not 2 <= len(title) <= 200: raise AppException("VALIDATION_ERROR", "发票抬头长度必须为2~200字符", http_status=422)
    key_hash, request_no = _command_key("invoice", tid, idempotency_key)
    payload_hash = _stable_hash({"tenantId": str(tid), "orderId": str(order_id), "amount": format(requested_amount, ".2f"), "currency": requested_currency, "invoiceTitle": title})
    db = get_sessionmaker()()
    try:
        order = _order(db, tid, order_id, lock=True)
        existing = db.scalars(select(CommercialInvoiceCase).where(CommercialInvoiceCase.request_key_hash == key_hash, CommercialInvoiceCase.is_deleted.is_(False)).with_for_update()).first()
        if existing is not None:
            if existing.request_payload_hash != payload_hash: raise AppException("DATA_CONFLICT", "同一发票命令键已用于不同申请", http_status=409)
            return {**_invoice_dict(existing), "replayed": True}
        currency = _validate_order_currency(db, order, requested_currency); paid = _decimal(order.paid_amount)
        if paid <= 0 or str(order.status).lower() not in {"paid", "refunded"}: raise AppException("DATA_CONFLICT", "订单尚无可核验已收款，不能申请发票", http_status=409)
        totals = _case_totals(db, tid, order_id)
        capacity = max(paid - totals["refundSettled"] - totals["refundApproved"] - totals["invoiceIssued"] - totals["invoiceRequested"], Decimal("0.00"))
        if requested_amount > capacity: raise AppException("DATA_CONFLICT", "开票金额超过当前可开票余额；请先处理退款或已有发票", details={"availableAmount": format(capacity, ".2f")}, http_status=409)
        row = CommercialInvoiceCase(tenant_id=tid, order_id=order_id, request_no=request_no, request_key_hash=key_hash, request_payload_hash=payload_hash, amount=requested_amount, currency=currency, invoice_title=title, status="REQUESTED", requested_by=_actor_id(actor_id), requested_at=datetime.utcnow())
        db.add(row); db.flush()
        audit_log.record_critical_in_session(db, "COMMERCIAL_INVOICE_REQUEST", f"commercial-invoice:{row.id}", detail={"tenantId": str(tid), "orderId": str(order_id), "requestNo": request_no, "amount": format(requested_amount, ".2f"), "externalInvoiceIssuedBySystem": False}, tenant_id=tid, resource_id=str(row.id))
        db.commit(); return {**_invoice_dict(row), "replayed": False}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def issue_invoice(tenant_id, invoice_case_id, *, expected_version: int, external_invoice_ref: str,
                  invoice_file_id=None, actor_id=None) -> dict[str, Any]:
    _require_db()
    from app.models import CommercialInvoiceCase
    from app.services import audit_log

    tid = _tid(tenant_id); cid = _positive_id(invoice_case_id, "invoiceCaseId"); ref = str(external_invoice_ref or "").strip()
    if not 6 <= len(ref) <= 160: raise AppException("VALIDATION_ERROR", "外部发票凭据长度必须为6~160字符", http_status=422)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(CommercialInvoiceCase).where(CommercialInvoiceCase.id == cid, CommercialInvoiceCase.tenant_id == tid, CommercialInvoiceCase.is_deleted.is_(False)).with_for_update()).first()
        if row is None: raise AppException("DATA_NOT_FOUND", "发票申请不存在", http_status=404)
        if int(row.version or 0) != int(expected_version): raise AppException("DATA_CONFLICT", "发票申请已变化，请刷新", http_status=409)
        if row.status != "REQUESTED": raise AppException("DATA_CONFLICT", "只有待开票申请才能登记已开票", http_status=409)
        duplicate = db.scalars(select(CommercialInvoiceCase).where(CommercialInvoiceCase.tenant_id == tid, CommercialInvoiceCase.external_invoice_ref == ref, CommercialInvoiceCase.id != cid, CommercialInvoiceCase.is_deleted.is_(False))).first()
        if duplicate is not None: raise AppException("DATA_CONFLICT", "该外部发票凭据已被其他发票记录使用", http_status=409)
        order = _order(db, tid, int(row.order_id), lock=True); paid = _decimal(order.paid_amount)
        totals = _case_totals(db, tid, int(row.order_id), exclude_invoice_id=cid)
        capacity = max(paid - totals["refundSettled"] - totals["refundApproved"] - totals["invoiceIssued"] - totals["invoiceRequested"], Decimal("0.00"))
        if _decimal(row.amount) > capacity: raise AppException("DATA_CONFLICT", "开票前财务事实已变化，申请金额超过当前可开票余额", details={"availableAmount": format(capacity, ".2f")}, http_status=409)
        file_id = None
        if invoice_file_id not in (None, ""):
            from app.models.file import FileObject
            file_id = _positive_id(invoice_file_id, "invoiceFileId")
            file_row = db.scalars(select(FileObject).where(FileObject.id == file_id, FileObject.tenant_id == tid, FileObject.status == "AVAILABLE", FileObject.is_deleted.is_(False))).first()
            if file_row is None: raise AppException("DATA_NOT_FOUND", "发票文件不存在、不可用或不属于该学校", http_status=404)
        row.status = "ISSUED"; row.issued_by = _actor_id(actor_id); row.issued_at = datetime.utcnow(); row.external_invoice_ref = ref; row.invoice_file_id = file_id; row.version = int(row.version or 0) + 1
        audit_log.record_critical_in_session(db, "COMMERCIAL_INVOICE_ISSUE", f"commercial-invoice:{row.id}", detail={"tenantId": str(tid), "orderId": str(row.order_id), "externalInvoiceRef": ref, "invoiceFileId": str(file_id) if file_id else None, "externalInvoiceIssuedBySystem": False}, tenant_id=tid, resource_id=str(row.id))
        db.commit(); return _invoice_dict(row)
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def void_invoice(tenant_id, invoice_case_id, *, expected_version: int, reason: str, actor_id=None) -> dict[str, Any]:
    _require_db()
    from app.models import CommercialInvoiceCase
    from app.services import audit_log

    tid = _tid(tenant_id); cid = _positive_id(invoice_case_id, "invoiceCaseId"); why = _reason(reason, minimum=8)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(CommercialInvoiceCase).where(CommercialInvoiceCase.id == cid, CommercialInvoiceCase.tenant_id == tid, CommercialInvoiceCase.is_deleted.is_(False)).with_for_update()).first()
        if row is None: raise AppException("DATA_NOT_FOUND", "发票记录不存在", http_status=404)
        if int(row.version or 0) != int(expected_version): raise AppException("DATA_CONFLICT", "发票记录已变化，请刷新", http_status=409)
        if row.status != "ISSUED": raise AppException("DATA_CONFLICT", "只有已开票记录才能登记作废", http_status=409)
        row.status = "VOIDED"; row.voided_by = _actor_id(actor_id); row.voided_at = datetime.utcnow(); row.void_reason = why; row.version = int(row.version or 0) + 1
        audit_log.record_critical_in_session(db, "COMMERCIAL_INVOICE_VOID", f"commercial-invoice:{row.id}", detail={"tenantId": str(tid), "orderId": str(row.order_id), "externalInvoiceRef": row.external_invoice_ref, "reason": why, "externalInvoiceVoidExecutedBySystem": False}, tenant_id=tid, resource_id=str(row.id))
        db.commit(); return _invoice_dict(row)
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
