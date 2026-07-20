"""Database-backed Dry-Run payloads with a cross-instance confirmation lease."""
from __future__ import annotations

import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.db.session import db_enabled, get_sessionmaker

DEFAULT_TTL = 24 * 60 * 60
RESULT_TTL = 7 * 24 * 60 * 60
CLAIM_STALE_SECONDS = 5 * 60


def _require_db() -> None:
    if not db_enabled():
        raise AppException("SERVER_ERROR", "共享导入批次需要启用数据库")


def _encode(value):
    if isinstance(value, datetime):
        return {"__import_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__import_type__": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"__import_type__": "time", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"__import_type__": "decimal", "value": str(value)}
    if isinstance(value, dict):
        return {str(k): _encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    return value


def _decode(value):
    if isinstance(value, dict):
        kind = value.get("__import_type__")
        raw = value.get("value")
        if kind == "datetime":
            return datetime.fromisoformat(raw)
        if kind == "date":
            return date.fromisoformat(raw)
        if kind == "time":
            return time.fromisoformat(raw)
        if kind == "decimal":
            return Decimal(raw)
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


def _row(db, tenant_id: int, namespace: str, batch_no: str, *, lock: bool = False):
    from app.models import SharedImportBatch

    stmt = select(SharedImportBatch).where(
        SharedImportBatch.tenant_id == int(tenant_id),
        SharedImportBatch.namespace == namespace,
        SharedImportBatch.batch_no == batch_no,
        SharedImportBatch.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    row = db.scalar(stmt)
    if not row or row.expires_at <= datetime.utcnow() or row.status == "EXPIRED":
        if row and row.status != "EXPIRED":
            row.status = "EXPIRED"
            row.claim_token = None
            row.claim_started_at = None
            db.commit()
        raise not_found("导入批次不存在或已过期，请重新校验")
    return row


def create(tenant_id: int, namespace: str, batch_no: str, status: str, payload: dict,
           *, errors: list | None = None, operator_key: str | None = None) -> None:
    _require_db()
    from app.models import SharedImportBatch

    db = get_sessionmaker()()
    try:
        db.add(SharedImportBatch(
            tenant_id=int(tenant_id), namespace=namespace, batch_no=batch_no,
            operator_key=str(operator_key or "") or None, status=status,
            payload_json=_encode(payload), errors_json=_encode(errors or []),
            expires_at=datetime.utcnow() + timedelta(seconds=DEFAULT_TTL),
        ))
        db.commit()
    finally:
        db.close()


def get(tenant_id: int, namespace: str, batch_no: str) -> dict:
    _require_db()
    db = get_sessionmaker()()
    try:
        row = _row(db, tenant_id, namespace, batch_no)
        return {"batchNo": row.batch_no, "status": row.status,
                "payload": _decode(row.payload_json or {}),
                "errors": _decode(row.errors_json or []),
                "publicResult": _decode(row.public_result_json or {}),
                "requestId": row.request_id}
    finally:
        db.close()


def claim(tenant_id: int, namespace: str, batch_no: str, *, required_status: str,
          request_id: str | None = None) -> tuple[dict, str | None, bool]:
    _require_db()
    db = get_sessionmaker()()
    try:
        row = _row(db, tenant_id, namespace, batch_no, lock=True)
        if row.status == "SUCCESS":
            if request_id and row.request_id and row.request_id != request_id:
                raise AppException("DATA_CONFLICT", "该批次已由另一个请求确认")
            return _decode(row.public_result_json or {}), None, True
        now = datetime.utcnow()
        if row.status == "CONFIRMING" and row.claim_started_at \
                and row.claim_started_at > now - timedelta(seconds=CLAIM_STALE_SECONDS):
            raise AppException("DATA_CONFLICT", "该批次正在另一服务实例确认，请稍后重试")
        if row.status not in (required_status, "CONFIRMING"):
            raise AppException("VALIDATION_ERROR", "该批次未通过 Dry-Run 校验，禁止确认导入")
        if request_id:
            conflict = db.scalar(select(type(row)).where(
                type(row).tenant_id == int(tenant_id), type(row).namespace == namespace,
                type(row).request_id == request_id, type(row).batch_no != batch_no,
                type(row).is_deleted.is_(False)))
            if conflict:
                raise AppException("IDEMPOTENCY_CONFLICT", "相同 requestId 提交了不同批次")
        token = secrets.token_hex(24)
        row.status = "CONFIRMING"
        row.request_id = request_id or row.request_id
        row.claim_token = token
        row.claim_started_at = now
        row.last_error = None
        row.version = int(row.version or 0) + 1
        db.commit()
        return _decode(row.payload_json or {}), token, False
    finally:
        db.close()


def finish(tenant_id: int, namespace: str, batch_no: str, claim_token: str,
           public_result: dict) -> None:
    _require_db()
    db = get_sessionmaker()()
    try:
        row = _row(db, tenant_id, namespace, batch_no, lock=True)
        if row.status == "SUCCESS":
            return
        if row.status != "CONFIRMING" or row.claim_token != claim_token:
            raise AppException("DATA_CONFLICT", "导入确认租约已失效")
        now = datetime.utcnow()
        row.status = "SUCCESS"
        row.public_result_json = _encode(public_result)
        row.confirmed_at = now
        row.claim_token = None
        row.claim_started_at = None
        row.expires_at = now + timedelta(seconds=RESULT_TTL)
        row.version = int(row.version or 0) + 1
        db.commit()
    finally:
        db.close()


def fail(tenant_id: int, namespace: str, batch_no: str, claim_token: str,
         error: str, *, retryable: bool = True) -> None:
    _require_db()
    db = get_sessionmaker()()
    try:
        row = _row(db, tenant_id, namespace, batch_no, lock=True)
        if row.status == "CONFIRMING" and row.claim_token == claim_token:
            row.status = "DRY_RUN_PASSED" if retryable else "CONFIRM_FAILED"
            row.claim_token = None
            row.claim_started_at = None
            row.last_error = str(error or "")[:2000]
            row.version = int(row.version or 0) + 1
            db.commit()
    finally:
        db.close()
