from __future__ import annotations

from contextlib import contextmanager
from inspect import signature
from importlib import import_module
from types import SimpleNamespace

import pytest

from app.api.v1 import mobile as mobile_router
from app.modules.academic_affairs.services import academic_affairs_warning_service as canonical_warning
from app.modules.academic_affairs.services import mobile_academic_affairs_service as mobile_academic
from app.student_portal import router as portal_router
from app.student_portal.services import academic_service as portal_academic


def _query_bound(query, name):
    direct = getattr(query, name, None)
    if direct is not None:
        return direct
    for item in getattr(query, "metadata", ()):
        value = getattr(item, name, None)
        if value is not None:
            return value
    return None


def _install_identity(monkeypatch, academic_student_id):
    # Patch globals on the function owner, not on the public alias module.
    owner = import_module(mobile_academic.warning_my.__module__)
    @contextmanager
    def fake_session():
        yield object()

    monkeypatch.setattr(owner, "session", fake_session)
    monkeypatch.setattr(owner, "_me", lambda _db, _user: SimpleNamespace(id=7))
    monkeypatch.setattr(
        owner,
        "_acad_student",
        lambda _db, _student: None if academic_student_id is None else SimpleNamespace(id=academic_student_id),
    )


def test_public_mobile_and_portal_aliases_keep_page_defaults_and_bounds():
    for endpoint in (mobile_router.academic_warning_my, portal_router.academic_warning):
        params = signature(endpoint).parameters
        assert params["page"].default.default == 1
        assert _query_bound(params["page"].default, "ge") == 1
        page_size = params["page_size"].default
        assert page_size.alias == "pageSize"
        assert page_size.default == 50
        assert _query_bound(page_size, "ge") == 1
        assert _query_bound(page_size, "le") == 100


def test_mobile_router_forwards_public_page_size_alias_values(monkeypatch):
    seen = {}

    def fake_warning_my(user, page, page_size):
        seen.update(user=user, page=page, page_size=page_size)
        return {"items": [], "total": 0, "page": page, "pageSize": page_size, "hasMore": False}

    monkeypatch.setattr(mobile_router.aa, "warning_my", fake_warning_my)
    user = {"userType": "STUDENT", "userId": "101"}
    mobile_router.academic_warning_my(user=user, page=2, page_size=17)
    assert seen == {"user": user, "page": 2, "page_size": 17}


def test_portal_router_and_service_forward_page_without_replacing_identity(monkeypatch):
    router_seen = {}
    service_seen = {}
    user = {"userType": "STUDENT", "userId": "101", "studentId": "someone-else"}

    def fake_portal_warning(received_user, page, page_size):
        router_seen.update(user=received_user, page=page, page_size=page_size)
        return {"items": []}

    def fake_mobile_warning(received_user, page, page_size):
        service_seen.update(user=received_user, page=page, page_size=page_size)
        return {"items": []}

    real_portal_warning = portal_academic.warning
    monkeypatch.setattr(portal_router.academic, "warning", fake_portal_warning)
    portal_router.academic_warning(user=user, page=3, page_size=9)
    assert router_seen == {"user": user, "page": 3, "page_size": 9}

    monkeypatch.setattr(portal_academic.aa, "warning_my", fake_mobile_warning)
    real_portal_warning(user, page=4, page_size=11)
    assert service_seen == {"user": user, "page": 4, "page_size": 11}


def test_default_page_uses_resolved_own_academic_student_and_canonical_query(monkeypatch):
    _install_identity(monkeypatch, academic_student_id=41)
    seen = {}

    def fake_list_warnings(user, *, acad_student_id, page, page_size):
        seen.update(user=user, acad_student_id=acad_student_id, page=page, page_size=page_size)
        return ([{"warningId": "W-1"}], 101)

    monkeypatch.setattr(canonical_warning, "list_warnings", fake_list_warnings)
    user = {"userType": "STUDENT", "userId": "101", "studentId": "999999"}
    result = mobile_academic.warning_my(user)

    assert seen == {"user": user, "acad_student_id": 41, "page": 1, "page_size": 50}
    assert result == {
        "items": [{"warningId": "W-1"}],
        "total": 101,
        "page": 1,
        "pageSize": 50,
        "hasMore": True,
    }


@pytest.mark.parametrize(
    ("page", "page_size", "total", "has_more"),
    [(2, 20, 45, True), (3, 20, 45, False)],
)
def test_page_two_and_last_page_metadata_come_from_canonical_total(
    monkeypatch, page, page_size, total, has_more
):
    _install_identity(monkeypatch, academic_student_id=52)
    seen = {}

    def fake_list_warnings(_user, *, acad_student_id, page, page_size):
        seen.update(acad_student_id=acad_student_id, page=page, page_size=page_size)
        return ([{"warningId": f"W-{page}"}], total)

    monkeypatch.setattr(canonical_warning, "list_warnings", fake_list_warnings)
    result = mobile_academic.warning_my({"userType": "STUDENT"}, page=page, page_size=page_size)
    assert seen == {"acad_student_id": 52, "page": page, "page_size": page_size}
    assert result["page"] == page
    assert result["pageSize"] == page_size
    assert result["total"] == total
    assert result["hasMore"] is has_more


def test_service_clamps_page_boundaries_before_calling_canonical(monkeypatch):
    _install_identity(monkeypatch, academic_student_id=63)
    seen = {}

    def fake_list_warnings(_user, *, acad_student_id, page, page_size):
        seen.update(acad_student_id=acad_student_id, page=page, page_size=page_size)
        return ([], 0)

    monkeypatch.setattr(canonical_warning, "list_warnings", fake_list_warnings)
    result = mobile_academic.warning_my({"userType": "STUDENT"}, page=0, page_size=999)
    assert seen == {"acad_student_id": 63, "page": 1, "page_size": 100}
    assert result == {"items": [], "total": 0, "page": 1, "pageSize": 100, "hasMore": False}


def test_unbound_student_returns_empty_paging_metadata_without_canonical_query(monkeypatch):
    _install_identity(monkeypatch, academic_student_id=None)
    calls = 0

    def forbidden_canonical(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("canonical warning query must not run for an unbound student")

    monkeypatch.setattr(canonical_warning, "list_warnings", forbidden_canonical)
    result = mobile_academic.warning_my(
        {"userType": "STUDENT", "userId": "unbound", "studentId": "other"},
        page=2,
        page_size=25,
    )
    assert calls == 0
    assert result == {"items": [], "total": 0, "page": 2, "pageSize": 25, "hasMore": False}
