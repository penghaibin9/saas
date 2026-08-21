"""Keep P1 System Management write authorities assignable from the existing role UI."""

from app.services.system_admin_catalog_service import SCHOOL_PERMISSION_GROUPS, collect_concrete_permission_codes


def _system_user_actions() -> set[str]:
    system_group = next(group for group in SCHOOL_PERMISSION_GROUPS if group["key"] == "mod-systemAdmin")
    user_menu = next(menu for menu in system_group["menus"] if menu["code"] == "systemAdmin.user.view")
    return {code for code, _label in user_menu["actions"]}


def test_p1_delegated_user_authorities_are_in_role_permission_catalog():
    actions = _system_user_actions()
    assert "systemAdmin.user.assign-role" in actions
    assert "systemAdmin.user.assign" in actions
    assert "systemAdmin.user.bind" in actions

    concrete = collect_concrete_permission_codes()
    assert {"systemAdmin.user.assign", "systemAdmin.user.bind"}.issubset(concrete)
