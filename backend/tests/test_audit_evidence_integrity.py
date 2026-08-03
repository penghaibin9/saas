"""SYS-21 安全审计、敏感操作与证据（真库）。

对应必测 SYS21-T01～T03：
高危动作都有actor/tenant/object/reason/version/traceId /
审计员可查但无业务写权限 / 证据包范围与操作者权限一致。

不新表——审计权威数据是既有 t_security_audit_log，证据包走既有 t_export_job。
"""
import pytest

from app.core.context import set_tenant
from app.core.exceptions import AppException

MAIN_TID = 1000000000000000001


@pytest.fixture()
def tenant_ctx(db_mode):
    from app.models import Tenant
    from app.services import platform_service as platform
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, MAIN_TID) is None:
            db.add(Tenant(id=MAIN_TID, tenant_code="demo", school_name="审计证据测试学校", status="ACTIVE"))
            db.commit()
    finally:
        db.close()
    platform.put_config_json(MAIN_TID, "TENANT_META", "-", {"status": "active", "packageCode": "professional"})
    set_tenant({"tenantId": str(MAIN_TID)})
    try:
        yield MAIN_TID
    finally:
        set_tenant(None)


# ── SYS21-T01：高危动作都有actor/tenant/object/reason/version/traceId ────────
def test_t01_evaluate_completeness_flags_missing_reason(tenant_ctx):
    from app.services import audit_evidence_service as evid

    complete_row = {
        "auditId": "a1", "action": "PLATFORM_CHANGE_ROLLBACK", "resource": "change:123",
        "actorId": "1", "tenantId": str(MAIN_TID), "requestId": "req-abc",
        "detail": {"reason": "灰度批次失败，紧急回滚"},
    }
    incomplete_row = {
        "auditId": "a2", "action": "PLATFORM_CHANGE_ROLLBACK", "resource": "change:456",
        "actorId": "1", "tenantId": str(MAIN_TID), "requestId": "req-def",
        "detail": {},  # 缺 reason
    }
    result = evid.evaluate_evidence_completeness([complete_row, incomplete_row])
    assert result["totalHighRisk"] == 2
    assert result["gapCount"] == 1
    assert result["gaps"][0]["auditId"] == "a2"
    assert "reason" in result["gaps"][0]["missing"]


def test_t01b_low_risk_action_not_flagged_even_without_reason(tenant_ctx):
    from app.services import audit_evidence_service as evid

    row = {"auditId": "a3", "action": "LOGIN", "resource": "", "actorId": "1",
          "tenantId": str(MAIN_TID), "requestId": "req-ghi", "detail": {}}
    result = evid.evaluate_evidence_completeness([row])
    assert result["totalHighRisk"] == 0
    assert result["gapCount"] == 0


def test_t01c_version_key_present_but_null_is_flagged(tenant_ctx):
    from app.services import audit_evidence_service as evid

    row = {
        "auditId": "a4", "action": "PLATFORM_PROVISIONING_CANCEL", "resource": "job:1",
        "actorId": "1", "tenantId": str(MAIN_TID), "requestId": "req-jkl",
        "detail": {"reason": "取消开通任务", "expectedVersion": None},
    }
    result = evid.evaluate_evidence_completeness([row])
    assert result["gapCount"] == 1
    assert "version" in result["gaps"][0]["missing"]


def test_t01d_real_db_backed_evidence_query_runs_completeness(tenant_ctx):
    from app.core.context import set_current_user
    from app.services import audit_evidence_service as evid
    from app.services import audit_log

    # audit_log.record() 靠 get_current_user_ctx() 拿 actor；直接调用（不经过
    # HTTP 请求中间件）必须自己把当前用户上下文设进去，否则 actorId 记不上。
    set_current_user({"userId": "db-1", "realName": "系统管理员"})
    try:
        audit_log.record("PLATFORM_CHANGE_ROLLBACK", "change:real1",
                         detail={"reason": "真实回归锁测试回滚"}, result="SUCCESS")
    finally:
        set_current_user(None)
    out = evid.get_evidence(action="PLATFORM_CHANGE_ROLLBACK", page=1, page_size=20)
    assert out["total"] >= 1
    assert out["completeness"]["totalHighRisk"] >= 1
    assert out["completeness"]["gapCount"] == 0  # 这条记录本身完整


# ── SYS21-T02：审计员可查但无业务写权限 ──────────────────────────────────────
def test_t02_security_auditor_has_no_business_write_permission():
    from app.core.permissions import get_base_permission_patterns

    patterns = get_base_permission_patterns({"currentRoleCode": "SECURITY_AUDITOR"})
    assert "*" not in patterns
    business_write_patterns = {"systemAdmin.user.manage", "systemAdmin.role.manage",
                               "studentAffairs.leave.approve", "academicAffairs.grade.manage"}
    assert not (business_write_patterns & set(patterns))
    audit_patterns = {p for p in patterns if "audit" in p}
    assert audit_patterns  # 但确实有审计相关权限


def test_t02b_security_auditor_http_denied_on_business_write(client, tenant_ctx):
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": "u-auditor-1", "realName": "安全审计员", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN_TID), "activeContextId": "ctx",
        "currentRoleCode": "SECURITY_AUDITOR", "clientType": "PC"})
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/system/audit/overview", headers=headers)
    assert r.json()["code"] == 0, r.json()  # 能查

    r = client.post("/api/v1/system/integrations", headers=headers,
                    json={"name": "越权测试", "endpoint": "https://example.com/x"})
    assert r.status_code == 403  # 不能写业务数据


# ── SYS21-T03：证据包范围与操作者权限一致 ────────────────────────────────────
def test_t03_unrestricted_actor_gets_null_allowlist(tenant_ctx):
    from app.services import audit_evidence_service as evid

    admin = {"userId": "db-1", "currentRoleCode": "SCHOOL_ADMIN"}  # 持有 "*"
    out = evid.create_evidence_pack_job(admin, {"action": "PLATFORM_CHANGE_ROLLBACK"})
    assert out["scopeSnapshot"]["actionPrefixAllowlist"] is None

    fetched = evid.get_evidence_pack_scope(int(out["jobId"]))
    assert fetched["scopeSnapshot"]["actionPrefixAllowlist"] is None


def test_t03b_restricted_pattern_set_derives_allowed_prefixes(tenant_ctx):
    from app.services import audit_evidence_service as evid

    restricted = {"campusService.audit.view", "internship.dashboard.view"}
    prefixes = evid._allowed_action_prefixes(restricted)
    assert prefixes == {"campusService"}


def test_t03c_actor_with_no_audit_visibility_cannot_create_pack(tenant_ctx):
    from app.services import audit_evidence_service as evid

    assert evid._allowed_action_prefixes(set()) == set()

    no_audit_actor = {"userId": "db-2", "currentRoleCode": "STUDENT"}
    with pytest.raises(AppException) as exc:
        evid.create_evidence_pack_job(no_audit_actor, {})
    assert exc.value.http_status == 403


def test_t03d_cross_tenant_scope_get_returns_404(tenant_ctx):
    from app.services import audit_evidence_service as evid

    admin = {"userId": "db-1", "currentRoleCode": "SCHOOL_ADMIN"}
    out = evid.create_evidence_pack_job(admin, {})
    job_id = int(out["jobId"])

    set_tenant({"tenantId": "1000000000000099999"})
    try:
        with pytest.raises(AppException) as exc:
            evid.get_evidence_pack_scope(job_id)
        assert exc.value.http_status == 404
    finally:
        set_tenant({"tenantId": str(MAIN_TID)})


# ── HTTP 端点冒烟 ────────────────────────────────────────────────────────────
def test_http_endpoints(client, tenant_ctx):
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": "u-audit-http", "realName": "系统管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN_TID), "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/system/audit/overview", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/system/audit/evidence", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.post("/api/v1/system/audit/evidence-pack-jobs", headers=headers,
                    json={"action": "", "purpose": "HTTP冒烟测试"})
    assert r.json()["code"] == 0, r.json()
    job_id = r.json()["data"]["jobId"]

    r = client.get(f"/api/v1/system/audit/evidence-pack-jobs/{job_id}", headers=headers)
    assert r.json()["code"] == 0, r.json()
