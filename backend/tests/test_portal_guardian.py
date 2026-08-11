"""学生 PC 门户 · 家长（proxy）侧安全合同测试（MySQL 真库 via db_mode）。

当前生产安全策略：家长短信验证码登录已永久停用，`/guardian/otp` 与
`/guardian/login` 兼容端点必须始终 fail-closed。学生侧既有家长授权关系仍可维护；
GUARDIAN 身份即使存在，也必须被 `require_staff` 拦在老师端之外。
"""
from __future__ import annotations

import hashlib

PORTAL = "/api/v1/portal"
TID = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC"})}


def _guardian_token(phone):
    from app.core.security import create_access_token

    phone_hash = hashlib.sha256(phone.strip().encode("utf-8")).hexdigest()
    token = create_access_token({
        "userId": "guardian-contract-test",
        "realName": "家长安全合同",
        "userType": "GUARDIAN",
        "tid": str(TID),
        "tenantId": str(TID),
        "activeContextId": "guardian-contract",
        "currentRoleCode": "GUARDIAN",
        "clientType": "PC",
        "guardianPhoneHash": phone_hash,
    })
    return {"Authorization": f"Bearer {token}"}


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


def _assert_login_disabled(response):
    assert response.status_code == 403
    payload = response.json()
    assert payload["code"] == 403001
    data = payload.get("data")
    if isinstance(data, dict):
        assert "devCode" not in data
        assert "accessToken" not in data
    return payload


def test_guardian_binding_and_authorized_read_remain_available_while_sms_login_is_disabled(client, db_mode):
    phone = "13800138777"
    _bind(client, "GRD-001", "王同学", phone)
    st = client.get(f"{PORTAL}/guardian/students", headers=_guardian_token(phone)).json()
    assert st["code"] == 0 and st["data"]["hasData"] is True
    item = st["data"]["items"][0]
    assert item["studentName"] == "王同学" and item["studentNo"] == "GRD-001"
    assert set(item["visibleScopes"]) == {"ACADEMIC_GRADE", "CAMPUS_ALERT"}


def test_guardian_otp_is_fail_closed_for_bound_phone(client, db_mode):
    _bind(client, "GRD-002", "李同学", "13800138778")
    response = client.post(f"{PORTAL}/guardian/otp", json={"phone": "13800138778"})
    _assert_login_disabled(response)


def test_guardian_otp_is_fail_closed_for_unbound_phone(client, db_mode):
    # 已绑定与未绑定号码必须得到相同的 fail-closed 结果，避免通过兼容端点枚举授权关系。
    response = client.post(f"{PORTAL}/guardian/otp", json={"phone": "13999999999"})
    _assert_login_disabled(response)


def test_guardian_login_is_fail_closed_even_with_legacy_code(client, db_mode):
    _bind(client, "GRD-003", "赵同学", "13800138779")
    response = client.post(
        f"{PORTAL}/guardian/login",
        json={"phone": "13800138779", "code": "123456"},
    )
    _assert_login_disabled(response)


def test_guardian_token_blocked_from_staff(client, db_mode):
    # 不依赖已经关闭的登录链路，直接构造合法签名的 GUARDIAN 身份验证老师端权限边界。
    response = client.get(
        "/api/v1/students",
        headers=_guardian_token("13800138780"),
    )
    assert response.status_code == 403
    assert response.json()["code"] == 403001
