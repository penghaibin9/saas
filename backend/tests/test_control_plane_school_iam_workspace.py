from sqlalchemy import select

from app.models import Role, User
from app.models.permission_governance import RoleTemplate, RoleTemplatePermission
from app.modules.system_admin.services import school_iam_access_explain_service as access_svc
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


def test_school_iam_router_requires_concrete_domain_context_for_final_explain():
    from app.modules.system_admin.routers import school_iam_router
    source = __import__("inspect").getsource(school_iam_router.iam_access_explain)
    assert "internship" in source
    assert "internship.recruitment.manage" in source
    for field in ("scopeTargetType", "scopeTargetId", "resourceType", "resourceId"):
        assert field in source
    assert "scope_target_type=scopeTargetType" in source
    assert "resource_id=resourceId" in source


def test_school_iam_domain_explain_fails_closed_without_resource_context():
    role = Role(tenant_id=TID, role_code="INTERN_MENTOR", role_name="实习指导教师", role_type="SYSTEM", status="ACTIVE")
    subject = User(
        id=101,
        tenant_id=TID,
        login_name="teacher-101",
        real_name="指导教师",
        password_hash="not-used",
        user_type="TEACHER",
        status="ACTIVE",
    )
    guard = access_svc._domain_guard_for_role(
        tenant_id=TID,
        subject=subject,
        role=role,
        actor={"userId": "db-101", "tenantId": str(TID), "currentRoleCode": "INTERN_MENTOR", "dataScope": "INTERN_STUDENTS"},
        scope_target_type=None,
        scope_target_id=None,
        resource_type=None,
        resource_id=None,
    )
    assert guard["allowed"] is False
    assert guard["reasonCode"] == "RESOURCE_CONTEXT_REQUIRED"
    assert guard["details"]["authority"] == "SCOPE_POLICY_SERVICE"


def test_school_iam_domain_explain_reuses_relation_and_scope_policy_authorities(monkeypatch):
    role = Role(tenant_id=TID, role_code="INTERN_MENTOR", role_name="实习指导教师", role_type="SYSTEM", status="ACTIVE")
    subject = User(
        id=102,
        tenant_id=TID,
        login_name="teacher-102",
        real_name="指导教师",
        password_hash="not-used",
        user_type="TEACHER",
        status="ACTIVE",
    )
    seen = {}

    def fake_relation(actor, *, resource_type, resource):
        seen["relation"] = (actor, resource_type, resource)
        return {"allowed": True, "reason": "在真实实习指导关系内", "scope": "INTERN_STUDENTS"}

    def fake_decide(role_code, *, target_type, target_id, business_relation_allows, tenant_id):
        seen["policy"] = (role_code, target_type, target_id, business_relation_allows, tenant_id)
        return {
            "decision": "ALLOW",
            "reasonCode": "BUSINESS_RELATION_ALLOW",
            "chain": [{"step": "BUSINESS_RELATION", "hit": True}],
            "traceId": "trace-test",
        }

    monkeypatch.setattr(access_svc.data_scope_service, "simulate_access", fake_relation)
    monkeypatch.setattr(access_svc.scope_policy_service, "decide", fake_decide)
    actor = {"userId": "db-102", "tenantId": str(TID), "currentRoleCode": "INTERN_MENTOR", "dataScope": "INTERN_STUDENTS"}
    guard = access_svc._domain_guard_for_role(
        tenant_id=TID,
        subject=subject,
        role=role,
        actor=actor,
        scope_target_type="DOMAIN",
        scope_target_id="internship",
        resource_type="STUDENT",
        resource_id="9001",
    )
    assert guard["allowed"] is True
    assert guard["reasonCode"] == "ALLOW"
    assert guard["details"]["authority"] == "SCOPE_POLICY_SERVICE"
    assert guard["details"]["businessRelationAuthority"] == "DATA_SCOPE_SERVICE"
    assert seen["relation"][1] == "STUDENT"
    assert seen["relation"][2]["studentId"] == "9001"
    assert seen["policy"] == ("INTERN_MENTOR", "DOMAIN", "internship", True, TID)


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
