"""PLAT-10 问题管理、已知错误与事故复盘（真库）。

覆盖：①事件转 Problem 幂等（同一事件重复申请不产生第二条）；②标记已知
错误前必须有临时规避方案；③非法状态回退被拒绝；④永久修复必须链接一个
真实存在的变更（复用 PLAT-11 的 get_change 校验，不接受空引用）；⑤复盘
发布前问题必须已解决且复盘内容完整；⑥总览是真实统计。
"""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException

TID = 1000000000000000071


@pytest.fixture()
def tenant_ctx(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(id=TID, tenant_code=f"plat10-{TID}", school_name="问题管理测试学校", status="ACTIVE"))
            db.commit()
    finally:
        db.close()
    yield TID


# ── PLAT10-T01：事件转 Problem 幂等，不产生第二条 ──────────────────────────
def test_t01_create_problem_from_incident_is_idempotent(tenant_ctx):
    from app.services import problem_management_service as prob

    p1 = prob.create_problem_from_incident(9001, title="核心接口不可用")
    p2 = prob.create_problem_from_incident(9001, title="核心接口不可用（重复申请）")
    assert p1["id"] == p2["id"]
    items = prob.list_problems()
    assert sum(1 for p in items if p["sourceIncidentId"] == "9001") == 1


# ── PLAT10-T02：标记已知错误前必须有临时规避方案 ───────────────────────────
def test_t02_known_error_requires_workaround(tenant_ctx):
    from app.services import problem_management_service as prob

    problem = prob.create_problem(title="登录偶发失败")
    with pytest.raises(AppException) as exc:
        prob.transition_status(int(problem["id"]), target_status="KNOWN_ERROR",
                               expected_version=problem["version"])
    assert exc.value.code == "VALIDATION_ERROR"

    prob.update_root_cause(int(problem["id"]), root_cause="连接池耗尽", workaround="重启应用实例",
                           expected_version=problem["version"])
    updated = prob.transition_status(int(problem["id"]), target_status="KNOWN_ERROR", expected_version=1)
    assert updated["status"] == "KNOWN_ERROR"
    assert updated["knownErrorPublished"] is True


# ── PLAT10-T03：CLOSED 是终态，不允许再流转 ────────────────────────────────
def test_t03_closed_is_terminal_state(tenant_ctx):
    from app.services import problem_management_service as prob

    problem = prob.create_problem(title="临时问题")
    prob.transition_status(int(problem["id"]), target_status="INVESTIGATING", expected_version=0)
    prob.transition_status(int(problem["id"]), target_status="RESOLVED", expected_version=1)
    prob.transition_status(int(problem["id"]), target_status="CLOSED", expected_version=2)
    with pytest.raises(AppException) as exc:
        prob.transition_status(int(problem["id"]), target_status="INVESTIGATING", expected_version=3)
    assert exc.value.code == "STATE_TRANSITION_DENIED"


# ── PLAT10-T04：永久修复必须链接真实存在的变更 ─────────────────────────────
def test_t04_permanent_fix_must_reference_real_change(tenant_ctx):
    from app.services import change_management_service as chg
    from app.services import problem_management_service as prob

    problem = prob.create_problem(title="需要代码修复的问题")
    with pytest.raises(AppException) as exc:
        prob.link_permanent_fix(int(problem["id"]), change_id=999999999, expected_version=0)
    assert exc.value.code == "DATA_NOT_FOUND"

    change = chg.create_change({"userId": "u-1"}, {
        "title": "修复连接池泄漏", "changeType": "HOTFIX", "affectedServiceCodes": ["svc_api"],
    })
    linked = prob.link_permanent_fix(int(problem["id"]), change_id=int(change["changeId"]), expected_version=0)
    assert linked["permanentFixChangeId"] == str(change["changeId"])


# ── PLAT10-T05：复盘发布前问题必须已解决，且内容不能是空壳 ────────────────
def test_t05_postmortem_publish_requires_resolved_problem_and_complete_content(tenant_ctx):
    from app.services import problem_management_service as prob

    problem = prob.create_problem(title="需要复盘的问题")
    pm = prob.create_postmortem(int(problem["id"]), what_happened="", action_items=[])
    with pytest.raises(AppException) as exc:
        prob.publish_postmortem(int(pm["id"]), expected_version=0)
    assert exc.value.code == "DATA_CONFLICT"  # 问题还没 RESOLVED

    prob.transition_status(int(problem["id"]), target_status="INVESTIGATING", expected_version=0)
    prob.transition_status(int(problem["id"]), target_status="RESOLVED", expected_version=1)
    with pytest.raises(AppException) as exc2:
        prob.publish_postmortem(int(pm["id"]), expected_version=0)
    assert exc2.value.code == "VALIDATION_ERROR"  # 已解决但内容是空壳

    pm2 = prob.create_postmortem(int(problem["id"]), what_happened="连接池耗尽导致登录失败",
                                 action_items=["加连接池监控", "补充自动扩容"])
    published = prob.publish_postmortem(int(pm2["id"]), expected_version=0)
    assert published["published"] is True


# ── PLAT10-T06：总览是真实统计 ──────────────────────────────────────────────
def test_t06_governance_overview_reflects_real_counts(tenant_ctx):
    from app.services import problem_management_service as prob

    before = prob.governance_overview()
    prob.create_problem(title="统计用问题-无根因")
    after = prob.governance_overview()
    assert after["openCount"] == before["openCount"] + 1
    assert after["withoutRootCauseCount"] == before["withoutRootCauseCount"] + 1


# ── HTTP：事件转 Problem 端到端落地一条真实 Problem 记录 ─────────────────
def test_http_incident_conversion_creates_real_problem_and_capability_gate(client, tenant_ctx):
    from app.core.security import create_access_token
    from app.models.incident import Incident, IncidentTenant
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        incident = Incident(title="HTTP冒烟事件", severity="P2", status="RESOLVED",
                            affected_service_codes_json=["svc_x"])
        db.add(incident)
        db.flush()
        db.add(IncidentTenant(incident_id=incident.id, tenant_id=TID, impact_type="DIRECT"))
        db.commit()
        incident_id = incident.id
    finally:
        db.close()

    admin_token = create_access_token({
        "userId": "u-plat10-owner", "realName": "平台超管", "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform", "tenantId": "0", "activeContextId": "ctx",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN", "clientType": "PC"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    r = client.post(f"/api/v1/platform/incidents/{incident_id}/request-problem-conversion", headers=headers)
    body = r.json()
    assert body["code"] == 0, body
    problem_id = body["data"]["problemId"]

    r = client.get(f"/api/v1/platform/problems/{problem_id}", headers=headers)
    detail = r.json()
    assert detail["code"] == 0, detail
    assert detail["data"]["sourceIncidentId"] == str(incident_id)

    school_token = create_access_token({
        "userId": "u-plat10-school", "realName": "校级管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})
    r = client.get("/api/v1/platform/problems/overview", headers={"Authorization": f"Bearer {school_token}"})
    assert r.status_code == 403
