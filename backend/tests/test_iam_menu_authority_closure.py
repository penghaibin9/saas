import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.core.permission_catalog import load_permission_catalog
from app.services import system_role_shadow_service as shadow
from app.services.system_admin_catalog_service import build_permission_tree, visible_codes_from_tree


ROOT = Path(__file__).resolve().parents[2]


def _platform_root():
    return {"currentRoleCode": "PLATFORM_SUPER_ADMIN", "userType": "PLATFORM_SUPER_ADMIN"}


def test_custom_role_authoring_tree_covers_every_canonical_assignable_permission():
    expected = {
        item["permissionCode"]
        for item in load_permission_catalog()["entries"]
        if item.get("plane") == "TENANT"
        and item.get("lifecycle") == "ACTIVE"
        and item.get("tenantAssignable") is True
        and item.get("customRoleAssignable") is True
        and not item["permissionCode"].startswith(("system.", "platform.", "enterprise."))
    }
    tree = build_permission_tree(_platform_root())
    actual = visible_codes_from_tree(tree)
    assert actual == expected
    assert any(menu.get("advanced") for module in tree for menu in module["children"])


def test_custom_role_authoring_tree_never_exposes_cross_plane_or_legacy_new_writes():
    actual = visible_codes_from_tree(build_permission_tree(_platform_root()))
    assert not {code for code in actual if code.startswith(("platform.", "enterprise.", "system."))}


def test_alias_backfill_migration_uses_the_exact_checked_in_alias_contract():
    contract = json.loads((ROOT / "shared" / "contracts" / "permission-aliases.json").read_text(encoding="utf-8"))
    migration_path = ROOT / "backend" / "alembic" / "versions" / "20260831_iam_alias_backfill.py"
    spec = importlib.util.spec_from_file_location("iam_alias_backfill", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ALIASES == contract["aliases"]
    assert all(code.startswith("system.") for code in module.ALIASES)
    assert all(code.startswith("systemAdmin.") for code in module.ALIASES.values())


def test_published_system_template_is_runtime_authority_not_legacy_equality(monkeypatch):
    allowed = {"academicAffairs.course.view", "academicAffairs.grade.view"}
    template = SimpleNamespace(id=9, permission_digest=shadow._digest(allowed))
    monkeypatch.setattr(shadow, "_latest_published_template", lambda db, role: template)
    monkeypatch.setattr(shadow, "_normalized_template_permissions", lambda db, item: (allowed, set()))
    monkeypatch.setattr(shadow, "active_tenant_permission_codes", lambda: tuple(allowed))
    monkeypatch.setattr(shadow, "expected_system_role_permissions", lambda role: ("academicAffairs.course.view",))
    assert shadow.published_system_role_permissions(object(), "ACADEMIC_ADMIN") == tuple(sorted(allowed))


def test_published_system_template_digest_drift_fails_closed(monkeypatch):
    allowed = {"academicAffairs.course.view"}
    template = SimpleNamespace(id=9, permission_digest="0" * 64)
    monkeypatch.setattr(shadow, "_latest_published_template", lambda db, role: template)
    monkeypatch.setattr(shadow, "_normalized_template_permissions", lambda db, item: (allowed, set()))
    monkeypatch.setattr(shadow, "active_tenant_permission_codes", lambda: tuple(allowed))
    monkeypatch.setattr(shadow, "expected_system_role_permissions", lambda role: tuple(allowed))
    with pytest.raises(AppException) as caught:
        shadow.published_system_role_permissions(object(), "ACADEMIC_ADMIN")
    assert caught.value.code == "B8_SYSTEM_TEMPLATE_DRIFT"
