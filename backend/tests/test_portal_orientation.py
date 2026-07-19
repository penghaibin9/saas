"""学生 PC 门户 · 迎新报到 + 办事大厅（第5期收口）测试（MySQL 真库 via db_mode）。"""
from __future__ import annotations

PORTAL = "/api/v1/portal"
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
    db.add(StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="M", grade="2026",
                          current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE"))
    db.commit()
    db.close()


def test_orientation_my_and_print(client, db_mode):
    _seed("OR-001", "迎新一")
    h = _stu_token("迎新一", "OR-001")
    assert client.get(f"{PORTAL}/orientation/my", headers=h).json()["code"] == 0  # 无记录空态code 0
    p = client.post(f"{PORTAL}/orientation/print", headers=h, json={"bizId": "O1"}).json()
    assert p["code"] == 0 and p["data"]["watermark"] == "迎新一"


def test_orientation_submit_without_record(client, db_mode):
    _seed("OR-002", "迎新二")  # 无迎新台账
    h = _stu_token("迎新二", "OR-002")
    # 无报到记录 → 提交被拒(NOT_FOUND)
    assert client.post(f"{PORTAL}/orientation/collect", headers=h,
                       json={"phone": "13800138000", "origin": "湖南长沙"}).json()["code"] != 0
    assert client.post(f"{PORTAL}/orientation/green-channel", headers=h,
                       json={"applyType": "缓交学费", "applyAmount": 5000}).json()["code"] != 0


def test_service_hall_catalog(client, db_mode):
    _seed("OR-003", "迎新三")
    h = _stu_token("迎新三", "OR-003")
    r = client.get(f"{PORTAL}/service-hall/catalog", headers=h).json()
    assert r["code"] == 0
    d = r["data"]
    assert isinstance(d["items"], list) and d["total"] == len(d["items"])
    if d["items"]:
        e = d["items"][0]
        assert e["key"] and e["label"] and e["path"]


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.get(f"{PORTAL}/orientation/my", headers=admin).json()["code"] == 403001
    assert client.post(f"{PORTAL}/orientation/print", headers=admin, json={}).json()["code"] == 403001
    assert client.get(f"{PORTAL}/service-hall/catalog", headers=admin).json()["code"] == 403001
