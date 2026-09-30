"""Editing permissions cannot silently rewrite or broaden an untouched scope."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppException
from app.services.data_scope_service import save_role_scope_in_session, _provider_custom


def case(row=None, scope="CUSTOM"):
    db = Mock()
    db.scalars.return_value.first.return_value = row
    role = SimpleNamespace(tenant_id=1007, role_code="STAFF", remark=f"SAAS_BUILTIN:v1;scope={scope}")
    return db, role


@pytest.mark.parametrize("structured", [False, True])
def test_permission_only_edit_preserves_empty_custom_scope_and_runtime_still_denies(structured):
    row = SimpleNamespace(scope_type="CUSTOM", target_json=None, status="ACTIVE", version=7) if structured else None
    db, role = case(row)
    before = role.remark
    out = save_role_scope_in_session(db, role, "CUSTOM", preserve_unchanged=True)
    assert out["scopeCode"] == "CUSTOM" and out["scopeTarget"] == {}
    assert out["before"] == {key: out[key] for key in ("scopeCode", "scopeTarget", "version")}
    assert role.remark == before
    db.add.assert_not_called()
    db.flush.assert_not_called()
    if row:
        assert row.version == 7
    with pytest.raises(AppException):
        _provider_custom({"customScopeTargets": {}}, "student", {"studentId": "1"})


@pytest.mark.parametrize("mode", ["new", "changed", "explicit_empty"])
def test_new_or_changed_custom_scope_still_requires_targets(mode):
    db, role = case(scope="SELF" if mode == "changed" else "CUSTOM")
    kwargs = {"preserve_unchanged": mode != "new"}
    if mode == "explicit_empty":
        kwargs["target_json"] = {}
    with pytest.raises(AppException):
        save_role_scope_in_session(db, role, "CUSTOM", **kwargs)
    db.add.assert_not_called()


def test_unchanged_structured_scope_retains_targets_and_version():
    row = SimpleNamespace(scope_type="CUSTOM", target_json={"classIds": ["9007199254740993"]}, status="ACTIVE", version=7)
    db, role = case(row)
    out = save_role_scope_in_session(db, role, "CUSTOM", preserve_unchanged=True)
    assert out["scopeTarget"] == row.target_json and out["version"] == 7
    db.flush.assert_not_called()


def test_scope_version_conflict_is_checked_before_noop():
    db, role = case(SimpleNamespace(scope_type="CUSTOM", target_json={}, status="ACTIVE", version=7))
    with pytest.raises(AppException) as exc:
        save_role_scope_in_session(db, role, "CUSTOM", expected_version=6, preserve_unchanged=True)
    assert exc.value.code == "DATA_CONFLICT"
