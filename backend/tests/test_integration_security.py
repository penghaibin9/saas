"""SYS-20 集成连接、同步与失败治理（真库）。

对应必测 SYS20-T01～T04：
私网保留地址与DNS重绑定阻断 / 凭证轮换不返回明文 /
无executor不能成功 / 同步重试幂等且可解释差异。

不新建表——沿用 system_governance_service.py 已有的 SystemJsonDoc 治理文档
(DOC_INTEGRATIONS/DOC_SYNC_JOBS)，本卡新增的是 SSRF 安全校验
（integration_security_service.py）与围绕它的回归锁。
"""
import pytest

from app.core.context import set_tenant
from app.core.exceptions import AppException

MAIN_TID = 1000000000000000001
ADMIN = {"userId": "db-1", "realName": "系统管理员", "currentRoleCode": "SCHOOL_ADMIN"}


@pytest.fixture()
def tenant_ctx(db_mode):
    from app.models import Tenant
    from app.services import platform_service as platform
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, MAIN_TID) is None:
            db.add(Tenant(id=MAIN_TID, tenant_code="demo", school_name="集成安全测试学校", status="ACTIVE"))
            db.commit()
    finally:
        db.close()
    platform.put_config_json(MAIN_TID, "TENANT_META", "-", {"status": "active", "packageCode": "professional"})
    set_tenant({"tenantId": str(MAIN_TID)})
    try:
        yield MAIN_TID
    finally:
        set_tenant(None)


# ── SYS20-T01：私网保留地址与DNS重绑定阻断 ───────────────────────────────────
def test_t01_private_ip_literal_host_rejected(tenant_ctx):
    from app.services import integration_security_service as isec

    with pytest.raises(AppException) as exc:
        isec.validate_endpoint_ssrf_safe("https://192.168.1.10/api")
    assert exc.value.http_status == 422
    assert "私网" in exc.value.message or "保留" in exc.value.message


def test_t01b_link_local_metadata_ip_rejected(tenant_ctx):
    """169.254.169.254 是云环境典型的元数据端点，SSRF 攻击常见目标。"""
    from app.services import integration_security_service as isec

    with pytest.raises(AppException):
        isec.validate_endpoint_ssrf_safe("https://169.254.169.254/latest/meta-data")


def test_t01c_public_domain_resolving_to_private_ip_rejected(tenant_ctx, monkeypatch):
    """模拟 DNS 重绑定：域名解析出内网IP，即便域名本身"看起来"是外部域名也要拒绝。"""
    import socket

    from app.services import integration_security_service as isec

    def _fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
    with pytest.raises(AppException) as exc:
        isec.validate_endpoint_ssrf_safe("https://looks-external.example.com/webhook")
    assert "10.0.0.5" in str(exc.value.details or {})


def test_t01d_public_ip_passes(tenant_ctx, monkeypatch):
    import socket

    from app.services import integration_security_service as isec

    def _fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
    info = isec.validate_endpoint_ssrf_safe("https://real-external.example.com/webhook")
    assert info["ips"] == ["8.8.8.8"]


def test_t01e_connect_reuses_same_resolution_for_validate_and_connect(tenant_ctx, monkeypatch):
    """连接前的解析只应发生一次：校验用的IP列表必须原样传给实际连接，
    不能在中间再对 hostname 做第二次系统DNS查询（否则留下重绑定窗口）。"""
    import socket

    from app.services import integration_security_service as isec

    calls = {"getaddrinfo": 0}

    def _fake_getaddrinfo(host, port, *args, **kwargs):
        calls["getaddrinfo"] += 1
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))]

    def _fake_create_connection(addr, timeout=None):
        assert addr[0] == "8.8.8.8"  # 必须是校验阶段解析出的同一个IP
        raise ConnectionRefusedError("no real service listening, expected in test")

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
    monkeypatch.setattr(socket, "create_connection", _fake_create_connection)
    with pytest.raises(AppException):
        isec.connect_ssrf_safe("https://real-external.example.com/webhook", timeout=1)
    assert calls["getaddrinfo"] == 1  # 只解析了一次


def test_t01f_localhost_blocked_in_prod(tenant_ctx, monkeypatch):
    from app.core.config import settings
    from app.services import integration_security_service as isec

    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(AppException):
        isec.validate_endpoint_ssrf_safe("http://127.0.0.1:9200/status")


# ── SYS20-T02：凭证轮换不返回明文 ────────────────────────────────────────────
def test_t02_credential_rotation_never_returns_plaintext(tenant_ctx, monkeypatch):
    import socket

    from app.services import system_governance_service as gov

    def _fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))]
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)

    saved = gov.save_integration(ADMIN, {
        "name": "SYS20测试连接", "endpoint": "https://real-external.example.com/api",
        "authType": "TOKEN", "credential": "sk-super-secret-plaintext-001"})
    assert "credential" not in saved and "credentialEncrypted" not in saved
    assert saved["credentialMasked"] != "sk-super-secret-plaintext-001"

    rotated = gov.rotate_integration_credential(ADMIN, saved["id"], "sk-rotated-secret-002")
    assert "credential" not in rotated and "credentialEncrypted" not in rotated
    assert "sk-rotated-secret-002" not in str(rotated)

    listed = gov.list_integrations()
    row = next(x for x in listed if x["id"] == saved["id"])
    assert "credential" not in row and "credentialEncrypted" not in row
    assert "sk-rotated-secret-002" not in str(row)


def test_t02b_credential_rotation_rejects_short_credential(tenant_ctx, monkeypatch):
    import socket

    from app.services import system_governance_service as gov

    def _fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.4.4", 0))]
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)

    saved = gov.save_integration(ADMIN, {
        "name": "SYS20短凭证测试", "endpoint": "https://real-external.example.com/api",
        "authType": "TOKEN", "credential": "initial-ok"})
    with pytest.raises(AppException):
        gov.rotate_integration_credential(ADMIN, saved["id"], "short")


# ── SYS20-T03：无executor不能成功 ────────────────────────────────────────────
def test_t03_sync_job_without_executor_cannot_succeed(tenant_ctx):
    from app.services import system_governance_service as gov

    job = gov.enqueue_sync_job(ADMIN, {"name": "无适配器同步", "adapterCode": "NOT_REGISTERED_ADAPTER"})
    assert job["status"] == gov.SYNC_PENDING
    assert job["hasExecutor"] is False

    with pytest.raises(AppException):
        gov.run_sync_job_executor(job["id"], ADMIN)

    refreshed = next(x for x in gov.list_sync_jobs() if x["id"] == job["id"])
    assert refreshed["status"] == gov.SYNC_FAILED  # 强行跑executor：明确失败，不是静默假成功


def test_t03b_known_adapter_field_wired_correctly(tenant_ctx):
    """KNOWN_SYNC_ADAPTERS 当前为空表（禁止伪造成功）；一旦登记了适配器，
    hasExecutor 必须如实反映，不能不管登记与否都统一 True/False。"""
    from app.services import system_governance_service as gov

    assert gov.KNOWN_SYNC_ADAPTERS == {}
    job = gov.enqueue_sync_job(ADMIN, {"name": "无适配器同步2", "adapterCode": "ANYTHING"})
    assert job["hasExecutor"] is False


# ── SYS20-T04：同步重试幂等且可解释差异 ──────────────────────────────────────
def test_t04_enqueue_idempotency_key_dedups(tenant_ctx):
    from app.services import system_governance_service as gov

    first = gov.enqueue_sync_job(ADMIN, {"name": "幂等测试", "adapterCode": "X", "idempotencyKey": "sys20-t04-key"})
    second = gov.enqueue_sync_job(ADMIN, {"name": "幂等测试重复提交", "adapterCode": "X",
                                          "idempotencyKey": "sys20-t04-key"})
    assert first["id"] == second["id"]
    assert second["name"] == "幂等测试"  # 命中去重返回既有行，不被第二次提交的内容覆盖

    all_jobs = [j for j in gov.list_sync_jobs() if j.get("idempotencyKey") == "sys20-t04-key"]
    assert len(all_jobs) == 1


def test_t04b_retry_is_explainable_and_reversible(tenant_ctx):
    from app.services import system_governance_service as gov

    job = gov.enqueue_sync_job(ADMIN, {"name": "重试可解释测试", "adapterCode": "UNKNOWN_X",
                                       "forceFail": True, "message": "上游超时"})
    assert job["status"] == gov.SYNC_FAILED
    assert job["message"] == "上游超时"

    retried = gov.retry_sync_job(ADMIN, job["id"])
    assert retried["status"] == gov.SYNC_PENDING
    assert "无真实执行器" in retried["message"]  # 差异原因明确可读，不是空白重试
    assert retried["retriedBy"] == "系统管理员"
    assert retried["version"] == int(job["version"]) + 1


def test_t04c_cancelled_job_cannot_be_retried(tenant_ctx):
    from app.services import system_governance_service as gov

    job = gov.enqueue_sync_job(ADMIN, {"name": "取消后重试测试", "adapterCode": "X"})
    gov.cancel_sync_job(ADMIN, job["id"], "不再需要该同步任务")
    with pytest.raises(AppException):
        gov.retry_sync_job(ADMIN, job["id"])


# ── HTTP 端点冒烟 ────────────────────────────────────────────────────────────
def test_http_endpoints(client, tenant_ctx, monkeypatch):
    import socket

    from app.core.security import create_access_token

    def _fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 0))]
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)

    token = create_access_token({
        "userId": "u-sys20-admin", "realName": "系统管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN_TID), "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/v1/system/integrations", headers=headers, json={
        "name": "HTTP集成测试", "endpoint": "https://real-external.example.com/hook",
        "authType": "TOKEN", "credential": "http-secret-value-001"})
    assert r.json()["code"] == 0, r.json()
    integ_id = r.json()["data"]["id"]
    assert "credential" not in r.json()["data"]

    r = client.get("/api/v1/system/integrations", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.post(f"/api/v1/system/integrations/{integ_id}/test", headers=headers)
    assert r.json()["code"] == 0, r.json()

    r = client.post(f"/api/v1/system/integrations/{integ_id}/rotate", headers=headers,
                    json={"credential": "http-secret-value-002"})
    assert r.json()["code"] == 0, r.json()
    assert "http-secret-value-002" not in str(r.json())

    r = client.post("/api/v1/system/sync-jobs", headers=headers,
                    json={"name": "HTTP同步测试", "adapterCode": "HTTP_ADAPTER"})
    assert r.json()["code"] == 0, r.json()

    r = client.get("/api/v1/system/sync-jobs", headers=headers)
    assert r.json()["code"] == 0, r.json()


def test_http_endpoint_rejects_private_ip_endpoint(client, tenant_ctx):
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": "u-sys20-admin2", "realName": "系统管理员", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN_TID), "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN", "clientType": "PC"})
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/v1/system/integrations", headers=headers, json={
        "name": "SSRF尝试", "endpoint": "https://192.168.0.1/admin", "authType": "TOKEN"})
    body = r.json()
    assert body["code"] != 0
    assert r.status_code in (400, 422)
