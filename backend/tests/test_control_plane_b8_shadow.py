import json
from pathlib import Path

from sqlalchemy import select

from app.core.permission_catalog import load_permission_catalog, permission_meta, runtime_wildcard_probe_codes
from app.modules.platform.services import platform_product_iam_service as product_iam
from app.services import system_role_shadow_service as shadow


def test_b8_contract_freezes_four_resolvers_and_tenant_only_shadow():
    root = Path(__file__).resolve().parents[2]
    contract = json.loads((root / "shared/contracts/control-plane/b8-system-shadow.json").read_text(encoding="utf-8"))
    assert contract["shadowScope"] == "TENANT_SYSTEM_ROLES_ONLY"
    assert contract["resolvers"] == [
        "OLD_BUILTIN_ROLE_PERMISSIONS",
        "NEW_PUBLISHED_TENANT_ROLE_TEMPLATE",
        "CUSTOM_ROLE_PERMISSION",
        "PLATFORM_WORKFORCE",
    ]
    assert contract["mismatchPolicy"] == "ZERO_UNEXPLAINED_DRIFT"
    assert contract["customTemplateFallback"] is False
    assert contract["platformMayEnterSchoolTemplate"] is False


def test_b8_concrete_catalog_materializes_all_previously_legacy_concrete_codes():
    catalog = load_permission_catalog()
    extension = catalog["b8ConcreteCatalog"]
    assert extension["count"] == 449
    assert runtime_wildcard_probe_codes() == {"*"}
    for code in (
        "academicAffairs.grade.view",
        "studentAffairs.risk.handle",
        "graduationDesign.defense.score",
        "internship.archive.force",
        "systemAdmin.role.view",
        "workflow.task.view",
    ):
        meta = permission_meta(code)
        assert meta is not None
        assert meta["plane"] == "TENANT"
        assert meta["lifecycle"] == "ACTIVE"
        assert meta["tenantAssignable"] is True
        assert meta["catalogSource"] == "B8_CONCRETE_CUTOVER"


def test_active_tenant_universe_is_complete_school_assignable_only():
    codes = shadow.active_tenant_permission_codes()
    assert len(codes) > 400
    assert not any(code.startswith("platform.") for code in codes)
    assert not any(code.startswith("enterprise.") for code in codes)
    assert "internship.recruitment.view" in codes
    assert "academicAffairs.grade.view" in codes
    assert "studentAffairs.risk.handle" in codes
    assert "systemAdmin.role.view" in codes


def test_b8_publishes_immutable_explicit_tenant_templates_then_shadow_is_zero(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.permission_governance import RoleTemplate, RoleTemplatePermission

    convergence = shadow.converge_published_system_templates(
        actor_user_id=9801,
        source_commit_sha="b8-shadow-test-head",
    )
    assert convergence["tenantPermissionUniverseCount"] == len(shadow.active_tenant_permission_codes())
    assert convergence["tenantPermissionUniverseCount"] > 400
    assert convergence["createdCount"] > 0

    report = shadow.shadow_system_roles()
    assert report["resolverSet"] == [
        "OLD_BUILTIN_ROLE_PERMISSIONS",
        "NEW_PUBLISHED_TENANT_ROLE_TEMPLATE",
        "CUSTOM_ROLE_PERMISSION",
        "PLATFORM_WORKFORCE",
    ]
    assert report["shadowScope"] == "TENANT_SYSTEM_ROLES_ONLY"
    assert report["schoolAssignableTenantOnly"] is True
    assert report["unexplainedDriftCount"] == 0
    assert report["planeViolationCount"] == 0
    assert report["zeroUnexplainedDrift"] is True
    assert report["customFallsBackToTemplate"] is False
    assert report["platformEntersSchoolTemplate"] is False
    assert report["enterpriseEntersSchoolTemplate"] is False

    db = get_sessionmaker()()
    try:
        school_admin = db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.template_code == "SCHOOL_ADMIN",
            RoleTemplate.publish_status == "PUBLISHED",
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc())).first()
        assert school_admin is not None
        rows = list(db.scalars(select(RoleTemplatePermission).where(
            RoleTemplatePermission.role_template_id == school_admin.id,
            RoleTemplatePermission.is_deleted.is_(False),
        )).all())
        codes = {row.permission_code for row in rows}
        assert codes == set(shadow.active_tenant_permission_codes())
        assert not any(code.startswith("platform.") or code.startswith("enterprise.") for code in codes)
        assert (school_admin.wildcard_json or {}).get("runtimeRetired") is False
    finally:
        db.close()


def test_b8_convergence_is_idempotent_and_never_rewrites_published_version(db_mode):
    first = shadow.converge_published_system_templates(actor_user_id=9802, source_commit_sha="b8-idempotent-head")
    second = shadow.converge_published_system_templates(actor_user_id=9802, source_commit_sha="b8-idempotent-head")
    assert first["createdCount"] > 0
    assert second["createdCount"] == 0
    assert set(second["unchangedRoleCodes"]) == set(shadow.delivered_system_role_codes())


def test_custom_resolver_uses_role_permission_only_and_never_falls_back_to_template(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Permission, Role, RolePermission
    from app.models.permission_governance import CustomRoleSource

    tenant_id = 1000000000000000001
    db = get_sessionmaker()()
    try:
        role = Role(tenant_id=tenant_id, role_code="B8_CUSTOM_DIRECT_ONLY", role_name="B8 Custom", role_type="CUSTOM", status="ACTIVE")
        db.add(role)
        db.flush()
        db.add(CustomRoleSource(
            tenant_id=tenant_id,
            role_id=role.id,
            role_code=role.role_code,
            source_template_code="SCHOOL_ADMIN",
            source_template_version=1,
            permission_codes_json={"items": ["internship.recruitment.view"]},
            drift_json={"policy": "DERIVED_PINNED"},
            status="ACTIVE",
        ))
        db.commit()

        assert shadow.custom_role_permission_codes(db, tenant_id=tenant_id, role_id=role.id) == ()
        assert shadow.custom_role_allows(db, tenant_id=tenant_id, role_id=role.id, permission_code="internship.recruitment.view") is False

        permission = db.scalars(select(Permission).where(Permission.permission_code == "internship.recruitment.view")).first()
        if permission is None:
            permission = Permission(permission_code="internship.recruitment.view", permission_name="B8 view", module_code="internship", action="view")
            db.add(permission)
            db.flush()
        db.add(RolePermission(tenant_id=tenant_id, role_id=role.id, permission_id=permission.id, status="ACTIVE"))
        db.commit()
        assert shadow.custom_role_permission_codes(db, tenant_id=tenant_id, role_id=role.id) == ("internship.recruitment.view",)
    finally:
        db.close()


def test_platform_workforce_resolver_is_plane_guarded():
    assert shadow.platform_workforce_allows("PLATFORM_OWNER", "platform.tenant.view") is True
    assert shadow.platform_workforce_allows("PLATFORM_OWNER", "systemAdmin.role.view") is False
    assert shadow.platform_workforce_allows("SCHOOL_ADMIN", "platform.tenant.view") is False


def test_b6_product_iam_snapshot_reads_published_normalized_template_truth(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.permission_governance import RoleTemplate

    shadow.converge_published_system_templates(actor_user_id=9803, source_commit_sha="b8-product-iam-head")
    expected = list(shadow.expected_system_role_permissions("SCHOOL_ADMIN"))
    db = get_sessionmaker()()
    try:
        school_admin = db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.template_code == "SCHOOL_ADMIN",
            RoleTemplate.publish_status == "PUBLISHED",
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc())).first()
        assert school_admin is not None
        school_admin.permission_ceiling_json = {"items": ["platform.fake.must-not-be-authority"]}
        school_admin.permission_digest = None
        db.commit()

        rows = product_iam._published_templates(db)
        item = next(row for row in rows if row["templateCode"] == "SCHOOL_ADMIN")
        assert item["permissionCount"] == len(expected)
        assert item["permissionDigest"] == product_iam._hash(expected)
    finally:
        db.close()
