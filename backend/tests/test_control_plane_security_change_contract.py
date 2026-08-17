from app.modules.system_admin.services.role_permission_service import _validated_codes
from app.services import audit_log, security_change_service


def test_security_activation_audits_are_critical():
    assert "SECURITY_CHANGE_ACTIVATE" in audit_log.CRITICAL_ACTIONS
    assert "SECURITY_CHANGE_ROLLBACK" in audit_log.CRITICAL_ACTIONS


def test_security_change_transition_comes_from_canonical_control_plane():
    assert security_change_service.transition.__module__ == "app.modules.system_admin.services.security_change_service"


def test_custom_role_runtime_materialization_rejects_wildcards_and_platform_plane():
    for invalid in (["*"], ["systemAdmin.*"], ["platform.tenant.view"]):
        try:
            _validated_codes(invalid)
        except Exception:
            pass
        else:
            raise AssertionError(f"expected fail-closed for {invalid}")
