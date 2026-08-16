import json
from pathlib import Path

from sqlalchemy import select

from app.core.school_admin_permission_resolver import (
    catalog_school_admin_permissions,
    published_school_admin_permissions,
    resolve_school_admin_permissions,
    school_admin_cutover_preflight,
)
from app.services import system_role_shadow_service as shadow


def test_school_admin_retirement_contract_freezes_fail_closed_cutover():
    root = Path(__file__).resolve().parents[2]
    contract = json.loads(
        (root / "shared/contracts/control-plane/school-admin-wildcard-retirement.json")
        .read_text(encoding="utf-8")
    )
    assert contract["card"] == "CTRL-B8-WILDCARD-RETIREMENT"
    assert contract["roleCode"] == "SCHOOL_ADMIN"
    assert contract["wildcardCode"] == "*"
    assert contract["runtimeResolver"] == "PUBLISHED_TENANT_ROLE_TEMPLATE"
    assert contract["requireExactNormalizedSnapshot"] is True
    assert contract["dbFailurePolicy"] == "FAIL_CLOSED"
    assert contract["legacyWildcardBaseline"] == "SHADOW_ONLY"


def test_school_admin_catalog_universe_is_explicit_tenant_only():
    codes = set(catalog_school_admin_permissions())
    assert len(codes) > 400
    assert "*" not in codes
    assert "systemAdmin.role.view" in codes
    assert "internship.recruitment.view" in codes
    assert not any(code.startswith("platform.") for code in codes)
    assert not any(code.startswith("enterprise.") for code in codes)


def test_school_admin_preflight_uses_latest_published_normalized_snapshot(db_mode):
    from app.db.session import get_sessionmaker

    convergence = shadow.converge_published_system_templates(
        actor_user_id=9811,
        source_commit_sha="school-admin-retirement-preflight",
    )
    assert convergence["tenantPermissionUniverseCount"] == len(catalog_school_admin_permissions())

    db = get_sessionmaker()()
    try:
        assert set(published_school_admin_permissions(db)) == set(catalog_school_admin_permissions())
    finally:
        db.close()

    proof = school_admin_cutover_preflight()
    assert proof["exactSnapshot"] is True
    assert proof["explicitPermissionCount"] == proof["tenantPermissionUniverseCount"]
    assert proof["explicitPermissionCount"] > 400
    assert proof["containsRuntimeWildcard"] is False
    assert proof["platformPermissionCount"] == 0
    assert proof["enterprisePermissionCount"] == 0
    assert proof["dbFailurePolicy"] == "FAIL_CLOSED"


def test_school_admin_resolver_fails_closed_on_normalized_template_drift(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.permission_governance import RoleTemplate, RoleTemplatePermission

    shadow.converge_published_system_templates(
        actor_user_id=9812,
        source_commit_sha="school-admin-retirement-drift",
    )
    db = get_sessionmaker()()
    try:
        template = db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.template_code == "SCHOOL_ADMIN",
            RoleTemplate.publish_status == "PUBLISHED",
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc(), RoleTemplate.id.desc()).limit(1)).first()
        assert template is not None
        row = db.scalars(select(RoleTemplatePermission).where(
            RoleTemplatePermission.role_template_id == int(template.id),
            RoleTemplatePermission.is_deleted.is_(False),
        ).limit(1)).first()
        assert row is not None
        row.is_deleted = True
        db.commit()
    finally:
        db.close()

    assert resolve_school_admin_permissions() == ()


def test_school_admin_preflight_does_not_retire_runtime_wildcard_yet(db_mode):
    from app.core.permissions import ROLE_PERMISSIONS

    shadow.converge_published_system_templates(
        actor_user_id=9813,
        source_commit_sha="school-admin-retirement-lock",
    )
    proof = school_admin_cutover_preflight()
    assert proof["exactSnapshot"] is True
    assert ROLE_PERMISSIONS["SCHOOL_ADMIN"] == {"*"}
