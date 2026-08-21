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
    ConfigDefinition,
    ConfigOverride,
)

router = APIRouter(prefix="/system", tags=["系统管理·P1闭环"])


@router.get("/effective-config-overrides", summary="当前有效配置覆盖元数据")
def list_effective_config_overrides(
    domain: str = Query(default="SECURITY"),
    user=Depends(require_any_permission("systemAdmin.config.view", "systemAdmin.config.manage")),
):
    """Return revocable override id/version without changing the canonical Resolver result shape."""
    tenant_id = int(current_tenant_id() or 0)
    now = datetime.utcnow().replace(microsecond=0)
    db = get_sessionmaker()()
    try:
        stmt = (
            select(ConfigOverride, ConfigDefinition)
            .join(ConfigDefinition, ConfigDefinition.config_key == ConfigOverride.config_key)
            .where(
                ConfigOverride.tenant_id == tenant_id,
                ConfigOverride.status == OVERRIDE_STATUS_ACTIVE,
                ConfigOverride.effective_at <= now,
                ConfigOverride.is_deleted.is_(False),
                ConfigDefinition.is_deleted.is_(False),
            )
            .order_by(ConfigOverride.config_key, ConfigOverride.effective_at.desc(), ConfigOverride.id.desc())
        )
        if domain:
            stmt = stmt.where(ConfigDefinition.domain_code == str(domain).upper())
        rows = db.execute(stmt).all()
        items = []
        for override, definition in rows:
            if override.expires_at is not None and override.expires_at <= now:
                continue
            items.append({
                "overrideId": str(override.id),
                "version": int(override.version or 0),
                "configKey": override.config_key,
                "configName": definition.config_name,
                "domain": definition.domain_code,
                "scopeType": override.scope_type,
                "scopeId": override.scope_id or None,
                "value": (override.value_json or {}).get("value"),
                "effectiveAt": override.effective_at.isoformat() if override.effective_at else None,
                "expiresAt": override.expires_at.isoformat() if override.expires_at else None,
                "reason": override.reason or "",
            })
        return success({"items": items, "total": len(items)})
    finally:
        db.close()
