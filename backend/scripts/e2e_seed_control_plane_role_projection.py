"""Seed the thirteen required role projections plus the Product-IAM platform root.

Safety is inherited from ``e2e_seed_playwright_tenants.assert_safe_target``:
only a local database whose name contains ``e2e`` or ``test`` is accepted.
The script creates identities and role/scope bindings only; all permissions for
SYSTEM roles continue to come from published RoleTemplate authority.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from sqlalchemy import select

from e2e_seed_playwright_tenants import assert_safe_target
from app.api.v1 import auth_browser
from app.core.permissions import _match
from app.core.security import create_access_token, hash_password
from app.core.token_store import consume_refresh, issue_refresh
from app.db.session import get_sessionmaker
from app.models import (
    CustomRoleSource,
    Permission,
    Role,
    RoleAssignmentScope,
    RolePermission,
    RoleTemplate,
    Tenant,
    User,
    UserRole,
)
from app.services import auth_service_db
from app.services import system_role_shadow_service as shadow

SCHOOL_TENANT_ID = 1000000000000000003
IAM_GOLDEN_TENANT_ID = 1000000000000000011
PLATFORM_TENANT_ID = 1000000000000000000
SCHOOL_LOGIN = "admin"
IAM_GOLDEN_LOGIN = "iam_admin"
PASSWORD = "E2eRole@2026"
CUSTOM_ROLE = "E2E_CUSTOM_MENU"
CUSTOM_PERMISSION = "internship.recruitment.view"
LEGACY_PRESERVED_PERMISSION = "system.role.view"

SCHOOL_ROLES = {
    "SCHOOL_ADMIN": ("学校管理员", "SCHOOL", 0),
    "SYS_ADMIN": ("系统管理员", "SCHOOL", 0),
    "ACADEMIC_ADMIN": ("教务管理员", "SCHOOL", 0),
    "COLLEGE_ADMIN": ("学院管理员", "COLLEGE", 990001),
    "ACADEMIC_TEACHER": ("任课教师", "SCHOOL", 0),
    "STUDENT_AFFAIRS": ("学工管理员", "SCHOOL", 0),
    "COUNSELOR": ("辅导员", "COLLEGE", 990001),
    "INTERN_MENTOR": ("实习指导教师", "STUDENT", 990101),
    "GRADUATION_ADMIN": ("毕业设计管理员", "SCHOOL", 0),
    CUSTOM_ROLE: ("E2E 自定义菜单角色", "COLLEGE", 990001),
}

PLATFORM_ROLES = {
    "PLATFORM_COMMERCIAL": ("e2e_platform_commercial", "平台商务"),
    "PLATFORM_OPERATIONS": ("e2e_platform_operations", "平台运维"),
    "PLATFORM_SECURITY_AUDITOR": ("e2e_platform_security", "平台安全审计"),
}


def _production_surfaces() -> list[dict]:
    path = Path(__file__).resolve().parents[2] / "shared" / "contracts" / "navigation-surface-contract.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        item for item in (payload.get("surfaces") or [])
        if item.get("path") and not item.get("hidden") and not item.get("disabled")
        and str(item.get("status") or "") in {"implemented", "partial"}
    ]


def _surface_allowed(item: dict, patterns: list[str]) -> bool:
    permission_key = str(item.get("permissionKey") or "").strip()
    permission_any = [str(code) for code in (item.get("permissionAny") or []) if str(code).strip()]
    permission_all = [str(code) for code in (item.get("permissionAll") or []) if str(code).strip()]
    if permission_key and not _match(permission_key, patterns):
        return False
    if permission_any and not any(_match(code, patterns) for code in permission_any):
        return False
    if permission_all and not all(_match(code, patterns) for code in permission_all):
        return False
    if permission_key or permission_any or permission_all:
        return True
    # Production frontend is fail-closed for unguarded business entries: only
    # the staff workbench is a public authenticated menu surface.
    return not item.get("platformOnly") and item.get("groupKey") == "workbench"


def _projection_expectation(*, plane: str, role_code: str, patterns: list[str]) -> dict:
    surfaces = _production_surfaces()
    platform = plane == "PLATFORM"
    same_plane = [item for item in surfaces if bool(item.get("platformOnly")) == platform]
    visible = [item for item in same_plane if _surface_allowed(item, patterns)]
    hidden = [
        item for item in same_plane
        if (item.get("permissionKey") or item.get("permissionAny") or item.get("permissionAll"))
        and not _surface_allowed(item, patterns)
    ]

    preferred = next((item for item in visible if item.get("groupKey") not in {"workbench"}), None)
    preferred = preferred or (visible[0] if visible else None)
    denied = hidden[0] if hidden else next(
        item for item in surfaces if bool(item.get("platformOnly")) != platform
    )
    visible_groups = sorted({str(item.get("groupLabel")) for item in visible if item.get("groupLabel")})
    if not platform and "工作台" not in visible_groups:
        visible_groups.insert(0, "工作台")
    school_visible_group = {
        "SCHOOL_ADMIN": "学工中心",
        "SYS_ADMIN": "系统管理",
        "ACADEMIC_ADMIN": "教务中心",
        "COLLEGE_ADMIN": "学工中心",
        "ACADEMIC_TEACHER": "教务中心",
        "STUDENT_AFFAIRS": "学工中心",
        "COUNSELOR": "学工中心",
        "INTERN_MENTOR": "岗位实习中心",
        "GRADUATION_ADMIN": "毕业设计中心",
        CUSTOM_ROLE: "岗位实习中心",
    }
    return {
        "visibleGroup": "平台运营" if platform else school_visible_group[role_code],
        "hiddenGroup": "工作台" if platform else "平台运营",
        "visiblePath": str((preferred or {}).get("path") or "/admin/platform") if platform else "/workbench",
        "hiddenPath": str(denied.get("path") or ("/workbench" if platform else "/admin/platform/product-iam")),
        "visibleGroupCount": len(visible_groups),
    }


def _browser_session(db, user: User, *, role_code: str, channel: str, client_type: str,
                     head_sha: str, patterns: list[str], platform_mfa: bool = False,
                     session_suffix: str = "") -> dict:
    contexts = auth_service_db._role_contexts(db, user)
    context = next((item for item in contexts if item.get("roleCode") == role_code), None)
    if context is None:
        raise RuntimeError(f"real auth context missing for {role_code}")
    suffix = f"-{session_suffix.strip()}" if session_suffix.strip() else ""
    browser_session_id = f"w12-{role_code.lower().replace('_', '-')}-{head_sha[:12]}{suffix}"
    login_result = auth_service_db._login_result(db, user, context, contexts, client_type)
    if platform_mfa:
        claims = consume_refresh(str(login_result.get("refreshToken") or ""))
        if not claims:
            raise RuntimeError(f"real refresh claims missing for {role_code}")
        claims.update({"auth_time": int(time.time()), "amr": ["pwd", "mfa"], "acr": "urn:e2e:mfa"})
        login_result["accessToken"] = create_access_token(dict(claims))
        login_result["refreshToken"] = issue_refresh(dict(claims))
    payload = auth_browser._sessionize_payload(
        {"data": login_result},
        browser_channel=channel,
        browser_session_id=browser_session_id,
    )
    refresh_token = str((payload.get("data") or {}).get("refreshToken") or "")
    if not refresh_token:
        raise RuntimeError(f"real browser refresh token missing for {role_code}")
    return {
        "roleCode": role_code,
        "userId": str(user.id),
        "plane": "PLATFORM" if channel == "platform" else "SCHOOL",
        "channel": channel,
        "browserSessionId": browser_session_id,
        "refreshToken": refresh_token,
        "expectedDataScope": str(context.get("dataScope") or ""),
        "expectedPermissionCount": len(patterns),
        **_projection_expectation(
            plane="PLATFORM" if channel == "platform" else "SCHOOL",
            role_code=role_code,
            patterns=patterns,
        ),
    }


def _role(db, tenant_id: int, code: str, name: str, role_type: str) -> Role:
    item = db.scalars(select(Role).where(
        Role.tenant_id == tenant_id,
        Role.role_code == code,
    )).first()
    if item is None:
        item = Role(
            tenant_id=tenant_id,
            role_code=code,
            role_name=name,
            role_type=role_type,
            status="ACTIVE",
        )
        db.add(item)
        db.flush()
    else:
        item.role_name = name
        item.role_type = role_type
        item.status = "ACTIVE"
        item.is_deleted = False
    return item


def _link(db, tenant_id: int, user_id: int, role: Role) -> UserRole:
    item = db.scalars(select(UserRole).where(
        UserRole.tenant_id == tenant_id,
        UserRole.user_id == user_id,
        UserRole.role_id == role.id,
    )).first()
    if item is None:
        item = UserRole(
            tenant_id=tenant_id,
            user_id=user_id,
            role_id=role.id,
            status="ACTIVE",
        )
        db.add(item)
        db.flush()
    else:
        item.status = "ACTIVE"
        item.is_deleted = False
    return item


def _scope(db, tenant_id: int, user_id: int, role: Role, link: UserRole,
           scope_type: str, scope_id: int) -> None:
    item = db.scalars(select(RoleAssignmentScope).where(
        RoleAssignmentScope.tenant_id == tenant_id,
        RoleAssignmentScope.user_role_id == link.id,
        RoleAssignmentScope.scope_type == scope_type,
        RoleAssignmentScope.scope_id == scope_id,
    )).first()
    if item is None:
        db.add(RoleAssignmentScope(
            tenant_id=tenant_id,
            user_role_id=int(link.id),
            user_id=user_id,
            role_code=role.role_code,
            scope_type=scope_type,
            scope_id=scope_id,
            scope_name_snapshot=f"E2E {scope_type} {scope_id}",
            source_type="E2E_ROLE_PROJECTION",
            status="ACTIVE",
            reason="W12 isolated browser role projection",
        ))
    else:
        item.user_id = user_id
        item.role_code = role.role_code
        item.status = "ACTIVE"
        item.is_deleted = False


def _custom_permission(db, role: Role, *, tenant_id: int = SCHOOL_TENANT_ID) -> None:
    permission = db.scalars(select(Permission).where(
        Permission.permission_code == CUSTOM_PERMISSION,
    )).first()
    if permission is None:
        raise RuntimeError(f"Permission Catalog was not reconciled: {CUSTOM_PERMISSION}")
    link = db.scalars(select(RolePermission).where(
        RolePermission.tenant_id == tenant_id,
        RolePermission.role_id == role.id,
        RolePermission.permission_id == permission.id,
    )).first()
    if link is None:
        db.add(RolePermission(
            tenant_id=tenant_id,
            role_id=int(role.id),
            permission_id=int(permission.id),
            status="ACTIVE",
        ))
    else:
        link.status = "ACTIVE"
        link.is_deleted = False

    legacy_permission = db.scalars(select(Permission).where(
        Permission.permission_code == LEGACY_PRESERVED_PERMISSION,
    )).first()
    if legacy_permission is None:
        raise RuntimeError(f"alias backfill missing preserved Permission row: {LEGACY_PRESERVED_PERMISSION}")
    legacy_link = db.scalars(select(RolePermission).where(
        RolePermission.tenant_id == tenant_id,
        RolePermission.role_id == role.id,
        RolePermission.permission_id == legacy_permission.id,
    )).first()
    if legacy_link is None:
        db.add(RolePermission(
            tenant_id=tenant_id,
            role_id=int(role.id),
            permission_id=int(legacy_permission.id),
            status="ACTIVE",
        ))
    else:
        legacy_link.status = "ACTIVE"
        legacy_link.is_deleted = False

    source_template = db.scalars(select(RoleTemplate).where(
        # Published RoleTemplate authority lives in the global governance
        # tenant (0); platform operator identities use PLATFORM_TENANT_ID.
        RoleTemplate.tenant_id == shadow.PLATFORM_TENANT,
        RoleTemplate.template_code == "ACADEMIC_ADMIN",
        RoleTemplate.publish_status == "PUBLISHED",
        RoleTemplate.status == "ACTIVE",
        RoleTemplate.is_deleted.is_(False),
    ).order_by(RoleTemplate.template_version.desc(), RoleTemplate.id.desc()).limit(1)).first()
    if source_template is None:
        raise RuntimeError("published ACADEMIC_ADMIN template missing for pinned custom-role proof")

    source = db.scalars(select(CustomRoleSource).where(
        CustomRoleSource.tenant_id == tenant_id,
        CustomRoleSource.role_code == CUSTOM_ROLE,
    )).first()
    payload = {"items": [CUSTOM_PERMISSION, LEGACY_PRESERVED_PERMISSION]}
    if source is None:
        db.add(CustomRoleSource(
            tenant_id=tenant_id,
            role_id=int(role.id),
            role_code=CUSTOM_ROLE,
            source_template_code="ACADEMIC_ADMIN",
            source_template_version=int(source_template.template_version or 0),
            permission_codes_json=payload,
            drift_json={"pinned": True, "automaticUpgrade": False},
            status="ACTIVE",
        ))
    else:
        source.role_id = int(role.id)
        source.source_template_code = "ACADEMIC_ADMIN"
        source.source_template_version = int(source_template.template_version or 0)
        source.permission_codes_json = payload
        source.drift_json = {"pinned": True, "automaticUpgrade": False}
        source.status = "ACTIVE"
        source.is_deleted = False


def _platform_user(db, code: str, login: str, name: str) -> User:
    item = db.scalars(select(User).where(
        User.tenant_id == PLATFORM_TENANT_ID,
        User.login_name == login,
    )).first()
    if item is None:
        item = User(
            tenant_id=PLATFORM_TENANT_ID,
            login_name=login,
            real_name=name,
            password_hash=hash_password(PASSWORD),
            user_type="PLATFORM_OP",
            status="ACTIVE",
            must_change_password=False,
        )
        db.add(item)
        db.flush()
    else:
        item.password_hash = hash_password(PASSWORD)
        item.user_type = "PLATFORM_OP"
        item.status = "ACTIVE"
        item.must_change_password = False
        item.is_deleted = False
    role = _role(db, PLATFORM_TENANT_ID, code, name, "SYSTEM")
    _link(db, PLATFORM_TENANT_ID, int(item.id), role)
    return item


def _platform_root(db) -> User:
    login = "e2e_platform_owner"
    item = db.scalars(select(User).where(
        User.tenant_id == PLATFORM_TENANT_ID,
        User.login_name == login,
    )).first()
    if item is None:
        item = User(
            tenant_id=PLATFORM_TENANT_ID,
            login_name=login,
            real_name="E2E 平台超级管理员",
            password_hash=hash_password(PASSWORD),
            user_type="PLATFORM_SUPER_ADMIN",
            status="ACTIVE",
            must_change_password=False,
        )
        db.add(item)
        db.flush()
    else:
        item.password_hash = hash_password(PASSWORD)
        item.user_type = "PLATFORM_SUPER_ADMIN"
        item.status = "ACTIVE"
        item.must_change_password = False
        item.is_deleted = False
    return item


def main() -> int:
    assert_safe_target()
    head_sha = str(os.getenv("E2E_EXPECTED_SHA") or os.getenv("GITHUB_SHA") or "").strip()
    if len(head_sha) < 7:
        raise RuntimeError("E2E_EXPECTED_SHA/GITHUB_SHA is required")
    db = get_sessionmaker()()
    try:
        school_user = db.scalars(select(User).where(
            User.tenant_id == SCHOOL_TENANT_ID,
            User.login_name == SCHOOL_LOGIN,
            User.is_deleted.is_(False),
        )).first()
        platform_tenant = db.get(Tenant, PLATFORM_TENANT_ID)
        if school_user is None:
            raise RuntimeError("run e2e_seed_playwright_tenants.py first")
        if platform_tenant is None:
            platform_tenant = Tenant(
                id=PLATFORM_TENANT_ID,
                tenant_code="platform",
                school_name="平台运营中心",
                short_name="平台",
                status="ACTIVE",
            )
            db.add(platform_tenant)
            db.flush()

        school_contexts = []
        for code, (name, scope_type, scope_id) in SCHOOL_ROLES.items():
            role = _role(db, SCHOOL_TENANT_ID, code, name, "CUSTOM" if code == CUSTOM_ROLE else "SYSTEM")
            link = _link(db, SCHOOL_TENANT_ID, int(school_user.id), role)
            _scope(db, SCHOOL_TENANT_ID, int(school_user.id), role, link, scope_type, scope_id)
            if code == CUSTOM_ROLE:
                _custom_permission(db, role)
            school_contexts.append({"roleCode": code, "roleId": str(role.id), "scopeType": scope_type})

        # Mutating Golden Journeys run in the dedicated IAM test school. The
        # demo-school tenant is intentionally read-only and remains suitable
        # only for the non-mutating 14-role projection matrix.
        iam_golden_user = db.scalars(select(User).where(
            User.tenant_id == IAM_GOLDEN_TENANT_ID,
            User.login_name == IAM_GOLDEN_LOGIN,
            User.is_deleted.is_(False),
        )).first()
        if iam_golden_user is None:
            raise RuntimeError("run e2e_seed_control_plane_school_iam.py first")
        iam_admin_role = _role(db, IAM_GOLDEN_TENANT_ID, "SCHOOL_ADMIN", "学校管理员", "SYSTEM")
        iam_admin_link = _link(db, IAM_GOLDEN_TENANT_ID, int(iam_golden_user.id), iam_admin_role)
        _scope(
            db, IAM_GOLDEN_TENANT_ID, int(iam_golden_user.id),
            iam_admin_role, iam_admin_link, "SCHOOL", 0,
        )
        iam_custom_role = _role(
            db, IAM_GOLDEN_TENANT_ID, CUSTOM_ROLE, "E2E 自定义菜单角色", "CUSTOM",
        )
        iam_custom_link = _link(db, IAM_GOLDEN_TENANT_ID, int(iam_golden_user.id), iam_custom_role)
        _scope(
            db, IAM_GOLDEN_TENANT_ID, int(iam_golden_user.id),
            iam_custom_role, iam_custom_link, "COLLEGE", 990001,
        )
        _custom_permission(db, iam_custom_role, tenant_id=IAM_GOLDEN_TENANT_ID)

        platform_users = []
        platform_user_rows = []
        for code, (login, name) in PLATFORM_ROLES.items():
            user = _platform_user(db, code, login, name)
            platform_user_rows.append((code, user))
            platform_users.append({"roleCode": code, "login": login, "userId": str(user.id)})
        platform_root = _platform_root(db)
        platform_users.append({
            "roleCode": "PLATFORM_SUPER_ADMIN",
            "login": platform_root.login_name,
            "userId": str(platform_root.id),
        })
        db.commit()

        sandbox_admin = db.scalars(select(User).where(
            User.tenant_id == 1000000000000000007,
            User.login_name == "admin2",
            User.is_deleted.is_(False),
        )).first()
        if sandbox_admin is None:
            raise RuntimeError("sandbox-school admin missing for cross-tenant browser proof")

        sessions = []
        for code, _meta in SCHOOL_ROLES.items():
            if code == CUSTOM_ROLE:
                patterns = [CUSTOM_PERMISSION, LEGACY_PRESERVED_PERMISSION]
            else:
                patterns = list(shadow.published_system_role_permissions(db, code))
            if not patterns:
                raise RuntimeError(f"published RoleTemplate runtime is empty for {code}")
            sessions.append(_browser_session(
                db,
                school_user,
                role_code=code,
                channel="staff",
                client_type="PC",
                head_sha=head_sha,
                patterns=patterns,
            ))
        from app.modules.platform.services.platform_access_governance_legacy import DUTY_CAPABILITIES
        for code, user in platform_user_rows:
            patterns = sorted(f"platform.{item}" for item in DUTY_CAPABILITIES[code])
            sessions.append(_browser_session(
                db,
                user,
                role_code=code,
                channel="platform",
                client_type="PLATFORM_PC",
                head_sha=head_sha,
                patterns=patterns,
            ))
        sessions.append(_browser_session(
            db,
            platform_root,
            role_code="PLATFORM_SUPER_ADMIN",
            channel="platform",
            client_type="PLATFORM_PC",
            head_sha=head_sha,
            patterns=["*"],
            platform_mfa=True,
        ))
        school_admin_golden_session = _browser_session(
            db,
            iam_golden_user,
            role_code="SCHOOL_ADMIN",
            channel="staff",
            client_type="PC",
            head_sha=head_sha,
            patterns=list(shadow.published_system_role_permissions(db, "SCHOOL_ADMIN")),
            session_suffix="golden",
        )
        custom_role_golden_session = _browser_session(
            db,
            iam_golden_user,
            role_code=CUSTOM_ROLE,
            channel="staff",
            client_type="PC",
            head_sha=head_sha,
            patterns=[CUSTOM_PERMISSION, LEGACY_PRESERVED_PERMISSION],
            session_suffix="golden",
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    fixture = {
        "headSha": head_sha,
        "schoolTenantCode": "iam-e2e-school",
        "schoolLogin": IAM_GOLDEN_LOGIN,
        "schoolPassword": "123456",
        "schoolContexts": school_contexts,
        "platformUsers": platform_users,
        "customPermission": CUSTOM_PERMISSION,
        "customPermissionPath": next(
            item["path"] for item in _production_surfaces()
            if CUSTOM_PERMISSION in (item.get("permissionCodes") or [])
        ),
        "legacyPreservedPermission": LEGACY_PRESERVED_PERMISSION,
        "schoolAdminGoldenSession": school_admin_golden_session,
        "customRoleGoldenSession": custom_role_golden_session,
        "crossTenantUserId": str(sandbox_admin.id),
        "sessions": sessions,
    }
    target = Path(__file__).resolve().parents[2] / "e2e" / "runtime-fixtures" / "control-plane-role-projection.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(fixture, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "headSha": head_sha,
        "roleCount": len(sessions),
        "roles": [item["roleCode"] for item in sessions],
        "realSignedBrowserSessions": True,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
