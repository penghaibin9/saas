"""Explicit effective security policy used by pre-authentication runtime.

Unlike ``system_config_service.get_int()``, this resolver never depends on the
request ContextVar.  Callers must provide a resolved tenant id (or explicitly
choose the PLATFORM principal plane), so a password login cannot silently fall
back to another tenant's/default policy before authentication establishes a
request subject.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.db.session import db_enabled, get_sessionmaker

TENANT = "TENANT"
PLATFORM = "PLATFORM"

_BASELINE = {
    "loginFailMaxTimes": 5,
    "loginFailLockMinutes": 15,
    "passwordMinLength": 8,
    "captchaAfterFailures": 2,
    "accessTokenExpireMinutes": 120,
    "refreshTokenExpireDays": 7,
}
_BOUNDS = {
    "loginFailMaxTimes": (3, 10),
    "loginFailLockMinutes": (5, 120),
    "passwordMinLength": (6, 32),
    "captchaAfterFailures": (1, 10),
    "accessTokenExpireMinutes": (15, 720),
    "refreshTokenExpireDays": (1, 30),
}
_TENANT_KEYS = {
    "SEC_LOCK_MAX_FAIL": "loginFailMaxTimes",
    "SEC_LOCK_MINUTES": "loginFailLockMinutes",
    "SEC_PASSWORD_MIN_LEN": "passwordMinLength",
}


def _bounded(name: str, value: Any, fallback: int) -> int:
    lo, hi = _BOUNDS[name]
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(fallback)
    return min(hi, max(lo, parsed))


def _revision(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def resolve_tenant_id(tenant_code: str | None) -> int | None:
    code = str(tenant_code or "").strip()
    if not code or not db_enabled():
        return None
    db = get_sessionmaker()()
    try:
        from app.models import Tenant

        tenant = db.scalars(select(Tenant).where(Tenant.tenant_code == code)).first()
        return int(tenant.id) if tenant is not None else None
    finally:
        db.close()


def _platform_security(db) -> tuple[dict, bool]:
    """Read global platform policy; malformed/unavailable data returns hard baseline."""
    try:
        from app.models import PlatformConfig

        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == "SECURITY",
            PlatformConfig.config_key == "-",
            PlatformConfig.is_deleted.is_(False),
        )).first()
        raw = dict(row.config_json or {}) if row is not None else {}
        return raw, False
    except Exception:  # noqa: BLE001
        return {}, True


def _tenant_security(db, tenant_id: int) -> tuple[dict, bool]:
    result: dict[str, int] = {}
    degraded = False
    try:
        from app.models import SysConfig
        from app.services.system_config_service import _override_int

        rows = db.scalars(select(SysConfig).where(
            SysConfig.tenant_id == int(tenant_id),
            SysConfig.config_key.in_(tuple(_TENANT_KEYS)),
            SysConfig.is_deleted.is_(False),
        )).all()
        saved = {row.config_key: row for row in rows}
        for source_key, target_key in _TENANT_KEYS.items():
            override = _override_int(db, int(tenant_id), source_key)
            if override is not None:
                result[target_key] = int(override)
                continue
            row = saved.get(source_key)
            if row is not None and row.value_text is not None:
                result[target_key] = int(str(row.value_text).strip())
    except Exception:  # noqa: BLE001
        # Enforcement must not become more permissive when configuration storage
        # is degraded.  The caller receives bounded hard-safe baseline/global
        # values and a DEGRADED marker for telemetry/audit.
        degraded = True
    return result, degraded


def resolve_login_policy(*, tenant_id: int | None, principal_plane: str = TENANT) -> dict:
    plane = str(principal_plane or TENANT).strip().upper()
    if plane not in {TENANT, PLATFORM}:
        plane = TENANT

    source = ["HARD_BASELINE"]
    degraded = False
    merged = dict(_BASELINE)
    merged["captchaAfterFailures"] = int(getattr(settings, "CAPTCHA_AFTER_FAILURES", 2) or 2)

    if db_enabled():
        db = get_sessionmaker()()
        try:
            platform_raw, platform_degraded = _platform_security(db)
            degraded = degraded or platform_degraded
            if platform_raw:
                source.append("PLATFORM_SECURITY")
                for key in (
                    "loginFailMaxTimes", "loginFailLockMinutes", "accessTokenExpireMinutes",
                    "refreshTokenExpireDays", "captchaAfterFailures", "passwordMinLength",
                ):
                    if key in platform_raw:
                        merged[key] = platform_raw[key]
            if plane == TENANT and tenant_id is not None:
                tenant_raw, tenant_degraded = _tenant_security(db, int(tenant_id))
                degraded = degraded or tenant_degraded
                if tenant_raw:
                    source.append("TENANT_SECURITY")
                    merged.update(tenant_raw)
        except Exception:  # noqa: BLE001
            degraded = True
        finally:
            db.close()
    else:
        degraded = True

    effective = {
        key: _bounded(key, merged.get(key), int(_BASELINE[key]))
        for key in _BASELINE
    }
    # Adaptive captcha must engage before or at the lock threshold.  Corrupted
    # configuration can therefore never create a window where brute-force
    # attempts exceed the lock contract without a challenge.
    effective["captchaAfterFailures"] = min(
        effective["captchaAfterFailures"],
        max(1, effective["loginFailMaxTimes"] - 1),
    )
    effective.update({
        "tenantId": int(tenant_id) if tenant_id is not None else None,
        "principalPlane": plane,
        "policySource": source,
        "dataQuality": "DEGRADED" if degraded else "HEALTHY",
    })
    effective["policyRevision"] = _revision({
        k: effective[k] for k in sorted(effective) if k != "policyRevision"
    })
    return effective


def resolve_for_user(user, client_type: str | None = None) -> dict:
    platform = (
        str(client_type or "").strip().upper() == "PLATFORM_PC"
        or str(getattr(user, "user_type", "") or "").upper() in {"PLATFORM_OP", "PLATFORM_SUPER_ADMIN"}
    )
    return resolve_login_policy(
        tenant_id=None if platform else int(user.tenant_id),
        principal_plane=PLATFORM if platform else TENANT,
    )


def resolve_for_claims(claims: dict) -> dict:
    role = str((claims or {}).get("currentRoleCode") or "").upper()
    user_type = str((claims or {}).get("userType") or "").upper()
    plane = PLATFORM if role == "PLATFORM_SUPER_ADMIN" or user_type in {"PLATFORM_OP", "PLATFORM_SUPER_ADMIN"} else TENANT
    raw_tid = (claims or {}).get("tenantId")
    tenant_id = int(raw_tid) if plane == TENANT and str(raw_tid or "").isdigit() else None
    return resolve_login_policy(tenant_id=tenant_id, principal_plane=plane)
