"""M1 itemized commercial order writer.

The existing ``PlatformOrder`` remains the payment/contract header. This service
adds immutable item snapshots and durable idempotency in the same MySQL
transaction. It never marks payment successful and never grants entitlement.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import secrets

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker
from app.services.commercial_catalog_contract import ContractError, compile_order_draft
from app.services.commercial_catalog_service import get_sku_snapshot

_OPERATION = "COMMERCIAL_CREATE_ITEMIZED_ORDER"


def _require_db() -> None:
    if not db_enabled():
        raise AppException("SERVER_ERROR", "商业分项订单需要数据库")


def _clean_body(body: dict) -> tuple[dict, str, str]:
    if not isinstance(body, dict):
        raise AppException("VALIDATION_ERROR", "订单请求必须是对象", http_status=422)
    order_type = str(body.get("orderType") or "NEW").strip().upper()
    if order_type not in {"NEW", "RENEW", "UPGRADE", "ADDON"}:
        raise AppException("VALIDATION_ERROR", "orderType 不支持", http_status=422)
    remark = str(body.get("remark") or "").strip()
    if len(remark) > 500:
        raise AppException("VALIDATION_ERROR", "订单备注不能超过500个字符", http_status=422)
    contract = {key: body.get(key) for key in ("tenantId", "currency", "totalAmount", "items")}
    return contract, order_type, remark


def _fingerprint(contract: dict, order_type: str, remark: str) -> str:
    payload = {"contract": contract, "orderType": order_type, "remark": remark}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _idempotency_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_itemized_order(body: dict, *, idempotency_key: str, actor_id: int | str = "0") -> dict:
    _require_db()
    from app.models import CommercialOrderItem, IdempotencyRecord, PlatformOrder, Tenant
    from app.services import audit_log

    key = str(idempotency_key or "").strip()
    if not 8 <= len(key) <= 200:
        raise AppException("VALIDATION_ERROR", "Idempotency-Key 长度必须为8~200", http_status=422)
    contract, order_type, remark = _clean_body(body)
    db = get_sessionmaker()()
    try:
        try:
            tenant_id = int(contract.get("tenantId") or 0)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "tenantId 格式无效", http_status=422) from exc
        # One stable parent lock serializes first-time idempotency/order creation for
        # this control-plane tenant and avoids racing INSERTs on the idempotency key.
        tenant = db.scalars(select(Tenant).where(
            Tenant.id == tenant_id, Tenant.is_deleted.is_(False),
        ).with_for_update()).first()
        if tenant is None:
            raise AppException("DATA_NOT_FOUND", "租户不存在", http_status=404)

        try:
            draft = compile_order_draft(
                contract,
                resolve_sku=lambda code, revision: get_sku_snapshot(code, revision, db_session=db),
            )
        except ContractError as exc:
            raise AppException("VALIDATION_ERROR", str(exc), http_status=422) from exc
        compiled = draft.as_dict()
        fingerprint = _fingerprint(contract, order_type, remark)
        key_hash = _idempotency_hash(key)
        idem = db.scalars(select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.user_id == str(actor_id),
            IdempotencyRecord.operation == _OPERATION,
            IdempotencyRecord.key_hash == key_hash,
        ).with_for_update()).first()
        if idem is not None:
            if idem.fingerprint != fingerprint:
                raise AppException("DATA_CONFLICT", "同一幂等键不能用于不同订单内容", http_status=409)
            if idem.state == "COMPLETED" and isinstance(idem.result_json, dict):
                return {**dict(idem.result_json), "replayed": True}
            raise AppException("DATA_CONFLICT", "同一订单命令仍在处理中，请稍后核对结果", http_status=409)

        idem = IdempotencyRecord(
            tenant_id=tenant_id,
            user_id=str(actor_id),
            operation=_OPERATION,
            key_hash=key_hash,
            fingerprint=fingerprint,
            state="PROCESSING",
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        db.add(idem)
        now = datetime.utcnow()
        items = compiled["items"]
        starts = [datetime.fromisoformat(item["startAt"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None) for item in items]
        ends = [datetime.fromisoformat(item["endAt"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None) for item in items]
        order = PlatformOrder(
            tenant_id=tenant_id,
            order_no=f"MO{now:%Y%m%d%H%M%S}{secrets.token_hex(4).upper()}",
            order_type=order_type,
            package_code="MODULE_V2",
            amount=Decimal(compiled["totalAmount"]),
            paid_amount=Decimal("0.00"),
            status="unpaid",
            start_at=min(starts),
            end_at=max(ends),
            remark=remark,
            version=1,
            created_by=int(actor_id) if str(actor_id).isdigit() else None,
            updated_by=int(actor_id) if str(actor_id).isdigit() else None,
        )
        db.add(order)
        db.flush()
        for item in items:
            sku = item["skuSnapshot"]
            row = CommercialOrderItem(
                tenant_id=tenant_id,
                order_id=int(order.id),
                line_no=int(item["lineNo"]),
                sku_code=item["skuCode"],
                sku_revision=int(item["skuRevision"]),
                sku_content_hash=item["skuContentHash"],
                module_key=sku.get("moduleKey"),
                module_generation=int(item["requestedGeneration"]),
                quantity=int(item["quantity"]),
                unit_price=Decimal(item["unitPrice"]),
                discount_amount=Decimal(item["discountAmount"]),
                net_amount=Decimal(item["netAmount"]),
                currency=item["currency"],
                service_start_at=datetime.fromisoformat(item["startAt"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None),
                service_end_at=datetime.fromisoformat(item["endAt"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None),
                sku_snapshot_json=sku,
                feature_snapshot_json=dict(sku.get("features") or {}),
                quota_snapshot_json=dict(sku.get("quotas") or {}),
                fulfillment_status="PENDING",
                created_by=order.created_by,
                updated_by=order.updated_by,
            )
            db.add(row)
        db.flush()
        result = {
            "orderId": str(order.id),
            "orderNo": order.order_no,
            "status": order.status,
            "version": int(order.version),
            "itemized": True,
            "itemCount": len(items),
            "totalAmount": compiled["totalAmount"],
            "currency": compiled["currency"],
            "paymentRecorded": False,
            "rightsMaterialized": False,
        }
        audit_log.record_critical_in_session(
            db,
            "COMMERCIAL_ITEMIZED_ORDER_CREATE",
            f"order:{order.order_no}",
            detail={"tenantId": str(tenant_id), "itemCount": len(items), "totalAmount": compiled["totalAmount"], "currency": compiled["currency"]},
            tenant_id=tenant_id,
            resource_id=str(order.id),
        )
        idem.state = "COMPLETED"
        idem.result_json = result
        db.commit()
        return {**result, "replayed": False}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def order_items(order_id: int, *, db_session=None) -> list:
    from app.models import CommercialOrderItem

    def read(db):
        return list(db.scalars(select(CommercialOrderItem).where(
            CommercialOrderItem.order_id == int(order_id),
            CommercialOrderItem.is_deleted.is_(False),
        ).order_by(CommercialOrderItem.line_no)).all())
    if db_session is not None:
        return read(db_session)
    db = get_sessionmaker()()
    try:
        return read(db)
    finally:
        db.close()


def is_native_itemized_order(order_id: int, *, db_session=None) -> bool:
    rows = order_items(order_id, db_session=db_session)
    return bool(rows) and all(row.fulfillment_status != "LEGACY_UNALLOCATED" for row in rows)
