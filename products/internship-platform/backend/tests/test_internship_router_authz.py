"""P3 · 岗位实习主路由（internship.py，104 端点）细粒度权限负向测试。

前端菜单投影只是展示，后端 require_permission 才是安全边界。本文件锁定既有域测试
未覆盖的新边界：辅导员/督导只读协同，导师写操作限本人学生工作流（不得触碰成绩权重配置、
成绩台账导出、企业库/批次组织级管理），未登记角色一律拒绝。数据范围(本人学生)由 service
owner scope 另行收敛，本文件只验角色级 permissionCode 门禁。
"""
from __future__ import annotations

BASE = "/api/v1/internship"
TID = 1000000000000000001


def _tok(role, user_type="TEACHER", client_type="PC"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{role}", "realName": role, "userType": user_type,
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": role, "clientType": client_type})}


def _batch_id(db_mode):
    """dashboard/risks 等看板类接口现已要求显式 batchId，直接建库省一次 HTTP 往返。"""
    from uuid import uuid4
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch
    db = get_sessionmaker()()
    try:
        b = InternshipBatch(tenant_id=TID, batch_name="路由权限测试批次",
                            batch_no=f"AUTHZB-{uuid4().hex[:8]}", status="RUNNING", planned_count=5)
        db.add(b); db.commit()
        return b.id
    finally:
        db.close()


def test_counselor_read_only(client, db_mode):
    """辅导员：本班实习学生只读协同（看板/周报/风险可读），不得处理/批阅/导出/核算。"""
    c = _tok("COUNSELOR")
    bid = _batch_id(db_mode)
    assert client.get(f"{BASE}/dashboard", headers=c, params={"batchId": bid}).status_code == 200  # dashboard.view
    assert client.get(f"{BASE}/reports", headers=c, params={"batchId": bid}).status_code == 200  # report.view
    # 写/处理/导出/成绩：辅导员无权
    assert client.post(f"{BASE}/exceptions/x/handle", headers=c,
                       json={"action": "REASONABLE", "comment": "已核实"}).status_code == 403  # attendance.review
    assert client.post(f"{BASE}/reports/x/review", headers=c,
                       json={"action": "APPROVE", "comment": ""}).status_code == 403           # report.review
    assert client.post(f"{BASE}/checkins/export", headers=c).status_code == 403               # attendance.export
    assert client.post(f"{BASE}/scores/compute", headers=c, json={}).status_code == 403        # score.manage


def test_mentor_management_boundaries(client, db_mode):
    """导师：本人指导学生工作流内可写（另见既有域测试），但不得触碰组织级/校级管理。"""
    m = _tok("INTERN_MENTOR")
    assert client.post(f"{BASE}/scores/config", headers=m, json={}).status_code == 403     # score.config（权重配置归校/院）
    assert client.post(f"{BASE}/scores/export", headers=m).status_code == 403              # score.export（成绩台账导出）
    assert client.post(f"{BASE}/enterprises", headers=m, json={}).status_code == 403       # enterprise.manage（企业库管理）
    assert client.post(f"{BASE}/batches", headers=m, json={}).status_code == 403           # batch.manage（批次组织）
    assert client.post(f"{BASE}/enterprises/x/blacklist", headers=m,
                       json={"on": True}).status_code == 403                                # enterprise.manage


def test_security_auditor_read_only(client, db_mode):
    """实习督导/审计：只读监督，不授予任何写操作。"""
    a = _tok("SECURITY_AUDITOR")
    bid = _batch_id(db_mode)
    assert client.get(f"{BASE}/risks", headers=a, params={"batchId": bid}).status_code == 200  # risk.view
    assert client.post(f"{BASE}/risks/x/handle", headers=a,
                       json={"comment": "越权受理"}).status_code == 403                     # risk.handle
    assert client.post(f"{BASE}/scores/x/publish", headers=a).status_code == 403           # score.publish


def test_unregistered_role_denied(client, db_mode):
    """未登记角色（真实教职工但无实习授权）→ 默认拒绝。"""
    u = _tok("SOME_CUSTOM_ROLE")
    assert client.get(f"{BASE}/reports", headers=u).status_code == 403
    assert client.get(f"{BASE}/dashboard", headers=u).status_code == 403
