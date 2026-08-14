from app.modules.system_admin.policies.role_template_plane import assert_school_role_template_code
from app.modules.system_admin.services import role_template_service as svc
from app.services import audit_log


def test_published_template_status_and_audit_contract():
    assert svc.PUBLISHED == "PUBLISHED"
    assert "ROLE_TEMPLATE_PUBLISH" in audit_log.CRITICAL_ACTIONS


def test_enterprise_and_platform_roles_cannot_enter_school_role_templates():
    for role in ("COMPANY_ADMIN", "HR", "MENTOR", "PLATFORM_OWNER", "PLATFORM_OPERATIONS"):
        try:
            assert_school_role_template_code(role)
        except Exception:
            pass
        else:
            raise AssertionError(f"{role} must not be a school RoleTemplate")


def test_role_template_digest_is_order_independent():
    assert svc._digest(["internship.recruitment.view", "internship.recruitment.manage"]) == svc._digest([
        "internship.recruitment.manage", "internship.recruitment.view"
    ])
