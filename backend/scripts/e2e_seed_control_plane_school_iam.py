"""Minimal real prerequisites for the Control Plane school-IAM browser E2E.

This seed creates identities/tenant entitlement only. It deliberately does not
create a Custom Role, SecurityChange, RolePermission, or security revision;
those are browser E2E writes under test. Global Permission definitions are
materialized through the production Permission Catalog reconciliation Authority.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import select

from e2e_seed_playwright_tenants import assert_safe_target, ensure_tenant
from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import Role, User, UserRole
from app.services import platform_service
from app.services import system_role_shadow_service as shadow
from app.services.permission_catalog_reconciliation_service import reconcile_permission_catalog

DEMO_TID = 1000000000000000003
SANDBOX_TID = 1000000000000000007
IAM_E2E_TID = 1000000000000000011
IAM_E2E_TENANT = {
    "id": IAM_E2E_TID,
    "code": "iam-e2e-school",
    "name": "IAM E2E测试学校",
    "short": "IAM E2E",
    "login": "iam_admin",
    "real_name": "E2E IAM管理员",
}
DEMO_TARGET_LOGIN = "iam_teacher_demo"
IAM_TARGET_LOGIN = "iam_teacher"
TARGET_PERMISSION = "internship.recruitment.view"


def _ensure_role(db, tenant_id: int, code: str, name: str) -> Role:
    role = db.scalars(select(Role).where(
        Role.tenant_id == tenant_id,
        Role.role_code == code,
        Role.is_deleted.is_(False),
    )).first()
    if role is None:
        role = Role(
            tenant_id=tenant_id,
            role_code=code,
            role_name=name,
            role_type="SYSTEM",
            status="ACTIVE",
        )
        db.add(role)
        db.flush()
    else:
        role.role_name = name
        role.role_type = "SYSTEM"
        role.status = "ACTIVE"
        role.is_deleted = False
    return role


def _ensure_teacher(db, *, tenant_id: int, login_name: str, real_name: str) -> User:
    role = _ensure_role(db, tenant_id, "ACADEMIC_TEACHER", "任课教师")
    target = db.scalars(select(User).where(
        User.tenant_id == tenant_id,
        User.login_name == login_name,
        User.is_deleted.is_(False),
    )).first()
    if target is None:
        target = User(
            tenant_id=tenant_id,
            login_name=login_name,
            real_name=real_name,
            password_hash=hash_password("E2eIam@2026"),
            user_type="TEACHER",
            status="ACTIVE",
            must_change_password=False,
        )
        db.add(target)
        db.flush()
    else:
        target.real_name = real_name
        target.password_hash = hash_password("E2eIam@2026")
        target.user_type = "TEACHER"
        target.status = "ACTIVE"
        target.must_change_password = False
        target.is_deleted = False

    link = db.scalars(select(UserRole).where(
        UserRole.tenant_id == tenant_id,
        UserRole.user_id == target.id,
        UserRole.role_id == role.id,
        UserRole.is_deleted.is_(False),
    )).first()
    if link is None:
        db.add(UserRole(
            tenant_id=tenant_id,
            user_id=target.id,
            role_id=role.id,
            status="ACTIVE",
        ))
    else:
        link.status = "ACTIVE"
        link.is_deleted = False
    return target


def main() -> int:
    assert_safe_target()
    head_sha = str(os.getenv("E2E_EXPECTED_SHA") or os.getenv("GITHUB_SHA") or "").strip()
    if len(head_sha) < 7:
        raise SystemExit("E2E_EXPECTED_SHA/GITHUB_SHA is required")

    # Preserve the product semantics of the two shared E2E schools:
    # demo-school remains the formal read-only demo, sandbox-school remains the
    # unentitled negative case. Mutating IAM journeys use a dedicated writable school.
    db = get_sessionmaker()()
    try:
        ensure_tenant(db, IAM_E2E_TENANT)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # Global Permission rows are reconciled by the production B3 Authority,
    # never by tenant role copy/save/activation code and never by test-only inserts.
    catalog_reconciliation = reconcile_permission_catalog(
        source="CONTROL_PLANE_SCHOOL_IAM_E2E",
    )
    if catalog_reconciliation.get("missingAfterReconcile") != 0:
        raise SystemExit("Permission Catalog reconciliation did not converge")

    # Make entitlement state explicit. Demo and the dedicated IAM school own
    # Internship; sandbox remains the not-entitled negative case.
    for tid in (DEMO_TID, SANDBOX_TID, IAM_E2E_TID):
        platform_service.put_config_json(tid, "TENANT_META", "-", {
            "packageCode": "professional",
            "status": "active",
            "environment": "test",
        })
    platform_service.put_config_json(DEMO_TID, "FEATURES", "-", {"internship": True})
    platform_service.put_config_json(SANDBOX_TID, "FEATURES", "-", {"internship": False})
    platform_service.put_config_json(IAM_E2E_TID, "FEATURES", "-", {"internship": True})

    convergence = shadow.converge_published_system_templates(
        actor_user_id=None,
        source_commit_sha=head_sha,
    )
    universe = set(shadow.active_tenant_permission_codes())
    if TARGET_PERMISSION not in universe:
        raise SystemExit(f"target permission missing from school-assignable B8 universe: {TARGET_PERMISSION}")
    if any(code.startswith("platform.") or code.startswith("enterprise.") for code in universe):
        raise SystemExit("school-assignable B8 universe contains forbidden PLATFORM/enterprise permission")

    db = get_sessionmaker()()
    try:
        demo_target = _ensure_teacher(
            db,
            tenant_id=DEMO_TID,
            login_name=DEMO_TARGET_LOGIN,
            real_name="Demo IAM只读验证教师",
        )
        iam_target = _ensure_teacher(
            db,
            tenant_id=IAM_E2E_TID,
            login_name=IAM_TARGET_LOGIN,
            real_name="IAM权限变更验证教师",
        )

        demo_admin = db.scalars(select(User).where(
            User.tenant_id == DEMO_TID,
            User.login_name == "admin",
            User.is_deleted.is_(False),
        )).first()
        sandbox_admin = db.scalars(select(User).where(
            User.tenant_id == SANDBOX_TID,
            User.login_name == "admin2",
            User.is_deleted.is_(False),
        )).first()
        iam_admin = db.scalars(select(User).where(
            User.tenant_id == IAM_E2E_TID,
            User.login_name == IAM_E2E_TENANT["login"],
            User.is_deleted.is_(False),
        )).first()
        if demo_admin is None or sandbox_admin is None or iam_admin is None:
            raise SystemExit("Playwright seed did not create all required school admins")
        db.commit()

        demo_target_id = int(demo_target.id)
        iam_target_id = int(iam_target.id)
        demo_admin_id = int(demo_admin.id)
        sandbox_admin_id = int(sandbox_admin.id)
        iam_admin_id = int(iam_admin.id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    fixture = {
        "headSha": head_sha,
        "demoTenantId": str(DEMO_TID),
        "sandboxTenantId": str(SANDBOX_TID),
        "iamTenantId": str(IAM_E2E_TID),
        "iamTenantCode": IAM_E2E_TENANT["code"],
        "iamAdminLogin": IAM_E2E_TENANT["login"],
        "demoAdminUserId": str(demo_admin_id),
        "sandboxAdminUserId": str(sandbox_admin_id),
        "iamAdminUserId": str(iam_admin_id),
        "targetUserId": str(demo_target_id),
        "targetLogin": DEMO_TARGET_LOGIN,
        "demoTargetUserId": str(demo_target_id),
        "demoTargetLogin": DEMO_TARGET_LOGIN,
        "iamTargetUserId": str(iam_target_id),
        "iamTargetLogin": IAM_TARGET_LOGIN,
        "targetPermission": TARGET_PERMISSION,
        "demoInternshipEntitled": True,
        "sandboxInternshipEntitled": False,
        "iamInternshipEntitled": True,
        "tenantPermissionUniverseCount": len(universe),
        "permissionCatalogReconciliation": catalog_reconciliation,
        "templateConvergence": convergence,
    }
    path = Path(__file__).resolve().parents[2] / "e2e" / "runtime-fixtures" / "control-plane-school-iam.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(fixture, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
