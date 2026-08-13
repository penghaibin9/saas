"""平台沙箱恢复路径兼容合同。

不在普通 CI 真灌 20K；用 profile monkeypatch 验证：
- standard-20k 只恢复轻量故事线；
- standard-20k-damaged 必须 409，绝不降级成 legacy-100；
- 既有 legacy-100 真实数据库恢复仍由 test_demo_tenants_login.py 负责。
"""
from __future__ import annotations


def _platform_headers():
    from app.core.security import create_access_token
    token = create_access_token({
        "userId": "platform-sandbox-test",
        "realName": "平台沙箱测试",
        "userType": "PLATFORM_SUPER_ADMIN",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN",
        "tenantId": "1000000000000000000",
        "tenantName": "平台运营中心",
        "activeContextId": "ctx_platform_sandbox_test",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def test_reset_sandbox_route_is_registered_once():
    from fastapi.routing import APIRoute
    from app.api.v1.router import api_router

    matches = [
        route for route in api_router.routes
        if isinstance(route, APIRoute)
        and route.path == "/platform/tenants/{tenant_id}/reset-sandbox-data"
        and "POST" in (route.methods or set())
    ]
    assert len(matches) == 1
    assert matches[0].endpoint.__module__ == "app.api.v1.sandbox_story_api"


def test_standard_20k_platform_restore_uses_story_mode(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.services.sandbox_service import SANDBOX_TID, seed_sandbox
    from app.services import sandbox_school_profile as profile_svc
    from app.services import sandbox_school_story_reset as story_svc

    db = get_sessionmaker()()
    try:
        seed_sandbox(db)
    finally:
        db.close()

    monkeypatch.setattr(profile_svc, "classify_sandbox_profile", lambda _db, _tid: {
        "profile": profile_svc.PROFILE_STANDARD,
        "students": 20_000,
        "colleges": 8,
        "majors": 32,
        "classes": 384,
        "backgroundStaffAccounts": 1_280,
    })
    monkeypatch.setattr(story_svc, "restore_sales_storylines", lambda _db, _tid: {
        "mode": "storyline",
        "preservedStudents": 20_000,
        "stories": ["2026S0001-迎新", "2025S0001-学生事务", "2024S0001-岗位实习"],
        "storyTodos": 4,
        "fullRebuild": False,
    })

    response = client.post(
        f"/api/v1/platform/tenants/{SANDBOX_TID}/reset-sandbox-data",
        headers=_platform_headers(),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 0
    assert body["data"]["profile"]["profile"] == "standard-20k"
    assert body["data"]["reseeded"]["mode"] == "storyline"
    assert body["data"]["reseeded"]["preservedStudents"] == 20_000
    assert body["data"]["reseeded"]["fullRebuild"] is False


def test_damaged_standard_20k_never_downgrades_to_legacy(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.services.sandbox_service import SANDBOX_TID, seed_sandbox
    from app.services import sandbox_school_profile as profile_svc

    db = get_sessionmaker()()
    try:
        seed_sandbox(db)
    finally:
        db.close()

    monkeypatch.setattr(profile_svc, "classify_sandbox_profile", lambda _db, _tid: {
        "profile": profile_svc.PROFILE_STANDARD_DAMAGED,
        "students": 19_999,
        "colleges": 8,
        "majors": 32,
        "classes": 384,
        "backgroundStaffAccounts": 1_280,
    })

    response = client.post(
        f"/api/v1/platform/tenants/{SANDBOX_TID}/reset-sandbox-data",
        headers=_platform_headers(),
    )
    body = response.json()
    assert response.status_code == 409
    assert body["code"] != 0
    assert "阻断 legacy-100 降级恢复" in body["message"]
