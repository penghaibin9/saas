from app.modules.system_admin.policies.role_template_plane import is_school_role_template_code


def test_platform_workforce_is_not_school_role_template():
    assert not is_school_role_template_code("PLATFORM_OPERATIONS")
    assert not is_school_role_template_code("PLATFORM_OWNER")


def test_enterprise_member_roles_are_not_school_role_templates():
    assert not is_school_role_template_code("COMPANY_ADMIN")
    assert not is_school_role_template_code("HR")
    assert not is_school_role_template_code("MENTOR")


def test_school_roles_remain_template_eligible():
    assert is_school_role_template_code("SCHOOL_ADMIN")
    assert is_school_role_template_code("INTERNSHIP_TEACHER")
