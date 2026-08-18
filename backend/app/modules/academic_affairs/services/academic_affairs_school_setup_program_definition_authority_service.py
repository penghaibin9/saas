"""Canonical activation owner for Program DEFINITION confirmation.

The lower-level confirm service owns the domain transaction.  This wrapper adds
the missing authority anchor for brand-new (v1) series before that transaction is
allowed to start: one control-plane Tenant row represents exactly one school, so
all v1 Program series confirmations for the same tenant serialize on a row that
already exists even when no Program row exists yet.

v2+ does not take this school-wide lock; its predecessor/series rows already give
the lower-level writer a stable domain lock anchor.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

from .academic_affairs_school_setup_program_definition_confirm_service import (
    _db_error_code,
    _is_mysql_lock_conflict,
    confirm_program_definition_import as _confirm_program_definition_import,
)


def _requires_tenant_series_lock(rows: Iterable[Mapping[str, object]]) -> bool:
    for raw in rows:
        if str(raw.get("logicalGroup") or "").strip().upper() != "MAIN":
            continue
        payload = raw.get("payload") or {}
        if not isinstance(payload, Mapping):
            continue
        try:
            version = int(payload.get("programVersion") or 0)
        except (TypeError, ValueError):
            version = 0
        if version == 1:
            return True
    return False


def _lock_tenant_authority(db) -> None:
    from app.models import Tenant

    tenant = db.scalars(
        select(Tenant).where(
            Tenant.id == _tid(),
            Tenant.is_deleted.is_(False),
        ).with_for_update()
    ).first()
    if tenant is None:
        raise AppException(
            "DATA_CONFLICT",
            "当前学校租户 Authority 不存在，拒绝确认培养方案",
            details={"tenantId": str(_tid())},
            http_status=409,
        )


def confirm_program_definition_import(
    normalized_rows: Iterable[Mapping[str, object]],
    *,
    user: dict,
) -> dict:
    """Canonical Program DEFINITION activation entrypoint.

    v1 holds the tenant row lock for the complete lower-level domain transaction,
    preventing two absent-series requests from choosing different Major rows and
    both creating the same ``series_key@v1`` before the later uniqueness phase is
    evidence-safe.  The lock transaction performs no domain writes of its own.
    """
    rows = [dict(row) for row in normalized_rows]
    if not _requires_tenant_series_lock(rows):
        return _confirm_program_definition_import(rows, user=user)

    try:
        with session() as lock_db:
            _lock_tenant_authority(lock_db)
            result = _confirm_program_definition_import(rows, user=user)
            lock_db.commit()
            return result
    except OperationalError as exc:
        if _is_mysql_lock_conflict(exc):
            raise AppException(
                "DATA_CONFLICT",
                "培养方案新系列确认期间发生租户 Authority 锁冲突，请重新预检后重试",
                details={"dbErrorCode": _db_error_code(exc)},
                http_status=409,
            ) from exc
        raise
