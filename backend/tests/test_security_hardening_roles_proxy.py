"""SEC-01/04 regressions against the repository's actual runtime symbols.

Deterministic session/cache doubles do not replace the required MySQL/Redis
multi-worker deployment acceptance. No tests mutate real school accounts.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request


def _settings(env="production", mock=False):
    return SimpleNamespace(is_prod=env == "production", APP_ENV=env, mock_login_enabled=mock)


def _empty_roles():
    return SimpleNamespace(execute=lambda statement: SimpleNamespace(all=lambda: []))


@pytest.mark.parametrize("tenant_id", [11001, 22002])
@pytest.mark.parametrize("env", ["production", "staging"])
@pytest.mark.parametrize("login_name", ["admin", "admin2", "admin_demo", "teacher", "student", "real_teacher"])
def test_no_role_never_infers_authority_in_strict_environment(monkeypatch, tenant_id, env, login_name):
    from app.services import auth_service_db as service

    monkeypatch.setattr(service, "settings", _settings(env, mock=True))
    user = SimpleNamespace(id=7, tenant_id=tenant_id, user_type="TEACHER", login_name=login_name)
    assert service._role_contexts(_empty_roles(), user) == []


def test_real_role_wins_even_when_login_name_matches_legacy_admin(monkeypatch):
    from app.services import auth_service_db as service

    monkeypatch.setattr(service, "settings", _settings())
    monkeypatch.setattr(service, "_scope_from_role", lambda role: "ASSIGNED")
    role = SimpleNamespace(id=12, role_code="ACADEMIC_TEACHER", role_name="Teacher", version=2)
    link = SimpleNamespace(version=3)
    db = SimpleNamespace(execute=lambda statement: SimpleNamespace(all=lambda: [(link, role)]))
    user = SimpleNamespace(id=7, tenant_id=11001, user_type="TEACHER", login_name="admin")
    contexts = service._role_contexts(db, user)
    assert [(item["contextId"], item["roleCode"], item["version"]) for item in contexts] == [
        ("role:12", "ACADEMIC_TEACHER", 3)
    ]


@pytest.mark.parametrize("mock", [False, True])
def test_nonproduction_compatibility_requires_explicit_mock_policy(monkeypatch, mock):
    from app.services import auth_service_db as service

    monkeypatch.setattr(service, "settings", _settings("test", mock))
    user = SimpleNamespace(id=7, tenant_id=11001, user_type="ADMIN", login_name="admin")
    contexts = service._role_contexts(_empty_roles(), user)
    assert bool(contexts) is mock
    if contexts:
        assert contexts[0]["contextId"] == "legacy:SCHOOL_ADMIN"


def test_platform_identity_is_not_converted_to_school_role(monkeypatch):
    from app.services import auth_service_db as service

    monkeypatch.setattr(service, "settings", _settings())
    user = SimpleNamespace(id=7, tenant_id=11001, user_type="PLATFORM_SUPER_ADMIN", login_name="admin")
    assert service._role_contexts(_empty_roles(), user)[0]["roleCode"] == "PLATFORM_SUPER_ADMIN"


def test_old_school_legacy_subject_cannot_use_cached_allow(monkeypatch):
    from app.services import auth_service_db as service

    monkeypatch.setattr(service, "settings", _settings())
    monkeypatch.setattr(service, "cache_get", lambda key: pytest.fail("legacy subject must revalidate"))
    monkeypatch.setattr(service, "cache_get_json", lambda key: pytest.fail("cached allow must not win"))
    assert service._subject_cache_matches({
        "userId": "db-7", "tenantId": "11001", "userType": "ADMIN",
        "activeContextId": "legacy:SCHOOL_ADMIN", "currentRoleCode": "SCHOOL_ADMIN",
        "permissionVersion": "u1|SCHOOL_ADMIN:0",
    }) is False


@pytest.mark.parametrize("peer,xff,real,trust,expected", [
    ("172.30.40.10", ["1.1.1.1, 203.0.113.8"], [], "172.30.40.10/32", "203.0.113.8"),
    ("203.0.113.8", ["1.1.1.1"], ["2.2.2.2"], "172.30.40.10/32", "203.0.113.8"),
    ("172.30.40.10", ["1.1.1.1", "203.0.113.8"], [], "172.30.40.10/32", "172.30.40.10"),
    ("172.30.40.10", ["1.1.1.1, invalid"], [], "172.30.40.10/32", "172.30.40.10"),
    ("172.30.40.10", ["203.0.113.8, 10.0.0.9"], [], "172.30.40.10/32,10.0.0.9/32", "203.0.113.8"),
    ("172.30.40.10", [",".join(["1.1.1.1"] * 17)], [], "172.30.40.10/32", "172.30.40.10"),
    ("::ffff:172.30.40.10", ["::ffff:203.0.113.8"], [], "172.30.40.10/32", "203.0.113.8"),
])
def test_canonical_proxy_chain(peer, xff, real, trust, expected):
    from app.core.forwarded_ip_security import canonical_client_ip

    assert canonical_client_ip(peer, xff, real, trust) == expected


def test_cached_headers_and_downstream_scope_keep_one_canonical_identity():
    from app.core.forwarded_ip_security import normalize_forwarded_request

    request = Request({
        "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": "/api/v1/auth/login", "root_path": "", "query_string": b"",
        "server": ("testserver", 80), "client": ("172.30.40.10", 1234),
        "headers": [(b"x-forwarded-for", b"1.1.1.1, 203.0.113.8"),
                    (b"x-real-ip", b"9.9.9.9"), (b"x-forwarded-proto", b"https"),
                    (b"authorization", b"Bearer unit-test-only")],
    })
    cached_headers = request.headers
    normalize_forwarded_request(request, "172.30.40.10/32")
    assert cached_headers["x-forwarded-for"] == "203.0.113.8"
    assert Request(request.scope).headers["x-real-ip"] == "203.0.113.8"
    assert request.headers["authorization"] == "Bearer unit-test-only"
    assert request.scope["scheme"] == "https"


def test_installed_runtime_preserves_existing_durable_auth_authority():
    import app.api.v1.router  # noqa: F401
    from app.core import token_store
    from app.services import auth_service_db, control_plane_auth_service as p0, wx_auth_service

    assert auth_service_db.login_with_password is p0.login_with_password
    assert auth_service_db.change_own_password is p0.change_own_password
    assert wx_auth_service.wx_bind is p0.wx_bind
    assert token_store.rate_limit is p0.rate_limit
