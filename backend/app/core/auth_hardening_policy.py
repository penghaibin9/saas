"""Small, side-effect-free policy shared by runtime auth and regression tests."""
from __future__ import annotations


def strict_security_environment(settings) -> bool:
    return bool(settings.is_prod or str(settings.APP_ENV or "").strip().lower() == "staging")


def allow_legacy_role_fallback(settings) -> bool:
    # Never infer production authority from a familiar username. Development
    # compatibility requires the existing explicit mock-login policy as well.
    return not strict_security_environment(settings) and settings.mock_login_enabled is True


def legacy_school_context(user: dict) -> bool:
    return (
        str(user.get("activeContextId") or "").startswith("legacy:")
        and str(user.get("userType") or "").upper() != "PLATFORM_SUPER_ADMIN"
    )
