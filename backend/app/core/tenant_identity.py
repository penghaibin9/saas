"""Canonical tenant identity registry.

All production/test helpers that need a well-known tenant slot must import from here.
Do not duplicate Snowflake tenant ids in feature seeds or request middleware.

The registry is intentionally small: it only covers platform-owned well-known tenants.
Real customer tenants remain database facts and must always be resolved by tenant_code.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantIdentity:
    tenant_id: int
    tenant_code: str


PLATFORM = TenantIdentity(1000000000000000000, "platform")
PRIMARY_DEMO = TenantIdentity(1000000000000000001, "demo")
LEGACY_HNSH = TenantIdentity(1000000000000000002, "hnsh")
DEMO_SCHOOL = TenantIdentity(1000000000000000003, "demo-school")
TRIAL_SCHOOL = TenantIdentity(1000000000000000004, "trial-school")
EXPIRED_SCHOOL = TenantIdentity(1000000000000000005, "expired-school")
DISABLED_SCHOOL = TenantIdentity(1000000000000000006, "disabled-school")
SANDBOX_SCHOOL = TenantIdentity(1000000000000000007, "sandbox-school")

WELL_KNOWN_BY_CODE = {
    item.tenant_code: item
    for item in (
        PLATFORM,
        PRIMARY_DEMO,
        LEGACY_HNSH,
        DEMO_SCHOOL,
        TRIAL_SCHOOL,
        EXPIRED_SCHOOL,
        DISABLED_SCHOOL,
        SANDBOX_SCHOOL,
    )
}
WELL_KNOWN_BY_ID = {item.tenant_id: item for item in WELL_KNOWN_BY_CODE.values()}


def assert_well_known_identity(tenant_id: int, tenant_code: str) -> TenantIdentity:
    """Fail closed when a hard-known tenant id/code pair drifts."""
    identity = WELL_KNOWN_BY_ID.get(int(tenant_id))
    if identity is None or identity.tenant_code != str(tenant_code or "").strip():
        raise ValueError(
            f"well-known tenant identity mismatch: id={tenant_id!r} code={tenant_code!r}"
        )
    return identity
