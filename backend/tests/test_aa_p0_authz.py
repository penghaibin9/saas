"""P0 · 教务旧接口权限漏挂：精确 permissionCode + 模块门禁 + 反向角色。"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _token(role: str, *, user_type: str = "TEACHER", user_id: str = "u-x"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": user_id, "realName": role, "userType": user_type,
        "tid": "demo", "tenantId": str(TID), "activeContextId": f"ctx_{role}",
        "currentRoleCode": role, "clientType": "PC",
    })}


def test_term_create_publish_denied_for_teacher_counselor_dorm_mentor(client, db_mode):
    body = {"yearCode": "2039-2040", "termNo": 1, "termName": "越权学期"}
    for login in ("academic01", "counselor01", "dorm01"):
        hdr = _hdr(client, login)
        r = client.post(f"{BASE}/terms", headers=hdr, json=body)
        assert r.status_code == 403, login
        assert r.json()["bizCode"] == "NO_PERMISSION"
    mentor = _token("INTERN_MENTOR", user_id="u_intern_mentor")
    assert client.post(f"{BASE}/terms", headers=mentor, json=body).status_code == 403


def test_term_create_publish_allowed_for_academic_and_school_admin(client, db_mode):
    aa = _token("ACADEMIC_ADMIN", user_type="ADMIN", user_id="u_aa_admin")
    created = client.post(f"{BASE}/terms", headers=aa, json={
        "yearCode": "2038-2039", "termNo": 1, "termName": "教务管理员学期",
        "startDate": "2038-09-01", "endDate": "2039-01-15", "teachingWeeks": 18,
    })
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["termId"]
    pub = client.post(f"{BASE}/terms/{tid}/publish", headers=aa)
    assert pub.status_code == 200 and pub.json()["data"]["status"] == "PUBLISHED"

    school = _hdr(client, "school_admin01")
    assert client.get(f"{BASE}/terms/current", headers=school).status_code == 200
    assert client.get(f"{BASE}/dashboard", headers=school).status_code == 200


def test_dashboard_and_term_view_teacher_ok_manage_denied(client, db_mode):
    hdr = _hdr(client, "academic01")
    assert client.get(f"{BASE}/dashboard", headers=hdr).status_code == 200
    assert client.get(f"{BASE}/terms", headers=hdr).status_code == 200
    assert client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": "2040-2041", "termNo": 1}).status_code == 403


def test_student_token_forbidden(client, db_mode):
    hdr = _hdr(client, "student01")
    assert client.get(f"{BASE}/dashboard", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": "2041-2042", "termNo": 1}).status_code == 403


def test_module_not_authorized_academic_affairs(client, db_mode, monkeypatch):
    monkeypatch.setattr("app.services.platform_service.feature_enabled",
                        lambda tid, key: False if key == "academicAffairs" else True)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/dashboard", headers=hdr)
    assert r.status_code == 403
    assert r.json()["bizCode"] == "NO_PERMISSION"
