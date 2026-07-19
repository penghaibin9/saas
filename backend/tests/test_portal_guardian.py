"""学生 PC 门户 · 家长（proxy）侧测试（MySQL 真库 via db_mode）：

覆盖：验证码登录闭环（otp→login→只读查看被授权学生+范围）/ 错误验证码 / 未授权手机号静默 /
GUARDIAN 令牌被挡在老师端之外（require_staff 403）。SMS 未开启故 otp 回带 devCode。
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


def _login(client, phone):
    otp = client.post(f"{PORTAL}/guardian/otp", json={"phone": phone}).json()
    assert otp["code"] == 0
    code = otp["data"].get("devCode")
    assert code, "SMS 未开启时应回带 devCode 供测试"
    lg = client.post(f"{PORTAL}/guardian/login", json={"phone": phone, "code": code}).json()
    return lg


def test_guardian_login_and_view(client, db_mode):
    _bind(client, "GRD-001", "王同学", "13800138777")
    lg = _login(client, "13800138777")
    assert lg["code"] == 0 and lg["data"]["studentCount"] == 1
    h = {"Authorization": f"Bearer {lg['data']['accessToken']}"}
    st = client.get(f"{PORTAL}/guardian/students", headers=h).json()
    assert st["code"] == 0 and st["data"]["hasData"] is True
    item = st["data"]["items"][0]
    assert item["studentName"] == "王同学" and item["studentNo"] == "GRD-001"
    assert set(item["visibleScopes"]) == {"ACADEMIC_GRADE", "CAMPUS_ALERT"}


def test_guardian_wrong_code(client, db_mode):
    _bind(client, "GRD-002", "李同学", "13800138778")
    client.post(f"{PORTAL}/guardian/otp", json={"phone": "13800138778"}).json()
    bad = client.post(f"{PORTAL}/guardian/login",
                      json={"phone": "13800138778", "code": "000000"}).json()
    assert bad["code"] != 0


def test_guardian_unauthorized_phone_silent(client, db_mode):
    # 未被任何学生授权的手机号：otp 静默成功但不回带 devCode，login 无有效码失败
    otp = client.post(f"{PORTAL}/guardian/otp", json={"phone": "13999999999"}).json()
    assert otp["code"] == 0 and "devCode" not in otp["data"]
    lg = client.post(f"{PORTAL}/guardian/login",
                     json={"phone": "13999999999", "code": "123456"}).json()
    assert lg["code"] != 0


def test_guardian_token_blocked_from_staff(client, db_mode):
    _bind(client, "GRD-003", "赵同学", "13800138779")
    lg = _login(client, "13800138779")
    h = {"Authorization": f"Bearer {lg['data']['accessToken']}"}
    # GUARDIAN 令牌访问老师端主档接口 → require_staff 403
    assert client.get("/api/v1/students", headers=h).json()["code"] == 403001
