from sqlalchemy import select

from app.models import Role
from app.models.permission_governance import RoleTemplate, RoleTemplatePermission
from app.modules.system_admin.services import school_iam_authority_projection_service as svc
from app.services.system_role_shadow_service import published_system_role_permissions

TID = 1000000000000000001


def test_school_iam_catalog_never_exposes_enterprise_permissions_as_assignable(monkeypatch):
    monkeypatch.setattr(svc, "load_permission_catalog", lambda: {
        "entries": [
            {"permissionCode": "internship.recruitment.manage", "plane": "TENANT", "tenantAssignable": True, "customRoleAssignable": True, "lifecycle": "ACTIVE"},
            {"permissionCode": "enterprise.internship.application.decide", "plane": "TENANT", "tenantAssignable": False, "customRoleAssignable": False, "lifecycle": "ACTIVE"},
        ],
        "_byCode": {
            "internship.recruitment.manage": {},
            "enterprise.internship.application.decide": {},
        },
    })
    result = svc.assignable_catalog()
    codes = {item["permissionCode"] for item in result["customRoleAssignablePermissions"]}
    assert "internship.recruitment.manage" in codes
    assert "enterprise.internship.application.decide" not in codes
    assert result["enterprisePermissionsVisibleButSchoolAssignable"] is False
    assert result["systemRoleAuthority"] == "PUBLISHED_TENANT_ROLE_TEMPLATE"
    assert result["templatePermissionAuthority"] == "ROLE_TEMPLATE_PERMISSION_NORMALIZED"


def test_school_iam_router_defaults_to_recruitment_manage_explain():
    from app.modules.system_admin.routers import school_iam_router
    source = __import__("inspect").getsource(school_iam_router.iam_access_explain)
    assert "internship" in source
    assert "internship.recruitment.manage" in source


def test_school_iam_system_role_reads_published_template_not_static_wildcard(db_mode):
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        role = Role(
            tenant_id=TID,
            role_code="SCHOOL_ADMIN",
            role_name="学校管理员",
            role_type="SYSTEM",
            status="ACTIVE",
        )
        codes = svc._role_permissions(db, TID, role)
        assert codes == list(published_system_role_permissions(db, "SCHOOL_ADMIN"))
        assert "*" not in codes
        assert len(codes) > 400
        governance = svc._role_governance(db, TID, role, codes)
        provenance = governance["templateProvenance"]
        assert provenance["authority"] == "PUBLISHED_TENANT_ROLE_TEMPLATE"
        assert provenance["permissionAuthority"] == "ROLE_TEMPLATE_PERMISSION_NORMALIZED"
        assert provenance["provenanceStatus"] == "PUBLISHED_EXPLICIT"
        assert governance["drift"]["b8RetirementPending"] is False
        assert governance["drift"]["wildcards"] == []
        assert governance["templateImpact"]["status"] == "CURRENT_PUBLISHED_AUTHORITY"
    finally:
        db.close()


def test_school_iam_template_permissions_ignore_compatibility_json_as_authority(db_mode):
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        template = db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.template_code == "SCHOOL_ADMIN",
            RoleTemplate.publish_status == "PUBLISHED",
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc())).first()
        assert template is not None
        expected = svc._template_permissions(db, template)
        assert len(expected) > 400

        template.permission_ceiling_json = {
            "items": ["platform.fake.must-not-authorize"],
            "permissionDigest": "forged-compatibility-json",
        }
        db.commit()

        actual = svc._template_permissions(db, template)
        assert actual == expected
        assert "platform.fake.must-not-authorize" not in actual
    finally:
        db.close()


def test_school_iam_template_permissions_fail_closed_without_normalized_rows(db_mode):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        template = db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.template_code == "SCHOOL_ADMIN",
            RoleTemplate.publish_status == "PUBLISHED",
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc())).first()
        assert template is not None
        rows = list(db.scalars(select(RoleTemplatePermission).where(
            RoleTemplatePermission.role_template_id == template.id,
            RoleTemplatePermission.is_deleted.is_(False),
        )).all())
        assert rows
        for row in rows:
            row.is_deleted = True
        db.commit()

        try:
            svc._template_permissions(db, template)
        except AppException as exc:
            assert exc.code == "B7_NORMALIZED_TEMPLATE_REQUIRED"
        else:
            raise AssertionError("normalized RoleTemplatePermission loss must fail closed")
    finally:
        db.close()


def test_school_iam_template_catalog_exposes_normalized_published_truth(db_mode, monkeypatch):
    monkeypatch.setattr(svc, "_tenant_id", lambda: TID)
    rows = svc.template_catalog()
    school_admin = next(item for item in rows if item["templateCode"] == "SCHOOL_ADMIN")
    assert school_admin["publishStatus"] == "PUBLISHED"
    assert school_admin["templatePlane"] == "TENANT"
    assert school_admin["templateCategory"] == "SYSTEM_ROLE"
    assert school_admin["permissionAuthority"] == "ROLE_TEMPLATE_PERMISSION_NORMALIZED"
    assert "*" not in school_admin["permissions"]
    assert len(school_admin["permissions"]) > 400
