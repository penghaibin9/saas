from app.modules.system_admin.services import school_iam_workspace_service as svc


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


def test_school_iam_router_defaults_to_recruitment_manage_explain():
    from app.modules.system_admin.routers import school_iam_router
    source = __import__("inspect").getsource(school_iam_router.iam_access_explain)
    assert "internship" in source
    assert "internship.recruitment.manage" in source
