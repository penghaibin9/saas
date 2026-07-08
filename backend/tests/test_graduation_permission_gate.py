"""毕业设计中心 · PC 管理端角色门禁回归测试（require_staff）。
学生令牌一律 403；教职工令牌放行；学生合法入口 /mobile/graduation/* 不受影响。"""
from __future__ import annotations

MAIN = 1000000000000000001


def _stu_token(name="门禁测试生"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-" + name, "realName": name, "userType": "STUDENT", "tid": "demo",
        "tenantId": str(MAIN), "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP"})}


# 覆盖各毕设管理端 router 的代表性端点（读/写/导出/统计）
GD_ADMIN_ENDPOINTS = [
    ("GET", "/api/v1/graduation/gd-mentors"),
    ("POST", "/api/v1/graduation/gd-mentors"),
    ("GET", "/api/v1/graduation/students"),
    ("GET", "/api/v1/graduation/gd-topics"),
    ("POST", "/api/v1/graduation/batches"),
    ("POST", "/api/v1/graduation/proposals/export"),
    ("GET", "/api/v1/graduation/gd-stats/overview"),
    ("GET", "/api/v1/graduation/gd-defense-experts"),
    ("GET", "/api/v1/graduation/gd-templates"),
]


def test_student_blocked_on_all_gd_admin_endpoints(client, db_mode):
    sh = _stu_token()
    for method, path in GD_ADMIN_ENDPOINTS:
        r = client.request(method, path, headers=sh, json={} if method == "POST" else None)
        assert r.status_code == 403, f"{method} {path} 应对学生 403，实际 {r.status_code}"


def test_staff_allowed_on_gd_admin(client, auth_headers, db_mode):
    # 教职工（school_admin01）读管理端应放行（非 403）
    r = client.get("/api/v1/graduation/gd-mentors", headers=auth_headers)
    assert r.status_code == 200
    assert r.json().get("code") == 0


def test_student_mobile_entry_not_blocked(client, db_mode):
    # 学生合法入口 /mobile/graduation/* 不被 require_staff 拦（查不到档案返回空态，不是 403）
    sh = _stu_token()
    r = client.get("/api/v1/mobile/graduation/my", headers=sh)
    assert r.status_code != 403
