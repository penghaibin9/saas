"""学生 PC 门户 · 学工事务（第4期）测试（MySQL 真库 via db_mode）：

学工自视图(总览/请假/奖助/资助/违纪) / 通用事务申请(校验) / 打印回执 / 非学生拒绝。
"""
from __future__ import annotations

PORTAL = "/api/v1/portal/affairs"
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
    db.add(StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="M", grade="2023",
                          current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE"))
    db.commit()
    db.close()


def test_affairs_views(client, db_mode):
    _seed("SA-001", "学工一")
    h = _stu_token("学工一", "SA-001")
    for path in ("/overview", "/leave", "/funding", "/aid", "/discipline"):
        assert client.get(f"{PORTAL}{path}", headers=h).json()["code"] == 0


def test_service_apply(client, db_mode):
    _seed("SA-002", "学工二")
    h = _stu_token("学工二", "SA-002")
    ok = client.post(f"{PORTAL}/service-apply", headers=h,
                     json={"serviceKey": "CONSULT", "reason": "咨询关于奖学金评定的相关问题"}).json()
    assert ok["code"] == 0
    # 事由过短拒绝
    assert client.post(f"{PORTAL}/service-apply", headers=h,
                       json={"serviceKey": "CONSULT", "reason": "短"}).json()["code"] != 0


def test_print(client, db_mode):
    _seed("SA-003", "学工三")
    h = _stu_token("学工三", "SA-003")
    r = client.post(f"{PORTAL}/print", headers=h,
                    json={"bizType": "LEAVE", "docName": "请假条"}).json()
    assert r["code"] == 0 and r["data"]["watermark"] == "学工三"


def test_psy_and_applications(client, db_mode):
    _seed("SA-010", "学工十")
    h = _stu_token("学工十", "SA-010")
    assert client.get(f"{PORTAL}/psy/questions", headers=h).json()["code"] == 0
    assert client.get(f"{PORTAL}/psy/history", headers=h).json()["code"] == 0
    assert client.get(f"{PORTAL}/applications", headers=h).json()["code"] == 0
    # 心理测评未作答拒绝
    assert client.post(f"{PORTAL}/psy/submit", headers=h, json={"answers": []}).json()["code"] != 0


def test_discipline_appeal(client, db_mode):
    _seed("SA-011", "学工十一")
    h = _stu_token("学工十一", "SA-011")
    ok = client.post(f"{PORTAL}/discipline/appeal", headers=h,
                     json={"reason": "对处分认定的事实有异议，特此书面申辩说明。"}).json()
    assert ok["code"] == 0
    assert client.post(f"{PORTAL}/discipline/appeal", headers=h, json={"reason": "短"}).json()["code"] != 0


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.get(f"{PORTAL}/leave", headers=admin).json()["code"] == 403001
    assert client.get(f"{PORTAL}/funding", headers=admin).json()["code"] == 403001
    assert client.post(f"{PORTAL}/service-apply", headers=admin,
                       json={"serviceKey": "CONSULT", "reason": "咨询相关问题事项"}).json()["code"] == 403001
    assert client.post(f"{PORTAL}/print", headers=admin, json={}).json()["code"] == 403001
    assert client.get(f"{PORTAL}/psy/questions", headers=admin).json()["code"] == 403001
    assert client.get(f"{PORTAL}/applications", headers=admin).json()["code"] == 403001
