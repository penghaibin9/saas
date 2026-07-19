"""学生 PC 门户 · 就业服务（第5期）测试（MySQL 真库 via db_mode）：

我的就业查看 / 去向登记(校验+提交) / 打印回执 / 非学生拒绝。
"""
from __future__ import annotations

PORTAL = "/api/v1/portal/employment"
TID = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC"})}


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(no, name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    db.add(StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="F", grade="2021",
                          current_stage="EMPLOYMENT", student_status="NORMAL", status="ACTIVE"))
    db.commit()
    db.close()


def test_my_view(client, db_mode):
    _seed("EM-001", "就业一")
    h = _stu_token("就业一", "EM-001")
    assert client.get(f"{PORTAL}/my", headers=h).json()["code"] == 0


def test_destination_register(client, db_mode):
    _seed("EM-002", "就业二")
    h = _stu_token("就业二", "EM-002")
    # 缺去向类型 → 校验失败
    assert client.post(f"{PORTAL}/destination", headers=h, json={}).json()["code"] != 0
    ok = client.post(f"{PORTAL}/destination", headers=h,
                     json={"destinationType": "签约就业", "unitName": "某科技公司",
                           "remark": "已签订三方协议"}).json()
    assert ok["code"] == 0


def test_print(client, db_mode):
    _seed("EM-003", "就业三")
    h = _stu_token("就业三", "EM-003")
    r = client.post(f"{PORTAL}/destination/print", headers=h, json={"bizId": "E1"}).json()
    assert r["code"] == 0 and r["data"]["watermark"] == "就业三"


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.get(f"{PORTAL}/my", headers=admin).json()["code"] == 403001
    assert client.post(f"{PORTAL}/destination", headers=admin,
                       json={"destinationType": "签约就业"}).json()["code"] == 403001
    assert client.post(f"{PORTAL}/destination/print", headers=admin, json={}).json()["code"] == 403001
