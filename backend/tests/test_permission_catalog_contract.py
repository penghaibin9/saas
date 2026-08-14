from app.core.permission_catalog import enterprise_permission_codes, load_permission_catalog, permission_meta


def test_e_series_permissions_are_canonical_in_internship_module():
    required = {
        "internship.recruitment.view", "internship.recruitment.manage", "internship.recruitment.invite", "internship.recruitment.close",
        "enterprise.internship.company.view", "enterprise.internship.company.edit",
        "enterprise.internship.position.view", "enterprise.internship.position.manage", "enterprise.internship.position.submit",
        "enterprise.internship.application.view", "enterprise.internship.application.decide",
        "enterprise.internship.student.view", "enterprise.internship.eval.submit",
    }
    catalog = load_permission_catalog()["_byCode"]
    assert required <= set(catalog)
    assert all(catalog[code]["moduleKey"] == "internship" for code in required)


def test_enterprise_permissions_are_never_school_custom_role_assignable():
    for code in enterprise_permission_codes():
        meta = permission_meta(code)
        assert meta["plane"] == "TENANT"
        assert meta["tenantAssignable"] is False
        assert meta["customRoleAssignable"] is False


def test_permission_catalog_codes_are_unique():
    catalog = load_permission_catalog()
    codes = [item["permissionCode"] for item in catalog["entries"]]
    assert len(codes) == len(set(codes))
