"""P0-C · 岗位实习 / 就业 PC 管理端角色门禁（require_staff）。

契约：
- 学生令牌访问任一 PC 管理端 internship/employment 接口 → 403（NO_PERMISSION）；
- 未登录 → 401（UNAUTHORIZED）；
- 教职工（school_admin01）不因门禁被 403。
学生的合法入口是 /mobile/internship/*（打卡/周报/我的实习），不在本门禁范围内，另有测试覆盖。
本测试只验证门禁（依赖在 handler 之前生效），不依赖 DB。
"""
from __future__ import annotations

TID = 1000000000000000001

# 每个被 _INTERN_DEP 门禁覆盖的独立 router 各取一个只读端点
MGMT_ENDPOINTS = [
    "/api/v1/internship/dashboard",           # internship.router
    "/api/v1/internship/students",            # internship.router（实习学生·legacy 列表）
    "/api/v1/internship/positions",           # internship_position.router
    "/api/v1/internship/agreement-templates",  # internship_agreement_template.router
    "/api/v1/internship/intern-students",     # internship_student.router
    "/api/v1/internship/match/results",       # internship_match.router
    "/api/v1/employment/dashboard",           # employment.router
]


def _student_headers():
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-STU-GATE", "realName": "门禁测试学生", "studentNo": "GATE001",
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def test_student_forbidden_on_internship_management(client):
    hdr = _student_headers()
    for ep in MGMT_ENDPOINTS:
        r = client.get(ep, headers=hdr)
        assert r.status_code == 403, f"{ep} 应对学生令牌返回 403，实际 {r.status_code}"


def test_unauthenticated_returns_401(client):
    for ep in MGMT_ENDPOINTS:
        r = client.get(ep)
        assert r.status_code == 401, f"{ep} 未登录应返回 401，实际 {r.status_code}"


def test_staff_not_blocked_by_gate(client, auth_headers, db_mode):
    # 教职工（school_admin01）通过门禁并正常拿到看板数据（真库）
    r = client.get("/api/v1/internship/dashboard", headers=auth_headers)
    assert r.status_code == 200, f"教职工应通过门禁，实际 {r.status_code}"
    assert r.json()["code"] == 0


def test_unlicensed_tenant_is_blocked(client, auth_headers, db_mode, monkeypatch):
    from app.services import platform_service
    monkeypatch.setattr(platform_service, "feature_enabled", lambda tenant_id, key: False)
    r = client.get("/api/v1/internship/dashboard", headers=auth_headers)
    assert r.status_code == 403
    assert r.json()["code"] != 0
