"""Create isolated browser identities and verified commercial prerequisites.

Domain fixtures remain real API writes. This seed must never use a retired tenant
FEATURES override as proof of purchase or report READY before activation succeeds.
"""
from __future__ import annotations

import os
from urllib.parse import unquote, urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import Role, Tenant, TenantBrandConfig, User, UserRole

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
    env_name = str(os.getenv("APP_ENV") or "").strip().lower()
    deploy_mode = str(os.getenv("DEPLOYMENT_MODE") or "").strip().lower()
    if env_name in {"prod", "production"} or deploy_mode in {"prod", "production"}:
        raise SystemExit("refusing to seed Playwright tenants in production")
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")

    db_url = str(os.getenv("DATABASE_URL") or "")
    parsed = urlparse(db_url)
    database_name = unquote(parsed.path.lstrip("/")).lower()
    if parsed.scheme not in {"mysql", "mysql+pymysql"}:
        raise SystemExit("Playwright tenant seed requires MySQL")
    if not database_name or not any(marker in database_name for marker in ("e2e", "test")):
        raise SystemExit("database name must contain e2e or test")
    if any(marker in database_name for marker in ("prod", "production", "staging")):
        raise SystemExit("database name looks like a production or staging database")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Playwright tenant seed only accepts a local database")


def ensure_commercial_entitlement(tenant_id: int) -> str:
    """Activate a real order only for the three guarded positive browser fixtures.

    Re-running a successful seed reuses its verified order. An existing narrower
    paid package is rejected, not silently upgraded; IAM negative tenants are not
    in this seed's allowlist. Independent scripts verify the canonical authority
    directly, without relying on importing an HTTP router to install adapters.
    """
    assert_safe_target()
    if int(tenant_id) not in {item["id"] for item in TENANTS}:
        raise SystemExit("tenant is outside the Playwright positive-fixture allowlist")

    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import platform_service

    required = ("academicAffairs", "internship", "fileUpload")
    state = commercial.commercial_state(int(tenant_id))
    if state["verified"] and state["authoritySource"] != "TRIAL":
        if state["authoritySource"] == "PAID_ORDER" and all(
            state["features"].get(key, False) for key in required
        ):
            return str(state["commercialOrderNo"])
        raise SystemExit(f"refusing to replace existing commercial state for tenant {tenant_id}")

    # Resume only this bootstrap's exact owned order. Never replace another
    # commercial contract or create a second purchase after interrupted activation.
    remark = "Isolated Playwright paid commercial prerequisite"
    orders = platform_service.list_orders(tenant_id=int(tenant_id))
    if orders:
        if len(orders) != 1:
            raise SystemExit(f"ambiguous commercial history for tenant {tenant_id}")
        order = orders[0]
        if not (
            order.get("remark") == remark
            and order.get("packageCode") == "professional"
            and order.get("orderType") == "NEW"
            and order.get("status") in {"unpaid", "paid"}
            and order.get("amount") == 1
        ):
            raise SystemExit(f"refusing to replace existing order for tenant {tenant_id}")
    else:
        if str(state.get("packageCode") or "trial") != "trial":
            raise SystemExit(f"unverified formal package needs review for tenant {tenant_id}")
        # The production command owns payment, activation, versions and audit.
        order = platform_service.create_order({
            "tenantId": str(tenant_id),
            "packageCode": "professional",
            "orderType": "NEW",
            "durationDays": 30,
            "amount": 1,
            "remark": remark,
        })
    paid = platform_service.order_action(
        order["orderNo"], "mark-paid" if order["status"] == "unpaid" else "repair-activation",
        expected_version=int(order["version"]),
        reason="Playwright真实订单授权初始化",
    )
    if paid.get("repairTaskRequired"):
        paid = platform_service.order_action(
            order["orderNo"], "repair-activation",
            expected_version=int(paid["version"]),
            reason="Playwright修复订单授权激活",
        )
    state = commercial.commercial_state(int(tenant_id))
    if not (
        paid.get("tenantActivated")
        and state["verified"]
        and state["authoritySource"] == "PAID_ORDER"
        and state.get("commercialOrderNo") == order["orderNo"]
        and all(state["features"].get(key, False) for key in required)
    ):
        raise SystemExit(f"commercial activation did not verify for tenant {tenant_id}")
    return str(order["orderNo"])


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
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # Order commands own separate transactions and must see committed identities.
    for spec in TENANTS:
        ensure_commercial_entitlement(spec["id"])
    print(
        "[e2e-seed] ready:",
        ", ".join(f"{item['code']}:{item['login']}" for item in TENANTS),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
