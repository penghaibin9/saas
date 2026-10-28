"""岗位实习乐观锁：复用公共 atomic_versioned_update，对外统一 DATA_CONFLICT。"""
from __future__ import annotations

from typing import Any, Mapping

from app.core.exceptions import AppException
from app.core.optimistic_lock import atomic_versioned_update, require_expected_version


def extract_expected_version(body: Any, *, required: bool = True) -> int | None:
    """从 body / dict 读取 expectedVersion（兼容 version 别名）。"""
    if body is None:
        raw = None
    elif isinstance(body, Mapping):
        raw = body.get("expectedVersion", body.get("version"))
    else:
        raw = getattr(body, "expectedVersion", None)
        if raw is None:
            raw = getattr(body, "version", None)
    if raw is None:
        if required:
            raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（乐观锁），请刷新后重试")
        return None
    return require_expected_version(raw)


def versioned_update(db, model, *, entity_id: int, tenant_id: int,
                     expected_version, values: dict,
                     expected_status: str | None = None,
                     status_column: str = "status",
                     extra_where=()):
    """原子 version 条件更新；冲突统一 DATA_CONFLICT。"""
    try:
        return atomic_versioned_update(
            db, model,
            entity_id=entity_id, tenant_id=tenant_id,
            expected_version=expected_version, values=values,
            expected_status=expected_status, status_column=status_column,
            extra_where=extra_where,
        )
    except AppException as e:
        if e.code == "APPROVAL_VERSION_CONFLICT":
            raise AppException("DATA_CONFLICT", "数据已被其他用户修改，请刷新后重试") from e
        raise
