"""学生 PC 门户 · 家长代理只读安全边界（MySQL 真库 via db_mode）。

当前生产合同已停用家长短信验证码登录：验证短信仅允许用于找回密码。
本文件验证：旧 otp/login 始终 fail-closed；已存在的家长授权只读范围仍按 guardianPhoneHash 收敛；
GUARDIAN 令牌仍被老师端 require_staff 拦截，且授权/未授权手机号不会形成存在性 oracle。
"""
from __future__ import annotations

PORTAL = "/api/v1/portal"
TID = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC"})}


def _guardian_token(phone):
    """仅用于验证当前只读授权边界，不经过已停用的 OTP 登录入口。"""
    from app.core.security import create_access_token
    from app.student_portal.services.parent_link_service import _phone_hash

    ph = _phone_hash(phone)
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"guardian:{ph[:16]}",
        "realName": "家长",
        "userType": "GUARDIAN",
        "guardianPhoneHash": ph,
        "tid": "x",
        "tenantId": str(TID),
        "activeContextId": "guardian",
        "currentRoleCode": "GUARDIAN",
        "clientType": "PC",
    })}


def _seed_student(no, name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    s = StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="M",
                       current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
    db.add(s)
    db.commit()
    sid = s.id
    db.close()
    return sid


def _bind(client, no, name, phone, scopes=("ACADEMIC_GRADE", "CAMPUS_ALERT")):
    _seed_student(no, name)
    h = _stu_token(name, no)
    resp = client.post(f"{PORTAL}/parent/guardians", headers=h, json={
        "guardianName": "家长" + name,
        "guardianPhone": phone,
        "relation": "FATHER",
        "visibleScopes": list(scopes),
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0
    return h


def _assert_otp_disabled(client, phone):
    resp = client.post(f"{PORTAL}/guardian/otp", json={"phone": phone})
    assert resp.status_code == 403
    payload = resp.json()
    assert payload["code"] == 403001
    assert "找回密码" in payload["message"]
    assert "devCode" not in str(payload)
    return payload


def _assert_login_disabled(client, phone, code="123456"):
    resp = client.post(f"{PORTAL}/guardian/login", json={"phone": phone, "code": code})
    assert resp.status_code == 403
    payload = resp.json()
    assert payload["code"] == 403001
    assert "找回密码" in payload["message"]
    assert "accessToken" not in str(payload)
    return payload


def test_guardian_login_and_view(client, db_mode):
    """历史名称保留：登录已停用，但既有授权的只读访问仍严格按手机号哈希收敛。"""
    phone = "13800138777"
    _bind(client, "GRD-001", "王同学", phone)
    _assert_otp_disabled(client, phone)
    _assert_login_disabled(client, phone)

    st = client.get(f"{PORTAL}/guardian/students", headers=_guardian_token(phone))
    assert st.status_code == 200, st.text
    payload = st.json()
    assert payload["code"] == 0 and payload["data"]["hasData"] is True
    item = payload["data"]["items"][0]
    assert item["studentName"] == "王同学" and item["studentNo"] == "GRD-001"
    assert set(item["visibleScopes"]) == {"ACADEMIC_GRADE", "CAMPUS_ALERT"}


def test_guardian_wrong_code(client, db_mode):
    """即使手机号已获授权，旧登录入口也不再接受任何验证码。"""
    phone = "13800138778"
    _bind(client, "GRD-002", "李同学", phone)
    _assert_login_disabled(client, phone, "000000")


def test_guardian_unauthorized_phone_silent(client, db_mode):
    """授权与未授权手机号得到相同停用响应，不泄露号码是否存在授权关系。"""
    authorized = "13800138780"
    unauthorized = "13999999999"
    _bind(client, "GRD-004", "周同学", authorized)
    a = _assert_otp_disabled(client, authorized)
    b = _assert_otp_disabled(client, unauthorized)
    assert a["code"] == b["code"] == 403001
    assert a["message"] == b["message"]


def test_guardian_token_blocked_from_staff(client, db_mode):
    phone = "13800138779"
    _bind(client, "GRD-003", "赵同学", phone)
    h = _guardian_token(phone)
    # GUARDIAN 只读令牌访问老师端主档接口 → require_staff 403。
    resp = client.get("/api/v1/students", headers=h)
    assert resp.status_code == 403
    assert resp.json()["code"] == 403001
