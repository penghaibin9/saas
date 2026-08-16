"""Create only the tenants and administrator identities required by Playwright E2E.

This script intentionally does not call the repository's rich demo/sandbox seeders. Those
seeders create many cross-domain records and can lag behind newly tightened production
constraints. Browser E2E prepares its own domain prerequisites through real APIs.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import PlatformConfig, Role, Tenant, TenantBrandConfig, User, UserRole

TENANTS = (
    {
        "id": 1000000000000000003,
        "code": "demo-school",
        "name": "演示职业技术学校",
        "short": "演示职校",
        "login": "admin",
        "real_name": "E2E演示管理员",
    },
    {
        "id": 1000000000000000007,
        "code": "sandbox-school",
        "name": "体验沙箱学校",
        "short": "体验沙箱",
        "login": "admin2",
        "real_name": "E2E沙箱管理员",
    },
    {
        "id": 1000000000000000911,
        "code": "academic-w1-school",
        "name": "A-W1学期权威验收学校",
        "short": "A-W1验收校",
        "login": "academic_w1_admin",
        "real_name": "A-W1验收管理员",
    },
)


def assert_safe_target() -> None:
    env_name = str(os.getenv("APP_ENV") or "").lower()
    deploy_mode = str(os.getenv("DEPLOYMENT_MODE") or "").lower()
    if env_name in {"prod", "production"} or deploy_mode in {"prod", "production"}:
        raise SystemExit("refusing to seed Playwright tenants in production")
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")

    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must contain e2e or test")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("DATABASE_URL looks like a production or staging database")

    parsed = urlparse(db_url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Playwright tenant seed only accepts a local database")


def ensure_internship_entitlement(db, tenant_id: int) -> None:
    """Keep the isolated browser fixture explicit after production package/catalog cutovers.

    Production remains fail-closed.  The Playwright sandbox is a disposable acceptance
    tenant and must opt into internship before exercising the real module guard.
    """
    row = db.scalars(
        select(PlatformConfig).where(
            PlatformConfig.tenant_id == tenant_id,
            PlatformConfig.config_type == "FEATURES",
            PlatformConfig.config_key == "-",
            PlatformConfig.is_deleted.is_(False),
        )
    ).first()
    if row is None:
        db.add(
            PlatformConfig(
                tenant_id=tenant_id,
                config_type="FEATURES",
                config_key="-",
                config_json={"internship": True},
                enabled=True,
                status="ACTIVE",
                remark="Isolated Playwright acceptance entitlement",
            )
        )
        return

    features = dict(row.config_json or {})
    features["internship"] = True
    row.config_json = features
    row.enabled = True
    row.status = "ACTIVE"
    row.is_deleted = False


def ensure_tenant(db, spec: dict) -> None:
    tenant = db.get(Tenant, spec["id"])
    if tenant is None:
        tenant = Tenant(
            id=spec["id"],
            tenant_code=spec["code"],
            school_name=spec["name"],
            short_name=spec["short"],
            status="ACTIVE",
        )
        db.add(tenant)
    else:
        if tenant.tenant_code != spec["code"]:
            raise SystemExit(
                f"tenant id {spec['id']} belongs to {tenant.tenant_code!r}, refusing overwrite"
            )
        tenant.school_name = spec["name"]
        tenant.short_name = spec["short"]
        tenant.status = "ACTIVE"
        tenant.is_deleted = False

    brand = db.scalars(
        select(TenantBrandConfig).where(TenantBrandConfig.tenant_id == spec["id"])
    ).first()
    if brand is None:
        db.add(
            TenantBrandConfig(
                tenant_id=spec["id"],
                platform_name="高校学生全生命周期管理平台",
                browser_title="高校学生全生命周期管理平台",
                primary_color="#2563EB",
                default_theme="academy_blue",
                watermark_text=f"{spec['name']} · Playwright E2E",
            )
        )

    ensure_internship_entitlement(db, spec["id"])

    user = db.scalars(
        select(User).where(
            User.tenant_id == spec["id"],
            User.login_name == spec["login"],
        )
    ).first()
    if user is None:
        user = User(
            tenant_id=spec["id"],
            login_name=spec["login"],
            real_name=spec["real_name"],
            password_hash=hash_password("123456"),
            user_type="ADMIN",
            status="ACTIVE",
            must_change_password=False,
        )
        db.add(user)
    else:
        user.real_name = spec["real_name"]
        user.password_hash = hash_password("123456")
        user.user_type = "ADMIN"
        user.status = "ACTIVE"
        user.must_change_password = False
        user.is_deleted = False
    db.flush()

    role = db.scalars(
        select(Role).where(
            Role.tenant_id == spec["id"],
            Role.role_code == "SCHOOL_ADMIN",
            Role.is_deleted.is_(False),
        )
    ).first()
    if role is None:
        role = Role(
            tenant_id=spec["id"],
            role_code="SCHOOL_ADMIN",
            role_name="学校管理员",
            role_type="SYSTEM",
            status="ACTIVE",
        )
        db.add(role)
        db.flush()

    link = db.scalars(
        select(UserRole).where(
            UserRole.tenant_id == spec["id"],
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
            UserRole.is_deleted.is_(False),
        )
    ).first()
    if link is None:
        db.add(
            UserRole(
                tenant_id=spec["id"],
                user_id=user.id,
                role_id=role.id,
                status="ACTIVE",
            )
        )


def main() -> int:
    assert_safe_target()
    db = get_sessionmaker()()
    try:
        for spec in TENANTS:
            ensure_tenant(db, spec)
        db.commit()
        print(
            "[e2e-seed] ready:",
            ", ".join(f"{item['code']}:{item['login']}" for item in TENANTS),
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
