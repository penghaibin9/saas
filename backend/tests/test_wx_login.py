"""微信一键登录 + 首次绑定测试。

monkeypatch wx_auth_service.code2session 注入固定 openid，不触发真实 httpx / 微信服务器。
复用 demo-school 真实账号（student/teacher·123456）验证绑定后 openid 免密登录。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

DEMO_TID = 1000000000000000003


@pytest.fixture()
def two_tenants(db_mode):
    from app.db.session import get_sessionmaker
    from _seed_demo_school import seed_demo_school
    from _seed_two_tenants import seed_two_tenants
    db = get_sessionmaker()()
    try:
        seed_demo_school(db)
        seed_two_tenants(db)
    finally:
        db.close()
    return db_mode


def _fake_openid(monkeypatch, openid):
    from app.services import wx_auth_service
    monkeypatch.setattr(wx_auth_service, "code2session", lambda code: openid)


def test_wx_login_first_time_needs_bind(client, two_tenants, monkeypatch):
    _fake_openid(monkeypatch, "openid_new_001")
    r = client.post("/api/v1/auth/wx-login", json={"code": "any"}).json()
    assert r["code"] == 0
    assert r["data"]["needBind"] is True
    assert r["data"]["wxToken"]
    assert "accessToken" not in r["data"]  # 未绑定不发登录令牌


def test_wx_bind_then_openid_login(client, two_tenants, monkeypatch):
    _fake_openid(monkeypatch, "openid_stu_bind")
    # 1) 一键登录 → needBind + wxToken
    r1 = client.post("/api/v1/auth/wx-login", json={"code": "c1"}).json()
    wx_token = r1["data"]["wxToken"]
    # 2) 用学号/密码首次绑定 → 直接登录成功
    r2 = client.post("/api/v1/auth/wx-bind",
                     json={"wxToken": wx_token, "loginName": "student", "password": "123456"}).json()
    assert r2["code"] == 0, r2.get("message")
    assert r2["data"]["accessToken"]
    assert r2["data"]["tenantId"] == str(DEMO_TID)
    assert r2["data"]["currentRole"]["roleCode"] == "STUDENT"
    # 3) 再次一键登录（同 openid）→ 已绑定，免密直接登录，不再 needBind
    r3 = client.post("/api/v1/auth/wx-login", json={"code": "c2"}).json()
    assert r3["code"] == 0
    assert r3["data"].get("needBind") is None
    assert r3["data"]["accessToken"]
    assert r3["data"]["currentRole"]["roleCode"] == "STUDENT"
    assert r3["data"]["tenantId"] == str(DEMO_TID)


def test_wx_bind_wrong_password(client, two_tenants, monkeypatch):
    _fake_openid(monkeypatch, "openid_wrongpw")
    wx_token = client.post("/api/v1/auth/wx-login", json={"code": "c"}).json()["data"]["wxToken"]
    r = client.post("/api/v1/auth/wx-bind",
                    json={"wxToken": wx_token, "loginName": "student", "password": "WRONG"}).json()
    assert r["code"] == 401001


def test_wx_bind_bad_token(client, two_tenants, monkeypatch):
    _fake_openid(monkeypatch, "openid_x")
    r = client.post("/api/v1/auth/wx-bind",
                    json={"wxToken": "not-a-valid-token", "loginName": "student", "password": "123456"}).json()
    assert r["code"] == 401001


def test_wx_login_not_configured(client, two_tenants, monkeypatch):
    # 不 monkeypatch code2session → 走真实 _require_wx_configured；未配置 AppID/Secret → 业务错误
    from app.core.config import settings
    monkeypatch.setattr(settings, "WX_APPID", "")
    monkeypatch.setattr(settings, "WX_SECRET", "")
    r = client.post("/api/v1/auth/wx-login", json={"code": "x"}).json()
    assert r["code"] != 0
    assert "配置" in (r.get("message") or "")
    # 账号密码登录不受影响
    ok = client.post("/api/v1/auth/login", json={"loginName": "student", "password": "123456"}).json()
    assert ok["code"] == 0
