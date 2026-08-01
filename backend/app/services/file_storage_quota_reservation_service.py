"""阶段 9：并发安全的文件存储配额预留、消费、释放与对账。

所有容量判定都在 ``TenantStorageQuota`` 行锁内完成。真实 FileObject 与仍处于 HELD 的预留
共同占用配额，避免两个并发请求都看到旧用量后同时写入。服务器物理写入以 object key 为
source_id；后续 FileObject 出现时会自动消费对应预留，进程崩溃则由过期回收释放。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, or_, select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker
from app.models.file_quota import FileStorageQuotaReservation

ACTIVE = "HELD"
FINAL = {"CONSUMED", "RELEASED", "EXPIRED"}
DEFAULT_TTL_SECONDS = 60 * 60


def _tenant_id(value: int | None = None) -> int:
    tenant_id = int(value or current_tenant_id() or 0)
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return tenant_id


def _actor_id() -> int | None:
    from app.services.message_identity import resolve_message_user_id

    return resolve_message_user_id(get_current_user_ctx() or {}) or None


def _module_from_biz(value: str | None) -> str:
    biz = str(value or "").upper()
    for prefix, module in (
        ("GRADUATION", "GRADUATION"),
        ("INTERNSHIP", "INTERNSHIP"),
        ("AFFAIRS", "STUDENT_AFFAIRS"),
        ("ACADEMIC", "ACADEMIC_AFFAIRS"),
        ("IDENTITY", "SYSTEM"),
        ("MIGRATION", "SYSTEM"),
        ("DATA_EXCHANGE", "SYSTEM"),
    ):
        if biz.startswith(prefix):
            return module
    return "SHARED"


def _expire_locked(db, tenant_id: int, now: datetime) -> int:
    rows = db.scalars(select(FileStorageQuotaReservation).where(
        FileStorageQuotaReservation.tenant_id == tenant_id,
        FileStorageQuotaReservation.status == ACTIVE,
        FileStorageQuotaReservation.expires_at <= now,
        FileStorageQuotaReservation.is_deleted.is_(False),
    ).with_for_update()).all()
    for row in rows:
        row.status = "EXPIRED"
        row.released_at = now
        row.release_reason = "RESERVATION_TTL_EXPIRED"
    if rows:
        db.flush()
    return len(rows)


def _reconcile_storage_locked(db, tenant_id: int, now: datetime) -> int:
    """将已产生 FileObject 的服务器物理写入预留转为 CONSUMED。"""
    from app.models.file import FileObject

    rows = db.scalars(select(FileStorageQuotaReservation).where(
        FileStorageQuotaReservation.tenant_id == tenant_id,
        FileStorageQuotaReservation.status == ACTIVE,
        FileStorageQuotaReservation.source_type == "STORAGE_PERSIST",
        FileStorageQuotaReservation.expires_at > now,
        FileStorageQuotaReservation.is_deleted.is_(False),
    ).with_for_update()).all()
    consumed = 0
    for row in rows:
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == tenant_id,
            FileObject.is_deleted.is_(False),
            or_(
                FileObject.file_key == row.source_id,
                FileObject.object_key == row.source_id,
            ),
        ).order_by(FileObject.id.desc())).first()
        if file_obj:
            row.status = "CONSUMED"
            row.consumed_file_id = int(file_obj.id)
            row.consumed_at = now
            consumed += 1
    if consumed:
        db.flush()
    return consumed


def _actual_usage(db, tenant_id: int) -> int:
    from app.models.file import FileObject

    return int(db.scalar(select(func.coalesce(func.sum(FileObject.size_bytes), 0)).where(
        FileObject.tenant_id == tenant_id,
        FileObject.is_deleted.is_(False),
    )) or 0)


def _actual_module_usage(db, tenant_id: int, module_code: str) -> int:
    from app.models.file import FileObject

    rows = db.execute(select(
        FileObject.biz_type,
        func.coalesce(func.sum(FileObject.size_bytes), 0),
    ).where(
        FileObject.tenant_id == tenant_id,
        FileObject.is_deleted.is_(False),
    ).group_by(FileObject.biz_type)).all()
    return sum(int(size or 0) for biz, size in rows if _module_from_biz(biz) == module_code)


def _held_usage(db, tenant_id: int, now: datetime, *, module_code: str | None = None,
                exclude_key: str | None = None) -> int:
    clauses = [
        FileStorageQuotaReservation.tenant_id == tenant_id,
        FileStorageQuotaReservation.status == ACTIVE,
        FileStorageQuotaReservation.expires_at > now,
        FileStorageQuotaReservation.is_deleted.is_(False),
    ]
    if module_code:
        clauses.append(FileStorageQuotaReservation.module_code == module_code)
    if exclude_key:
        clauses.append(FileStorageQuotaReservation.reservation_key != exclude_key)
    return int(db.scalar(select(func.coalesce(func.sum(
        FileStorageQuotaReservation.reserved_bytes
    ), 0)).where(*clauses)) or 0)


def reserve_quota(
    *,
    reservation_key: str,
    source_type: str,
    source_id: str,
    size_bytes: int,
    module_code: str | None = None,
    tenant_id: int | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    db=None,
) -> FileStorageQuotaReservation | None:
    """原子占用容量；未配置硬配额时返回 None。"""
    if not db_enabled():
        return None
    from app.models.file import TenantStorageQuota

    tenant_id = _tenant_id(tenant_id)
    requested = max(0, int(size_bytes or 0))
    if requested <= 0:
        raise AppException("VALIDATION_ERROR", "预留文件大小必须大于 0")
    key = str(reservation_key or "").strip()
    if not key or len(key) > 160:
        raise AppException("VALIDATION_ERROR", "配额预留键无效")
    module = str(module_code or "SHARED").upper()
    now = datetime.utcnow()
    owns = db is None
    working = db or get_sessionmaker()()
    try:
        quota = working.scalars(select(TenantStorageQuota).where(
            TenantStorageQuota.tenant_id == tenant_id,
            TenantStorageQuota.is_deleted.is_(False),
        ).with_for_update()).first()
        if not quota or not quota.hard_limit_enabled:
            if owns:
                working.rollback()
            return None

        _expire_locked(working, tenant_id, now)
        _reconcile_storage_locked(working, tenant_id, now)
        existing = working.scalars(select(FileStorageQuotaReservation).where(
            FileStorageQuotaReservation.tenant_id == tenant_id,
            FileStorageQuotaReservation.reservation_key == key,
            FileStorageQuotaReservation.is_deleted.is_(False),
        ).with_for_update()).first()
        if existing:
            if existing.status == ACTIVE:
                if int(existing.reserved_bytes or 0) != requested:
                    raise AppException("DATA_CONFLICT", "同一配额预留键的文件大小不一致")
                existing.expires_at = max(
                    existing.expires_at,
                    now + timedelta(seconds=max(60, int(ttl_seconds or DEFAULT_TTL_SECONDS))),
                )
                if owns:
                    working.commit()
                    working.refresh(existing)
                else:
                    working.flush()
                return existing
            if existing.status == "CONSUMED":
                return existing
            raise AppException("DATA_CONFLICT", "配额预留键已释放或过期，不能重复使用")

        actual = _actual_usage(working, tenant_id)
        held = _held_usage(working, tenant_id, now)
        total_limit = int(quota.total_quota_bytes or 0)
        if total_limit > 0 and actual + held + requested > total_limit:
            raise AppException(
                "TENANT_STORAGE_QUOTA_EXCEEDED",
                "学校文件存储空间已满，请清理过期文件或联系学校管理员扩容",
                http_status=409,
                details={
                    "usedBytes": actual,
                    "reservedBytes": held,
                    "quotaBytes": total_limit,
                    "requestedBytes": requested,
                },
            )

        module_limits = dict(quota.module_quota_json or {})
        module_limit = int(module_limits.get(module) or 0)
        if module_limit > 0:
            module_actual = _actual_module_usage(working, tenant_id, module)
            module_held = _held_usage(working, tenant_id, now, module_code=module)
            if module_actual + module_held + requested > module_limit:
                raise AppException(
                    "MODULE_STORAGE_QUOTA_EXCEEDED",
                    "当前业务模块存储空间已满",
                    http_status=409,
                    details={
                        "moduleCode": module,
                        "usedBytes": module_actual,
                        "reservedBytes": module_held,
                        "quotaBytes": module_limit,
                        "requestedBytes": requested,
                    },
                )

        row = FileStorageQuotaReservation(
            tenant_id=tenant_id,
            reservation_key=key,
            module_code=module,
            source_type=str(source_type or "UNKNOWN").upper()[:40],
            source_id=str(source_id or "")[:500],
            reserved_bytes=requested,
            status=ACTIVE,
            expires_at=now + timedelta(seconds=max(60, int(ttl_seconds or DEFAULT_TTL_SECONDS))),
            created_by=_actor_id(),
        )
        working.add(row)
        if owns:
            working.commit()
            working.refresh(row)
        else:
            working.flush()
        return row
    except Exception:
        if owns:
            working.rollback()
        raise
    finally:
        if owns:
            working.close()


def consume_quota(reservation_key: str, *, file_id: int, tenant_id: int | None = None,
                  db=None) -> bool:
    if not db_enabled() or not reservation_key:
        return False
    tenant_id = _tenant_id(tenant_id)
    owns = db is None
    working = db or get_sessionmaker()()
    try:
        row = working.scalars(select(FileStorageQuotaReservation).where(
            FileStorageQuotaReservation.tenant_id == tenant_id,
            FileStorageQuotaReservation.reservation_key == reservation_key,
            FileStorageQuotaReservation.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            return False
        if row.status == "CONSUMED":
            if row.consumed_file_id and int(row.consumed_file_id) != int(file_id):
                raise AppException("DATA_CONFLICT", "配额预留已被其他文件消费")
            return True
        if row.status != ACTIVE:
            raise AppException("DATA_CONFLICT", "配额预留已失效")
        row.status = "CONSUMED"
        row.consumed_file_id = int(file_id)
        row.consumed_at = datetime.utcnow()
        if owns:
            working.commit()
        else:
            working.flush()
        return True
    except Exception:
        if owns:
            working.rollback()
        raise
    finally:
        if owns:
            working.close()


def release_quota(reservation_key: str, *, reason: str, tenant_id: int | None = None,
                  db=None) -> bool:
    if not db_enabled() or not reservation_key:
        return False
    tenant_id = _tenant_id(tenant_id)
    owns = db is None
    working = db or get_sessionmaker()()
    try:
        row = working.scalars(select(FileStorageQuotaReservation).where(
            FileStorageQuotaReservation.tenant_id == tenant_id,
            FileStorageQuotaReservation.reservation_key == reservation_key,
            FileStorageQuotaReservation.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row or row.status in FINAL:
            return bool(row)
        row.status = "RELEASED"
        row.released_at = datetime.utcnow()
        row.release_reason = str(reason or "RELEASED")[:300]
        if owns:
            working.commit()
        else:
            working.flush()
        return True
    except Exception:
        if owns:
            working.rollback()
        raise
    finally:
        if owns:
            working.close()


def release_source(*, source_type: str, source_id: str, reason: str,
                   tenant_id: int | None = None, db=None) -> int:
    if not db_enabled():
        return 0
    tenant_id = _tenant_id(tenant_id)
    owns = db is None
    working = db or get_sessionmaker()()
    try:
        rows = working.scalars(select(FileStorageQuotaReservation).where(
            FileStorageQuotaReservation.tenant_id == tenant_id,
            FileStorageQuotaReservation.source_type == str(source_type).upper(),
            FileStorageQuotaReservation.source_id == str(source_id),
            FileStorageQuotaReservation.status == ACTIVE,
            FileStorageQuotaReservation.is_deleted.is_(False),
        ).with_for_update()).all()
        now = datetime.utcnow()
        for row in rows:
            row.status = "RELEASED"
            row.released_at = now
            row.release_reason = str(reason or "SOURCE_RELEASED")[:300]
        if owns:
            working.commit()
        else:
            working.flush()
        return len(rows)
    except Exception:
        if owns:
            working.rollback()
        raise
    finally:
        if owns:
            working.close()


def expire_reservations(*, tenant_id: int, limit: int = 5000) -> dict:
    if not db_enabled():
        return {"tenantId": tenant_id, "expired": 0, "reconciled": 0}
    db = get_sessionmaker()()
    now = datetime.utcnow()
    try:
        reconciled = _reconcile_storage_locked(db, tenant_id, now)
        rows = db.scalars(select(FileStorageQuotaReservation).where(
            FileStorageQuotaReservation.tenant_id == tenant_id,
            FileStorageQuotaReservation.status == ACTIVE,
            FileStorageQuotaReservation.expires_at <= now,
            FileStorageQuotaReservation.is_deleted.is_(False),
        ).order_by(FileStorageQuotaReservation.id).limit(max(1, min(limit, 5000))).with_for_update()).all()
        for row in rows:
            row.status = "EXPIRED"
            row.released_at = now
            row.release_reason = "RESERVATION_TTL_EXPIRED"
        db.commit()
        return {"tenantId": tenant_id, "expired": len(rows), "reconciled": reconciled}
    finally:
        db.close()


def held_bytes(*, tenant_id: int | None = None, module_code: str | None = None) -> int:
    if not db_enabled():
        return 0
    tenant_id = _tenant_id(tenant_id)
    db = get_sessionmaker()()
    try:
        now = datetime.utcnow()
        _expire_locked(db, tenant_id, now)
        _reconcile_storage_locked(db, tenant_id, now)
        value = _held_usage(db, tenant_id, now, module_code=module_code)
        db.commit()
        return value
    finally:
        db.close()
