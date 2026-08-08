"""Regression contract: resetting sandbox must not leave teacher2 logged in but unable to work."""
from __future__ import annotations


def _seed_context():
    from app.core.context import set_current_user, set_tenant

    set_tenant({
        "tenantId": "1000000000000000007",
        "tenantCode": "sandbox-school",
        "tenantName": "体验沙箱学校",
        "status": "ACTIVE",
    })
    set_current_user({
        "userId": "pytest-sandbox-admin",
        "loginName": "admin2",
        "realName": "Pytest Sandbox Admin",
        "userType": "ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
        "tenantId": "1000000000000000007",
        "tenantCode": "sandbox-school",
    })


def _clear_context():
    from app.core.context import set_current_user, set_tenant

    set_current_user(None)
    set_tenant(None)


def test_sandbox_reset_rebuilds_teacher_role_and_stable_mentor_contract(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.services.sandbox_service import reset_sandbox, seed_sandbox

    db = get_sessionmaker()()
    try:
        _seed_context()
        seed_sandbox(db)
        report = reset_sandbox(db, dry_run=False)
        assert report["removed"] and report["reseeded"]
    finally:
        _clear_context()
        db.close()

    login = client.post(
        "/api/v1/auth/login", json={"loginName": "teacher2", "password": "123456"}
    ).json()
    assert login["code"] == 0, login
    contexts = login["data"].get("contexts") or []
    by_role = {item["roleCode"]: item for item in contexts}
    assert {"COUNSELOR", "INTERN_MENTOR", "GD_MENTOR"}.issubset(by_role)
    assert login["data"]["currentRole"]["roleCode"] == "COUNSELOR"

    auth = {"Authorization": "Bearer " + login["data"]["accessToken"]}
    switched = client.post(
        "/api/v1/auth/switch-role",
        headers=auth,
        json={"contextId": by_role["GD_MENTOR"]["contextId"], "clientType": "MP"},
    ).json()
    assert switched["code"] == 0, switched
    assert switched["data"]["currentRole"]["roleCode"] == "GD_MENTOR"

    gd_auth = {"Authorization": "Bearer " + switched["data"]["accessToken"]}
    dashboard = client.get("/api/v1/mobile/teacher/graduation", headers=gd_auth).json()
    assert dashboard["code"] == 0, dashboard
    assert dashboard["data"].get("students"), dashboard
