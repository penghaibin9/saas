"""Small contracts used by existing System Management pages to close P1 UI loops."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import or_, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.core.permissions import require_any_permission, require_permission
from app.core.response import success
from app.db.session import get_sessionmaker
from app.models.config_governance import (
    OVERRIDE_STATUS_ACTIVE,
    OVERRIDE_STATUS_REVOKED,
    SCOPE_TENANT,
    ConfigDefinition,
    ConfigOverride,
)

router = APIRouter(prefix="/system", tags=["系统管理·P1闭环"])


def _actor_id(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or (user or {}).get("id") or "").replace("db-", "")
    return int(raw) if raw.isdigit() else None


@router.get("/effective-config-overrides", summary="当前学校层配置覆盖元数据")
def list_effective_config_overrides(
    domain: str = Query(default="SECURITY"),
    user=Depends(require_any_permission(
        "systemAdmin.config.view",
        "systemAdmin.config.manage",
        "systemAdmin.security.policy.manage",
    )),
):
    """Return complete unexpired ACTIVE TENANT chains so restore can be exact and atomic."""
    tenant_id = int(current_tenant_id() or 0)
    now = datetime.utcnow().replace(microsecond=0)
    db = get_sessionmaker()()
    try:
        stmt = (
            select(ConfigOverride, ConfigDefinition)
            .join(ConfigDefinition, ConfigDefinition.config_key == ConfigOverride.config_key)
            .where(
                ConfigOverride.tenant_id == tenant_id,
                ConfigOverride.scope_type == SCOPE_TENANT,
                ConfigOverride.status == OVERRIDE_STATUS_ACTIVE,
                ConfigOverride.is_deleted.is_(False),
                ConfigDefinition.is_deleted.is_(False),
            )
            .order_by(ConfigOverride.config_key, ConfigOverride.effective_at.desc(), ConfigOverride.id.desc())
        )
        if domain:
            stmt = stmt.where(ConfigDefinition.domain_code == str(domain).upper())

        grouped: dict[str, dict] = {}
        for override, definition in db.execute(stmt).all():
            if override.expires_at is not None and override.expires_at <= now:
                continue
            group = grouped.setdefault(override.config_key, {"definition": definition, "rows": []})
            group["rows"].append(override)

        items = []
        for config_key, group in grouped.items():
            rows = group["rows"]
            definition = group["definition"]
            current = next((row for row in rows if row.effective_at <= now), None)
            display = current or rows[-1]
            chain = [
                {
                    "overrideId": str(row.id),
                    "version": int(row.version or 0),
                    "effectiveAt": row.effective_at.isoformat() if row.effective_at else None,
                    "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
                    "value": (row.value_json or {}).get("value"),
                    "reason": row.reason or "",
                    "scheduled": bool(row.effective_at and row.effective_at > now),
                }
                for row in rows
            ]
            items.append({
                "overrideId": str(display.id),
                "version": int(display.version or 0),
                "configKey": config_key,
                "configName": definition.config_name,
                "domain": definition.domain_code,
                "scopeType": SCOPE_TENANT,
                "scopeId": None,
                "value": (display.value_json or {}).get("value"),
                "effectiveAt": display.effective_at.isoformat() if display.effective_at else None,
                "expiresAt": display.expires_at.isoformat() if display.expires_at else None,
                "reason": display.reason or "",
                "isScheduledOnly": current is None,
                "overrideChain": chain,
                "overrideCount": len(chain),
                "scheduledCount": sum(1 for row in chain if row["scheduled"]),
            })
        items.sort(key=lambda item: item["configKey"])
        return success({"items": items, "total": len(items)})
    finally:
        db.close()


@router.post("/effective-config-overrides/restore-inheritance", summary="原子恢复学校层配置继承")
def restore_effective_config_inheritance(
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.config.manage")),
):
    """Revoke the entire active/scheduled TENANT chain with one lock, one audit and one commit."""
    tenant_id = int(current_tenant_id() or 0)
    config_key = str((body or {}).get("configKey") or "").strip()
    reason = str((body or {}).get("reason") or "").strip()
    requested = (body or {}).get("overrides") or []
    if not config_key:
        raise AppException("VALIDATION_ERROR", "缺少 configKey")
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "恢复继承原因不少于 5 个字")
    if not isinstance(requested, list) or not requested:
        raise AppException("VALIDATION_ERROR", "缺少要撤销的学校层覆盖链")

    expected_versions: dict[int, int] = {}
    try:
        for item in requested:
            override_id = int(item["overrideId"])
            expected_versions[override_id] = int(item["expectedVersion"])
    except (KeyError, TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "overrides 必须包含 overrideId 与 expectedVersion") from None
    if len(expected_versions) != len(requested):
        raise AppException("VALIDATION_ERROR", "覆盖链包含重复 overrideId")

    now = datetime.utcnow().replace(microsecond=0)
    db = get_sessionmaker()()
    try:
        rows = list(db.scalars(select(ConfigOverride).where(
            ConfigOverride.tenant_id == tenant_id,
            ConfigOverride.config_key == config_key,
            ConfigOverride.scope_type == SCOPE_TENANT,
            ConfigOverride.status == OVERRIDE_STATUS_ACTIVE,
            ConfigOverride.is_deleted.is_(False),
            or_(ConfigOverride.expires_at.is_(None), ConfigOverride.expires_at > now),
        ).with_for_update()).all())

        actual_ids = {int(row.id) for row in rows}
        requested_ids = set(expected_versions)
        if actual_ids != requested_ids:
            raise AppException(
                "DATA_CONFLICT",
                "学校层配置覆盖链已发生变化，请刷新后重试",
                http_status=409,
                details={"expectedIds": sorted(requested_ids), "actualIds": sorted(actual_ids)},
            )
        for row in rows:
            if int(row.version or 0) != expected_versions[int(row.id)]:
                raise AppException(
                    "DATA_CONFLICT", "配置覆盖已被其他人修改，请刷新后重试", http_status=409,
                    details={"overrideId": str(row.id)},
                )

        actor_id = _actor_id(user)
        for row in rows:
            row.status = OVERRIDE_STATUS_REVOKED
            row.reason = reason
            row.updated_by = actor_id
            row.version = int(row.version or 0) + 1

        from app.services import audit_log
        audit_log.record_critical_in_session(
            db,
            "CONFIG_OVERRIDE_RESTORE_INHERITANCE",
            f"config:{config_key}",
            detail={
                "configKey": config_key,
                "overrideIds": sorted(str(row.id) for row in rows),
                "overrideCount": len(rows),
                "reason": reason,
                "moduleCode": "systemAdmin",
                "scopeType": SCOPE_TENANT,
                "restoredByInheritance": True,
            },
            tenant_id=tenant_id,
            resource_id=config_key,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    from app.services import effective_config_service as svc
    return success(
        {
            "configKey": config_key,
            "revokedCount": len(expected_versions),
            "effective": svc.resolve(config_key, tenant_id=tenant_id),
        },
        message="学校层覆盖已原子撤销并恢复继承",
    )
