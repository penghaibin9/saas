"""Fixture grants are explicit, tenant-bound and forbidden in strict environments."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _helper():
    path = Path(__file__).resolve().parents[1] / "scripts/_seed_fixture_roles.py"
    spec = importlib.util.spec_from_file_location("pr265_fixture_roles", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _user(**changes):
    values = dict(id=7, tenant_id=11, user_type="STUDENT", status="ACTIVE", is_deleted=False)
    values.update(changes)
    return SimpleNamespace(**values)


class Session:
    def __init__(self, role=None, link=None):
        self.role, self.link = role, link
        self.added, self.queries = [], []

    def scalars(self, statement):
        self.queries.append(str(statement.compile(compile_kwargs={"literal_binds": True})))
        row = self.role if len(self.queries) == 1 else self.link
        return SimpleNamespace(one_or_none=lambda: row)

    def add(self, row):
        self.added.append(row)

    def flush(self):
        for row in self.added:
            if not row.id:
                row.id = 23


@pytest.mark.parametrize("env", ["production", "staging"])
def test_fixture_role_grants_cannot_run_in_strict_environment(monkeypatch, env):
    from app.core import config
    monkeypatch.setattr(config, "settings", SimpleNamespace(is_prod=env == "production", APP_ENV=env))
    db = Session()
    with pytest.raises(RuntimeError, match="prohibited"):
        _helper().ensure_fixture_role(db, _user(), "STUDENT")
    assert not db.added and not db.queries


@pytest.mark.parametrize("changes", [
    {"status": "DISABLED"}, {"is_deleted": True}, {"user_type": "PLATFORM_SUPER_ADMIN"},
    {"user_type": "ADMIN"}, {"id": None}, {"tenant_id": None},
])
def test_invalid_or_mismatched_fixture_subject_gets_no_grant(monkeypatch, changes):
    from app.core import config
    monkeypatch.setattr(config, "settings", SimpleNamespace(is_prod=False, APP_ENV="test"))
    db = Session()
    with pytest.raises(RuntimeError, match="contract"):
        _helper().ensure_fixture_role(db, _user(**changes), "STUDENT")
    assert not db.added and not db.queries


def test_fixture_writes_explicit_system_role_and_user_link(monkeypatch):
    from app.core import config
    from app.models import Role, UserRole
    monkeypatch.setattr(config, "settings", SimpleNamespace(is_prod=False, APP_ENV="test"))
    db = Session()
    _helper().ensure_fixture_role(db, _user(), "STUDENT")
    role, link = db.added
    assert isinstance(role, Role) and role.role_type == "SYSTEM" and role.role_code == "STUDENT"
    assert isinstance(link, UserRole) and link.user_id == 7 and link.role_id == role.id
    assert role.tenant_id == link.tenant_id == 11
    assert all("tenant_id = 11" in query for query in db.queries)


def test_fixture_replay_does_not_reactivate_withdrawn_assignment(monkeypatch):
    from app.core import config
    monkeypatch.setattr(config, "settings", SimpleNamespace(is_prod=False, APP_ENV="test"))
    role = SimpleNamespace(id=23, is_deleted=False, status="ACTIVE", role_type="SYSTEM")
    link = SimpleNamespace(is_deleted=False, status="DISABLED")
    db = Session(role, link)
    with pytest.raises(RuntimeError, match="reactivate"):
        _helper().ensure_fixture_role(db, _user(), "STUDENT")
    assert not db.added and link.status == "DISABLED"
