"""学生 PC 门户 · 家长（proxy）安全合同（MySQL 真库 via db_mode）。

覆盖：
- 家长短信 OTP 登录已正式停用，已授权/未授权手机号都必须 fail-closed；
- 已由受信身份链验证并签发的 GUARDIAN 令牌仍只能读取学生明确授权的范围；
- GUARDIAN 令牌必须被老师端 require_staff 拦截。
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


def _guardian_token(phone: str):
    """代表由受信身份链完成验证后的 GUARDIAN 令牌；不恢复已停用的短信登录。"""
    from app.core.security import create_access_token
    from app.student_portal.services.parent_link_service import _phone_hash

    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"guardian-{phone[-4:]}",
        "userType": "GUARDIAN",
        "tid": "x",
        "tenantId": str(TID),
        "guardianPhoneHash": _phone_hash(phone),
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
    r = client.post(f"{PORTAL}/parent/guardians", headers=h, json={
        "guardianName": "家长" + name, "guardianPhone": phone, "relation": "FATHER",
        "visibleScopes": list(scopes)}).json()
    assert r["code"] == 0
    return h


def test_guardian_sms_login_is_fail_closed_for_authorized_phone(client, db_mode):
    phone = "13800138777"
    _bind(client, "GRD-001", "王同学", phone)

    otp = client.post(f"{PORTAL}/guardian/otp", json={"phone": phone}).json()
    login = client.post(
        f"{PORTAL}/guardian/login", json={"phone": phone, "code": "123456"}
    ).json()

    assert otp["code"] == 403001
    assert login["code"] == 403001


def test_guardian_sms_login_does_not_enumerate_unbound_phone(client, db_mode):
    phone = "13999999999"
    otp = client.post(f"{PORTAL}/guardian/otp", json={"phone": phone}).json()
    login = client.post(
        f"{PORTAL}/guardian/login", json={"phone": phone, "code": "123456"}
    ).json()

    assert otp["code"] == 403001
    assert login["code"] == 403001


def test_verified_guardian_token_can_only_view_authorized_student_scope(client, db_mode):
    phone = "13800138778"
    _bind(client, "GRD-002", "李同学", phone)

    st = client.get(f"{PORTAL}/guardian/students", headers=_guardian_token(phone)).json()
    assert st["code"] == 0 and st["data"]["hasData"] is True
    item = st["data"]["items"][0]
    assert item["studentName"] == "李同学" and item["studentNo"] == "GRD-002"
    assert set(item["visibleScopes"]) == {"ACADEMIC_GRADE", "CAMPUS_ALERT"}


def test_guardian_token_blocked_from_staff(client, db_mode):
    phone = "13800138779"
    _bind(client, "GRD-003", "赵同学", phone)
    assert client.get("/api/v1/students", headers=_guardian_token(phone)).json()["code"] == 403001
