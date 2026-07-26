"""公共乐观锁：强制 version + 原子 UPDATE（rowcount 校验）。"""
from __future__ import annotations

from sqlalchemy import update

from app.core.exceptions import AppException


def require_expected_version(expected_version) -> int:
    """状态变更必须携带 version；禁止 None 兼容放行。"""
    if expected_version is None:
        raise AppException("VALIDATION_ERROR", "必须提供 version（乐观锁），请刷新后重试")
    try:
        return int(expected_version)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "版本号非法")


def atomic_versioned_update(db, model, *, entity_id: int, tenant_id: int,
                            expected_version, values: dict,
                            expected_status: str | None = None,
                            status_column: str = "status",
                            extra_where=()):
    """
    UPDATE ... SET ..., version=version+1
    WHERE id AND tenant_id AND version=expected [AND status=expected]
    rowcount!=1 → APPROVAL_VERSION_CONFLICT
    """
    ver = require_expected_version(expected_version)
    payload = dict(values)
    # 数据库侧 version = version + 1，避免 Python 先读后写竞态
    payload["version"] = model.version + 1
    cond = [
        model.id == int(entity_id),
        model.tenant_id == int(tenant_id),
        model.version == ver,
        model.is_deleted.is_(False),
    ]
    if expected_status is not None:
        cond.append(getattr(model, status_column) == expected_status)
    cond.extend(list(extra_where or ()))
    res = db.execute(update(model).where(*cond).values(**payload))
    if (res.rowcount or 0) != 1:
        raise AppException("APPROVAL_VERSION_CONFLICT", "数据已被他人修改或状态已变化，请刷新后重试")
    return ver + 1


def atomic_claim_version(db, entity, expected_version) -> int:
    """Atomically reserve an ORM entity version before any side effects.

    This is the migration-safe CAS primitive for existing affairs services:
    the caller validates state/scope first, claims ``WHERE version=expected``,
    and only the winning transaction proceeds to audit/todo/message writes.
    """
    model = type(entity)
    ver = require_expected_version(expected_version)
    cond = [
        model.id == int(entity.id),
        model.version == ver,
    ]
    if hasattr(model, "tenant_id"):
        cond.append(model.tenant_id == int(entity.tenant_id))
    if hasattr(model, "is_deleted"):
        cond.append(model.is_deleted.is_(False))
    # The guarded no-op UPDATE acquires the row write lock. Existing services
    # then perform their normal single ``version += 1`` in the same transaction,
    # preserving the public contract that one successful action advances once.
    result = db.execute(
        update(model).where(*cond).values(version=model.version),
        execution_options={"synchronize_session": False},
    )
    if (result.rowcount or 0) != 1:
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "数据已被他人修改或状态已经变化，请刷新后重试",
        )
    return ver
