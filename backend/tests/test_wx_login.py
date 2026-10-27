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
SANDBOX_TID = 1000000000000000007
STUDENT_MINI = "STUDENT_MINI"
TEACHER_MINI = "TEACHER_MINI"


@pytest.fixture()
def two_tenants(db_mode):
    from app.db.session import get_sessionmaker
    from _seed_demo_school import seed_demo_school
    from _seed_two_tenants import seed_two_tenants
    from sqlalchemy import select
    from app.models import User, Role, UserRole
    db = get_sessionmaker()()
    try:
        seed_demo_school(db)
        seed_two_tenants(db)
        # 旧演示种子只建账号；登录测试显式准备有效任职，不依赖运行时按账号类型授予角色。
        for tenant_id, login_name, role_code in [(DEMO_TID, 'student', 'STUDENT'),
                (DEMO_TID, 'teacher', 'TEACHER'), (SANDBOX_TID, 'student2', 'STUDENT')]:
            user = db.scalars(select(User).where(User.tenant_id == tenant_id, User.login_name == login_name)).one()
            role = db.scalars(select(Role).where(Role.tenant_id == tenant_id, Role.role_code == role_code)).first()
            if role is None:
                role = Role(tenant_id=tenant_id, role_code=role_code, role_name='学生' if role_code == 'STUDENT' else '教师', role_type='SYSTEM', status='ACTIVE')
                db.add(role)
                db.flush()
            if db.scalars(select(UserRole).where(UserRole.tenant_id == tenant_id, UserRole.user_id == user.id, UserRole.role_id == role.id)).first() is None:
                db.add(UserRole(tenant_id=tenant_id, user_id=user.id, role_id=role.id, status='ACTIVE'))
        db.commit()
    finally:
        db.close()
    return db_mode


def _fake_openid(monkeypatch, openid):
    from app.services import wx_auth_service
    monkeypatch.setattr(wx_auth_service, "code2session", lambda code: openid)


def _approval(login_name, tenant_id, openid):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import User
    from app.services.wx_binding_approval_service import issue_in_session
    with get_sessionmaker()() as db:
        user = db.scalars(select(User).where(User.tenant_id == tenant_id, User.login_name == login_name)).one()
        ticket = issue_in_session(db, tenant_id=tenant_id, user_id=user.id, expected_version=user.version,
            openid=openid, incident_ref='D613-ISOLATED-LOGIN-CHECK', operator='os:pytest', identity_verified=True)
        db.commit()
        return ticket['bindingApprovalToken']


def test_wx_login_first_time_needs_bind(client, two_tenants, monkeypatch):
    _fake_openid(monkeypatch, "openid_new_001")
    r = client.post("/api/v1/auth/wx-login", json={"code": "any", "clientType": STUDENT_MINI}).json()
    assert r["code"] == 0
    assert r["data"]["needBind"] is True
    assert r["data"]["wxToken"]
    assert "accessToken" not in r["data"]  # 未绑定不发登录令牌


def test_wx_bind_then_openid_login(client, two_tenants, monkeypatch):
    _fake_openid(monkeypatch, "openid_stu_bind")
    # 1) 一键登录 → needBind + wxToken
    r1 = client.post("/api/v1/auth/wx-login", json={"code": "c1", "clientType": STUDENT_MINI}).json()
    wx_token = r1["data"]["wxToken"]
    # 2) 用学号/密码首次绑定 → 直接登录成功
    r2 = client.post("/api/v1/auth/wx-bind",
                     json={"wxToken": wx_token, "tenantCode": "demo-school", "loginName": "student", "password": "123456", "clientType": STUDENT_MINI,
                           "bindingApprovalToken": _approval('student', DEMO_TID, 'openid_stu_bind')}).json()
    assert r2["code"] == 0, r2.get("message")
    assert r2["data"]["accessToken"]
    assert r2["data"]["tenantId"] == str(DEMO_TID)
    assert r2["data"]["currentRole"]["roleCode"] == "STUDENT"
    # 3) 再次一键登录（同 openid）→ 已绑定，免密直接登录，不再 needBind
    r3 = client.post("/api/v1/auth/wx-login", json={"code": "c2", "clientType": STUDENT_MINI}).json()
    assert r3["code"] == 0
    assert r3["data"].get("needBind") is None
    assert r3["data"]["accessToken"]
    assert r3["data"]["currentRole"]["roleCode"] == "STUDENT"
    assert r3["data"]["tenantId"] == str(DEMO_TID)


def test_one_wechat_can_select_between_two_schools(client, two_tenants, monkeypatch):
    _fake_openid(monkeypatch, "openid_multi_school")
    first_token = client.post("/api/v1/auth/wx-login", json={"code": "first", "clientType": STUDENT_MINI}).json()["data"]["wxToken"]
    first = client.post("/api/v1/auth/wx-bind", json={
        "wxToken": first_token, "tenantCode": "demo-school",
        "loginName": "student", "password": "123456", "clientType": STUDENT_MINI,
        "bindingApprovalToken": _approval('student', DEMO_TID, 'openid_multi_school'),
    }).json()
    assert first["code"] == 0 and first["data"]["tenantId"] == str(DEMO_TID)

    another = client.post("/api/v1/auth/wx-login",
                          json={"code": "another", "bindAnother": True, "clientType": STUDENT_MINI}).json()["data"]
    assert another["needBind"] is True
    second = client.post("/api/v1/auth/wx-bind", json={
        "wxToken": another["wxToken"], "tenantCode": "sandbox-school",
        "loginName": "student2", "password": "123456", "clientType": STUDENT_MINI,
        "bindingApprovalToken": _approval('student2', SANDBOX_TID, 'openid_multi_school'),
    }).json()
    assert second["code"] == 0 and second["data"]["tenantId"] == str(SANDBOX_TID)

    choices = client.post("/api/v1/auth/wx-login", json={"code": "choose", "clientType": STUDENT_MINI}).json()["data"]
    assert choices["needSelectTenant"] is True
    assert {item["tenantCode"] for item in choices["accounts"]} == {"demo-school", "sandbox-school"}
    selected = client.post("/api/v1/auth/wx-select", json={
        "wxToken": choices["wxToken"], "tenantCode": "demo-school", "clientType": STUDENT_MINI,
    }).json()
    assert selected["code"] == 0 and selected["data"]["tenantId"] == str(DEMO_TID)


def test_wx_bind_wrong_password(client, two_tenants, monkeypatch):
    _fake_openid(monkeypatch, "openid_wrongpw")
    wx_token = client.post("/api/v1/auth/wx-login", json={"code": "c", "clientType": STUDENT_MINI}).json()["data"]["wxToken"]
    r = client.post("/api/v1/auth/wx-bind",
                    json={"wxToken": wx_token, "loginName": "student", "password": "WRONG", "clientType": STUDENT_MINI}).json()
    assert r["code"] == 401001


def test_wx_bind_bad_token(client, two_tenants, monkeypatch):
    _fake_openid(monkeypatch, "openid_x")
    r = client.post("/api/v1/auth/wx-bind",
                    json={"wxToken": "not-a-valid-token", "loginName": "student", "password": "123456", "clientType": STUDENT_MINI}).json()
    assert r["code"] == 401001


def test_wx_login_not_configured(client, two_tenants, monkeypatch):
    # 不 monkeypatch code2session → 走真实 _require_wx_configured；未配置 AppID/Secret → 业务错误
    from app.core.config import settings
    monkeypatch.setattr(settings, "WX_APPID", "")
    monkeypatch.setattr(settings, "WX_SECRET", "")
    r = client.post("/api/v1/auth/wx-login", json={"code": "x", "clientType": STUDENT_MINI}).json()
    assert r["code"] != 0
    assert "配置" in (r.get("message") or "")
    # 账号密码登录不受影响
    ok = client.post("/api/v1/auth/login", json={"tenantCode": "demo-school", "loginName": "student", "password": "123456"}).json()
    assert ok["code"] == 0


def test_wx_login_cannot_issue_a_student_mini_session_for_a_teacher_binding(client, two_tenants, monkeypatch):
    _fake_openid(monkeypatch, "openid_teacher_side")
    token = client.post("/api/v1/auth/wx-login", json={
        "code": "teacher-bind", "clientType": TEACHER_MINI,
    }).json()["data"]["wxToken"]
    bound = client.post("/api/v1/auth/wx-bind", json={
        "wxToken": token, "tenantCode": "demo-school", "loginName": "teacher", "password": "123456", "clientType": TEACHER_MINI,
        "bindingApprovalToken": _approval('teacher', DEMO_TID, 'openid_teacher_side'),
    }).json()
    assert bound["code"] == 0
    assert bound["data"]["currentRole"]["roleCode"] in {"COUNSELOR", "TEACHER", "GD_MENTOR"}

    wrong_side = client.post("/api/v1/auth/wx-login", json={
        "code": "student-side", "clientType": STUDENT_MINI,
    }).json()
    assert wrong_side["code"] == 403001


def test_wx_select_token_is_bound_to_its_original_mini_side(client, two_tenants, monkeypatch):
    _fake_openid(monkeypatch, "openid_select_side")
    first_token = client.post("/api/v1/auth/wx-login", json={"code": "first", "clientType": STUDENT_MINI}).json()["data"]["wxToken"]
    assert client.post("/api/v1/auth/wx-bind", json={
        "wxToken": first_token, "tenantCode": "demo-school", "loginName": "student", "password": "123456", "clientType": STUDENT_MINI,
        "bindingApprovalToken": _approval('student', DEMO_TID, 'openid_select_side'),
    }).json()["code"] == 0
    second_token = client.post("/api/v1/auth/wx-login", json={
        "code": "second", "bindAnother": True, "clientType": STUDENT_MINI,
    }).json()["data"]["wxToken"]
    assert client.post("/api/v1/auth/wx-bind", json={
        "wxToken": second_token, "tenantCode": "sandbox-school", "loginName": "student2", "password": "123456", "clientType": STUDENT_MINI,
        "bindingApprovalToken": _approval('student2', SANDBOX_TID, 'openid_select_side'),
    }).json()["code"] == 0
    choices = client.post("/api/v1/auth/wx-login", json={"code": "choices", "clientType": STUDENT_MINI}).json()["data"]

    mismatched = client.post("/api/v1/auth/wx-select", json={
        "wxToken": choices["wxToken"], "tenantCode": "demo-school", "clientType": TEACHER_MINI,
    }).json()
    assert mismatched["code"] == 401001
    selected = client.post("/api/v1/auth/wx-select", json={
        "wxToken": choices["wxToken"], "tenantCode": "sandbox-school", "clientType": STUDENT_MINI,
    }).json()
    assert selected["code"] == 0 and selected["data"]["tenantId"] == str(SANDBOX_TID)
