"""P5.5A：refresh / logout 失效 / 登录锁定 / 限流。"""
from __future__ import annotations


def _login(client, name="school_admin01"):
    return client.post("/api/v1/auth/mock-login",
                       json={"loginName": name, "password": "x"}).json()["data"]


def test_refresh_rotation(client):
    d = _login(client)
    assert d["refreshToken"] and len(d["refreshToken"]) > 20
    r1 = client.post("/api/v1/auth/refresh", json={"refreshToken": d["refreshToken"]}).json()
    assert r1["code"] == 0 and r1["data"]["accessToken"] and r1["data"]["refreshToken"]
    # 旧 refresh 已轮换作废
    r2 = client.post("/api/v1/auth/refresh", json={"refreshToken": d["refreshToken"]}).json()
    assert r2["code"] == 401001
    # 新 access 可用
    me = client.get("/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {r1['data']['accessToken']}"}).json()
    assert me["code"] == 0


def test_logout_invalidates_access_token(client):
    d = _login(client)
    hd = {"Authorization": f"Bearer {d['accessToken']}"}
    assert client.get("/api/v1/auth/me", headers=hd).json()["code"] == 0
    out = client.post("/api/v1/auth/logout", headers=hd).json()
    assert out["code"] == 0 and out["data"]["tokenInvalidated"] is True
    again = client.get("/api/v1/auth/me", headers=hd).json()
    assert again["code"] == 401001  # jti 黑名单生效
    # refreshToken 一并吊销
    r = client.post("/api/v1/auth/refresh", json={"refreshToken": d["refreshToken"]}).json()
    assert r["code"] == 401001


def test_login_rate_limit_10_per_minute(client, monkeypatch):
    # P0 风控切换到 MySQL authority 后，限流桶会跨请求持久存在；前序 refresh/logout
    # 用例也会真实经过 mock-login。这个测试只固定自身 request meta 的来源 IP，从而得到
    # 独立的持久化 bucket；限流实现仍走真实 Redis/MySQL authority。代理/XFF 信任边界由
    # 下方独立安全合同覆盖，禁止通过伪造 X-Forwarded-For 来隔离本用例。
    from app.api.v1 import auth as auth_api
    monkeypatch.setattr(auth_api, "get_request_meta", lambda: {"ip": "203.0.113.210"})

    for _ in range(10):
        assert client.post("/api/v1/auth/mock-login",
                           json={"loginName": "school_admin01", "password": "x"}).json()["code"] == 0
    r = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "school_admin01", "password": "x"}).json()
    assert r["code"] == 429001 and r["bizCode"] == "RATE_LIMITED"


def test_password_login_lockout(client, db_mode, monkeypatch):
    # 图形验证码门禁有独立专项覆盖；本用例保留真实 HTTP 登录链，只隔离挑战层，
    # 验证错误密码计数、锁定和审计不会因验证码策略升级而失去回归保护。
    from app.api.v1 import auth as auth_api
    monkeypatch.setattr(auth_api.captcha_svc, "enforce_login_captcha",
                        lambda *_args, **_kwargs: None)
    # auth/login 是 tenant-neutral；夹具没有 admin_demo 的真实 User 行，因此必须显式给出
    # 已存在的测试租户 demo，才能验证失败登录审计的真实学校归属。禁止依赖默认租户猜测。
    failure_codes = set()
    for i in range(5):
        r = client.post("/api/v1/auth/login",
                        json={"tenantCode": "demo", "loginName": "admin_demo", "password": f"wrong-{i}"}).json()
        assert r["code"] == 401001
        failure_codes.add(r["bizCode"])
    assert "CAPTCHA_REQUIRED" in failure_codes
    locked = client.post("/api/v1/auth/login",
                         json={"tenantCode": "demo", "loginName": "admin_demo", "password": "wrong-final"}).json()
    assert locked["code"] == 401001 and "锁定" in locked["message"]
    # 审计里能查到 LOGIN_FAIL 与 LOGIN_LOCKED
    tk = _login(client)["accessToken"]
    logs = client.get("/api/v1/audit/logs?pageSize=100",
                      headers={"Authorization": f"Bearer {tk}"}).json()["data"]["items"]
    actions = {x["action"] for x in logs}
    assert "LOGIN_FAIL" in actions and "LOGIN_LOCKED" in actions


def test_export_rate_limit_5_per_minute(client, auth_headers, db_mode):
    for _ in range(5):
        assert client.post("/api/v1/export/students", headers=auth_headers,
                           json={"purpose": "限流验证批量导出"}).json()["code"] == 0
    r = client.post("/api/v1/export/students", headers=auth_headers,
                    json={"purpose": "限流验证批量导出"}).json()
    assert r["code"] == 429001


# ── P0-1：真实客户端 IP 解析（可信代理才吃 X-Forwarded-For，防全校共享限流桶/审计串源） ──

def test_client_ip_trusts_xff_only_from_trusted_proxy():
    from types import SimpleNamespace
    from app.middleware.context import _resolve_client_ip

    def fake_request(direct_ip, headers):
        return SimpleNamespace(client=SimpleNamespace(host=direct_ip), headers=headers)

    # 直连方是可信代理（默认 127.0.0.1）→ 取 X-Forwarded-For 第一跳
    r = fake_request("127.0.0.1", {"x-forwarded-for": "203.0.113.7, 10.0.0.2"})
    assert _resolve_client_ip(r) == "203.0.113.7"
    # 可信代理 + 只有 X-Real-IP → 取 X-Real-IP
    r = fake_request("127.0.0.1", {"x-real-ip": "198.51.100.9"})
    assert _resolve_client_ip(r) == "198.51.100.9"
    # 直连方不可信 → 头部一律忽略，防伪造
    r = fake_request("192.0.2.50", {"x-forwarded-for": "1.2.3.4"})
    assert _resolve_client_ip(r) == "192.0.2.50"
    # 可信代理但没带头 → 回落直连 IP
    r = fake_request("127.0.0.1", {})
    assert _resolve_client_ip(r) == "127.0.0.1"
