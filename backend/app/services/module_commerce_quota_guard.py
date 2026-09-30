"""M3 commercial module quota enforcement for the shared file reservation ledger.

The existing reservation service already serializes school-governance quotas. This
wrapper adds the upper commercial MODULE_V2 contract limit before that lower school
limit. It does not create a usage counter: actual FileObject bytes and HELD rows
remain the only consumption facts.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import select, text

from app.core.exceptions import AppException

_CANONICAL = {
    "INTERNSHIP": ("internship", "INTERNSHIP"),
    "GRADUATION": ("graduationDesign", "GRADUATION"),
    "GRADUATIONDESIGN": ("graduationDesign", "GRADUATION"),
    "STUDENT_AFFAIRS": ("studentAffairs", "STUDENT_AFFAIRS"),
    "STUDENTAFFAIRS": ("studentAffairs", "STUDENT_AFFAIRS"),
    "AFFAIRS": ("studentAffairs", "STUDENT_AFFAIRS"),
    "ACADEMIC_AFFAIRS": ("academicAffairs", "ACADEMIC_AFFAIRS"),
    "ACADEMICAFFAIRS": ("academicAffairs", "ACADEMIC_AFFAIRS"),
    "ACADEMIC": ("academicAffairs", "ACADEMIC_AFFAIRS"),
}
_LOCK_TIMEOUT_SECONDS = 8


def _module(value: str | None):
    return _CANONICAL.get(str(value or "").strip().upper())


@contextmanager
def _quota_lock(tenant_id: int, canonical_key: str):
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    acquired = False
    name = f"module-commerce-quota:{int(tenant_id)}:{canonical_key}"
    try:
        if db.get_bind().dialect.name != "mysql":
            raise AppException("SERVER_ERROR", "模块商业配额并发锁仅支持生产 MySQL", http_status=500)
        acquired = int(db.execute(
            text("SELECT GET_LOCK(:name, :timeout)"),
            {"name": name, "timeout": _LOCK_TIMEOUT_SECONDS},
        ).scalar_one_or_none() or 0) == 1
        if not acquired:
            raise AppException(
                "COMMERCIAL_QUOTA_BUSY", "模块配额正在并发核算，请使用相同请求重试",
                details={"retryable": True}, http_status=503,
            )
        yield
    finally:
        if acquired:
            try:
                db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": name})
            except Exception:
                pass
        db.close()


def _commercial_storage_limit(db, tenant_id: int, canonical_key: str) -> int | None:
    from app.models import TenantCommercialProfile, TenantModuleState, TenantModuleSubscriptionSource
    from app.services import module_subscription_service as subscriptions

    profile = db.scalars(select(TenantCommercialProfile).where(
        TenantCommercialProfile.tenant_id == int(tenant_id),
        TenantCommercialProfile.is_deleted.is_(False),
    )).first()
    if profile is None or str(profile.reader_version) != "MODULE_V2":
        return None
    state = db.scalars(select(TenantModuleState).where(
        TenantModuleState.tenant_id == int(tenant_id),
        TenantModuleState.module_key == canonical_key,
        TenantModuleState.is_deleted.is_(False),
    )).first()
    if state is None or str(state.data_state or "").upper() != "AVAILABLE":
        raise AppException("MODULE_NOT_WRITABLE", "目标模块当前不可写，不能新增文件占用", http_status=403)
    now = datetime.utcnow()
    rows = list(db.scalars(select(TenantModuleSubscriptionSource).where(
        TenantModuleSubscriptionSource.tenant_id == int(tenant_id),
        TenantModuleSubscriptionSource.module_key == canonical_key,
        TenantModuleSubscriptionSource.module_generation == int(state.generation),
        TenantModuleSubscriptionSource.status.in_(("ACTIVE", "SCHEDULED")),
        TenantModuleSubscriptionSource.starts_at <= now,
        TenantModuleSubscriptionSource.ends_at > now,
        TenantModuleSubscriptionSource.is_deleted.is_(False),
    ).order_by(TenantModuleSubscriptionSource.starts_at, TenantModuleSubscriptionSource.id)).all())
    if not rows:
        raise AppException("MODULE_NOT_AUTHORIZED", "目标模块没有有效商业订阅来源，不能新增文件占用", http_status=403)
    quotas = subscriptions._quota_projection(rows)
    rule = quotas.get("storageBytes")
    if rule is None:
        return None
    if not isinstance(rule, dict) or str(rule.get("unit") or "").upper() != "BYTES":
        raise AppException("DATA_CONFLICT", "模块商业存储额度快照无效，已停止新增占用", http_status=409)
    try:
        limit = int(rule.get("limit"))
    except (TypeError, ValueError, OverflowError):
        raise AppException("DATA_CONFLICT", "模块商业存储额度不是有效整数", http_status=409) from None
    return max(0, limit)


def install(quota_service):
    if getattr(quota_service, "_commercial_module_quota_installed", False):
        return quota_service
    original = quota_service.reserve_quota

    def reserve_quota(*, reservation_key: str, source_type: str, source_id: str,
                      size_bytes: int, module_code: str | None = None,
                      tenant_id: int | None = None, ttl_seconds: int = quota_service.DEFAULT_TTL_SECONDS,
                      db=None):
        from app.db.session import db_enabled, get_sessionmaker

        target = _module(module_code)
        if not db_enabled() or target is None:
            return original(
                reservation_key=reservation_key, source_type=source_type, source_id=source_id,
                size_bytes=size_bytes, module_code=module_code, tenant_id=tenant_id,
                ttl_seconds=ttl_seconds, db=db,
            )
        canonical_key, ledger_code = target
        tid = quota_service._tenant_id(tenant_id)
        requested = max(0, int(size_bytes or 0))
        with _quota_lock(tid, canonical_key):
            owns = db is None
            working = db or get_sessionmaker()()
            try:
                limit = _commercial_storage_limit(working, tid, canonical_key)
                if limit is not None:
                    now = datetime.utcnow()
                    actual = quota_service._actual_module_usage(working, tid, ledger_code)
                    held = quota_service._held_usage(
                        working, tid, now, module_code=ledger_code,
                        exclude_key=str(reservation_key or ""),
                    )
                    if actual + held + requested > limit:
                        raise AppException(
                            "COMMERCIAL_MODULE_STORAGE_QUOTA_EXCEEDED",
                            "当前模块已达到合同存储额度上限，请续费扩容或清理可清理内容",
                            http_status=409,
                            details={
                                "moduleKey": canonical_key,
                                "usedBytes": actual,
                                "reservedBytes": held,
                                "commercialQuotaBytes": limit,
                                "requestedBytes": requested,
                            },
                        )
                row = original(
                    reservation_key=reservation_key, source_type=source_type, source_id=source_id,
                    size_bytes=requested, module_code=ledger_code, tenant_id=tid,
                    ttl_seconds=ttl_seconds, db=working,
                )
                if owns:
                    working.commit()
                    if row is not None:
                        working.refresh(row)
                return row
            except Exception:
                if owns:
                    working.rollback()
                raise
            finally:
                if owns:
                    working.close()

    quota_service.reserve_quota = reserve_quota
    quota_service._commercial_module_quota_installed = True
    return quota_service
