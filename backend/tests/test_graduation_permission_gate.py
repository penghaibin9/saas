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


def test_student_blocked_on_all_gd_admin_endpoints(graduation_client, db_mode):
    sh = _stu_token()
    for method, path in GD_ADMIN_ENDPOINTS:
        r = graduation_client.request(method, path, headers=sh, json={} if method == "POST" else None)
        assert r.status_code == 403, f"{method} {path} 应对学生 403，实际 {r.status_code}"


def test_staff_allowed_on_gd_admin(graduation_client, auth_headers, db_mode):
    # 教职工（school_admin01）读管理端应放行（非 403）
    r = graduation_client.get("/api/v1/graduation/gd-mentors", headers=auth_headers)
    assert r.status_code == 200
    assert r.json().get("code") == 0


def test_student_mobile_entry_not_blocked(graduation_client, db_mode):
    # 学生合法入口 /mobile/graduation/* 不被 require_staff 拦（查不到档案返回空态，不是 403）
    sh = _stu_token()
    r = graduation_client.get("/api/v1/mobile/graduation/my", headers=sh)
    assert r.status_code != 403


def _role_token(role: str, user_type: str = "TEACHER", **claims):
    from app.core.security import create_access_token
    payload = {"userId": f"u-{role}", "realName": role, "userType": user_type, "tid": "demo",
              "tenantId": str(MAIN), "activeContextId": "ctx", "currentRoleCode": role, "clientType": "PC"}
    payload.update(claims)
    return {"Authorization": "Bearer " + create_access_token(payload)}


# require_graduation_request_permission（router.py 的 _GD_DEP，覆盖全部 15 个毕设 router）按角色收敛的
# 端到端回归：证明"角色只授予了部分 permissionCode"这件事在真实 HTTP 请求链路上确实生效，
# 不只是 has_permission()/graduation_permission_for() 的纯函数单测（test_graduation_permission_codes.py）。
def test_gd_mentor_cannot_create_mentor_record(graduation_client, db_mode):
    # GD_MENTOR 只有 view/guide.*/proposal.review/final.review，没有创建导师所需的 graduationDesign.manage
    h = _role_token("GD_MENTOR")
    r = graduation_client.post("/api/v1/graduation/gd-mentors", headers=h, json={})
    assert r.status_code == 403, f"GD_MENTOR 建导师应 403，实际 {r.status_code}"


def test_gd_defense_expert_cannot_publish_grade(graduation_client, db_mode):
    # GD_DEFENSE_EXPERT 只有 view/defense.score，没有 graduationDesign.grade.publish
    h = _role_token("GD_DEFENSE_EXPERT")
    r = graduation_client.post("/api/v1/graduation/gd-grades/999999/publish", headers=h)
    assert r.status_code == 403, f"GD_DEFENSE_EXPERT 发布成绩应 403，实际 {r.status_code}"


def test_gd_mentor_cannot_submit_archive(graduation_client, db_mode):
    # GD_MENTOR 没有 graduationDesign.archive.submit
    h = _role_token("GD_MENTOR")
    r = graduation_client.post("/api/v1/graduation/gd-archives/999999/submit", headers=h)
    assert r.status_code == 403, f"GD_MENTOR 提交归档应 403，实际 {r.status_code}"


def test_graduation_admin_passes_permission_gate_for_same_actions(graduation_client, db_mode):
    # 对照组：GRADUATION_ADMIN 拥有 graduationDesign.* 全权，应放行到业务层（记录不存在 404，而非权限层 403）
    h = _role_token("GRADUATION_ADMIN")
    r = graduation_client.post("/api/v1/graduation/gd-grades/999999/publish", headers=h)
    assert r.status_code != 403, f"GRADUATION_ADMIN 应放行到业务层，实际卡在权限层 {r.status_code}"


# GET /graduation/context 审计整改：此前前端 permissionActions 是静态常量，所有角色一律
# allowed:true。现按真实 permissionCode 逐项判定，回归证明「无权限角色拿到 false，全权角色拿到 true」。
def test_context_reflects_real_permission_per_role(graduation_client, db_mode):
    mentor = graduation_client.get("/api/v1/graduation/context", headers=_role_token("GD_MENTOR")).json()["data"]
    assert mentor["permissionActions"]["createBatch"] is False, "GD_MENTOR 无 manage 权限，createBatch 应为 false"
    assert mentor["fullScope"] is False

    admin = graduation_client.get("/api/v1/graduation/context", headers=_role_token("GRADUATION_ADMIN")).json()["data"]
    assert admin["permissionActions"]["createBatch"] is True, "GRADUATION_ADMIN 拥有 manage 权限，createBatch 应为 true"
    assert admin["permissionActions"]["publishDefense"] is True
    assert admin["fullScope"] is True
