from types import SimpleNamespace

from app.services import auth_service_db


def test_auth_me_returns_tenant_from_loaded_user(monkeypatch):
    closed = []
    db = SimpleNamespace(close=lambda: closed.append(True))
    user = SimpleNamespace(id=7, tenant_id=42, login_name="student-test", real_name="Test", user_type="STUDENT")
    context = {"contextId": "ctx-student", "roleCode": "STUDENT", "roleName": "Student", "dataScope": "SELF", "scopeLabel": "Self"}
    monkeypatch.setattr(auth_service_db, "get_sessionmaker", lambda: lambda: db)
    monkeypatch.setattr(auth_service_db, "_load_token_user", lambda _db, _ctx: user)
    monkeypatch.setattr(auth_service_db, "_role_contexts", lambda _db, _user: [context])
    monkeypatch.setattr(auth_service_db, "_pick_context", lambda *_args, **_kwargs: context)
    result = auth_service_db.get_me({"userId": "db-7", "activeContextId": "ctx-student"})
    assert result["tenantId"] == "42"
    assert result["userId"] == "db-7"
    assert result["activeContextId"] == "ctx-student"
    assert result["currentRole"]["roleCode"] == "STUDENT"
    assert "accessToken" not in result
    assert closed == [True]
