"""Small read-only contract used by the existing System Management pages to close P1 UI loops."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.permissions import require_any_permission
from app.core.response import success
from app.db.session import get_sessionmaker
from app.models.config_governance import (
    OVERRIDE_STATUS_ACTIVE,
    SCOPE_TENANT,
    ConfigDefinition,
    ConfigOverride,
)

router = APIRouter(prefix="/system", tags=["系统管理·P1闭环"])


@router.get("/effective-config-overrides", summary="当前学校层配置覆盖元数据")
def list_effective_config_overrides(
    domain: str = Query(default="SECURITY"),
    user=Depends(require_any_permission(
        "systemAdmin.config.view",
        "systemAdmin.config.manage",
        "systemAdmin.security.policy.manage",
    )),
):
    """Return complete active TENANT override chains so the UI can truly restore inheritance.

    ``set_override`` intentionally permits multiple same-layer rows with different effective_at
    values (scheduled/current history). Revoking only the winner can expose an older override
    instead of the package/default value. Each item therefore carries every unexpired ACTIVE
    TENANT row and its optimistic-lock version; the UI revokes the whole chain explicitly.
    """
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
            group = grouped.setdefault(override.config_key, {
                "definition": definition,
                "rows": [],
            })
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
