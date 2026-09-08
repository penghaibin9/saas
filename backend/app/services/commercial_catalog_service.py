"""Immutable M1 SKU publication backed by MySQL.

The catalogue defines what may be sold; it never grants a tenant runtime access.
Published snapshots are immutable. Retirement only prevents future selection and
never rewrites order-item snapshots already signed into a contract.
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker
from app.services import platform_defaults as D
from app.services.commercial_catalog_contract import ContractError, Snapshot, compile_sku
from time import sleep

from sqlalchemy.exc import IntegrityError, OperationalError


APPROVED_FEATURE_SCOPES: dict[str, tuple[str, ...]] = {
    "internship": (
        "internship", "studentProfile", "fileUpload", "studentImport", "studentExport",
        "approval", "todoMessage", "auditLog", "dataExport", "miniapp",
    ),
    "graduationDesign": (
        "graduation", "studentProfile", "fileUpload", "studentImport", "studentExport",
        "approval", "todoMessage", "auditLog", "dataExport", "miniapp",
    ),
    "studentAffairs": (
        "studentAffairs", "studentProfile", "orientation", "campusService", "riskWarning",
        "fileUpload", "studentImport", "studentExport", "approval", "todoMessage",
        "auditLog", "dataExport", "miniapp",
    ),
    "academicAffairs": (
        "academicAffairs", "studentProfile", "fileUpload", "studentImport", "studentExport",
        "approval", "todoMessage", "auditLog", "dataExport", "miniapp",
    ),
}


def _require_db() -> None:
    if not db_enabled():
        raise AppException("SERVER_ERROR", "商业商品发布需要数据库")


def _row_snapshot(row) -> Snapshot:
    if row is None:
        raise AppException("DATA_NOT_FOUND", "商品版本不存在", http_status=404)
    return Snapshot(str(row.snapshot_json and __import__('json').dumps(
        row.snapshot_json, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False
    )))


def get_sku_snapshot(sku_code: str, revision: int, *, published_only: bool = True, db_session=None) -> Snapshot:
    _require_db()
    from sqlalchemy import select
    from app.models import CommercialSkuVersion

    def read(db):
        row = db.scalars(select(CommercialSkuVersion).where(
            CommercialSkuVersion.sku_code == str(sku_code),
            CommercialSkuVersion.sku_revision == int(revision),
            CommercialSkuVersion.is_deleted.is_(False),
        )).first()
        if row is None or (published_only and row.publish_status != "PUBLISHED"):
            raise AppException("DATA_NOT_FOUND", "商品版本不存在或已停售", http_status=404)
        snapshot = _row_snapshot(row)
        if snapshot.content_hash != row.content_hash:
            raise AppException("DATA_CONFLICT", "商品快照指纹不一致，已停止使用", http_status=409)
        return snapshot

    if db_session is not None:
        return read(db_session)
    db = get_sessionmaker()()
    try:
        return read(db)
    finally:
        db.close()


_MAX_PUBLISH_ATTEMPTS = 4


def publish_sku(payload: dict, *, reason: str, actor_id: int | None = None) -> dict:
    """Publish atomically; retry only a confirmed, fully rolled-back deadlock.

    Never retry a lost connection/unknown commit result, a business conflict or
    an audit outage. Each attempt owns a fresh session and closes it before any
    backoff. The immutable unique key still decides the winner and replay.
    """
    for attempt in range(_MAX_PUBLISH_ATTEMPTS):
        try:
            return _publish_sku_once(payload, reason=reason, actor_id=actor_id)
        except OperationalError as exc:
            args = getattr(exc.orig, "args", ())
            if exc.connection_invalidated or not args or args[0] != 1213:
                raise
            if attempt + 1 == _MAX_PUBLISH_ATTEMPTS:
                raise AppException(
                    "COMMERCIAL_PUBLISH_BUSY",
                    "商品发布并发繁忙，本次事务已回滚，请使用相同内容重试",
                    details={"retryable": True},
                    http_status=503,
                ) from exc
            sleep(0.01 * (2 ** attempt))
    raise AssertionError("unreachable publication retry state")


def _publish_sku_once(payload: dict, *, reason: str, actor_id: int | None = None) -> dict:
    _require_db()
    from sqlalchemy import select
    from app.models import CommercialSkuVersion
    from app.services import audit_log

    reason_text = str(reason or "").strip()
    if len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "商品发布原因至少5个字符", http_status=422)
    db = get_sessionmaker()()
    try:
        def resolve_component(code: str, revision: int) -> Snapshot:
            return get_sku_snapshot(code, revision, db_session=db)

        try:
            snapshot = compile_sku(
                payload,
                known_features=D.FEATURE_KEYS,
                approved_features=APPROVED_FEATURE_SCOPES,
                resolve_component=resolve_component,
            )
        except ContractError as exc:
            raise AppException("VALIDATION_ERROR", str(exc), http_status=422) from exc
        data = snapshot.as_dict()
        # The snapshot is immutable: this is only an optimistic replay check.
        # Do not gap-lock a missing version before INSERT. The database unique
        # constraint serializes publishers; duplicate losers read after rollback.
        existing = db.scalars(select(CommercialSkuVersion).where(
            CommercialSkuVersion.sku_code == data["skuCode"],
            CommercialSkuVersion.sku_revision == int(data["revision"]),
            CommercialSkuVersion.is_deleted.is_(False),
        )).first()
        if existing is not None:
            if existing.content_hash != snapshot.content_hash:
                raise AppException("DATA_CONFLICT", "同一SKU版本已经发布且内容不可修改", http_status=409)
            return {
                "skuCode": existing.sku_code,
                "revision": int(existing.sku_revision),
                "contentHash": existing.content_hash,
                "publishStatus": existing.publish_status,
                "version": int(existing.version or 0),
                "replayed": True,
            }
        row = CommercialSkuVersion(
            tenant_id=0,
            sku_code=data["skuCode"],
            sku_revision=int(data["revision"]),
            product_type=data["productType"],
            module_key=data.get("moduleKey"),
            content_hash=snapshot.content_hash,
            snapshot_json=data,
            lifecycle_policy_version=data["lifecyclePolicyVersion"],
            publish_status="PUBLISHED",
            remark=reason_text,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            # Two publishers can observe an absent version concurrently.  The
            # database uniqueness constraint is the serialization point: after
            # rollback, the winner is authoritative.  Identical content is an
            # idempotent replay; different content for the same immutable version
            # is a 409 rather than a leaked MySQL duplicate-key error.
            db.rollback()
            winner = db.scalars(select(CommercialSkuVersion).where(
                CommercialSkuVersion.sku_code == data["skuCode"],
                CommercialSkuVersion.sku_revision == int(data["revision"]),
                CommercialSkuVersion.is_deleted.is_(False),
            )).first()
            if winner is not None and winner.content_hash == snapshot.content_hash:
                return {
                    "skuCode": winner.sku_code,
                    "revision": int(winner.sku_revision),
                    "contentHash": winner.content_hash,
                    "publishStatus": winner.publish_status,
                    "version": int(winner.version or 0),
                    "replayed": True,
                }
            raise AppException(
                "DATA_CONFLICT", "同一SKU版本已被并发发布且内容不同", http_status=409
            )
        audit_log.record_critical_in_session(
            db,
            "COMMERCIAL_SKU_PUBLISH",
            f"sku:{row.sku_code}:{row.sku_revision}",
            detail={"contentHash": row.content_hash, "moduleKey": row.module_key, "reason": reason_text},
            tenant_id=0,
            resource_id=str(row.id),
        )
        # Build the response before COMMIT so a post-commit lazy read cannot
        # accidentally cause the outer wrapper to replay an already committed write.
        response = {
            "skuCode": row.sku_code,
            "revision": int(row.sku_revision),
            "contentHash": row.content_hash,
            "publishStatus": row.publish_status,
            "version": int(row.version or 0),
            "replayed": False,
        }
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
