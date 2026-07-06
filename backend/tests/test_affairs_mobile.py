"""13A-P7 多端收口 · 端到端（学生自视图 + 学生自选床位 + 教师待办卡）。

MB1 学生只见本人请假；MB2 学生隔离；MB3 处分仅数量；MB4 自选开关关→提示+403、
开→可选床入住+我的宿舍；MB5 教师学工待办卡聚合；非学生调自视图403。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"
MB = "/api/v1/mobile"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    zhang = StudentProfile(tenant_id=TID, student_no="MB13A01", real_name="张三", class_id=a.id, gender="M",
                           current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    li = StudentProfile(tenant_id=TID, student_no="MB13A02", real_name="李四", class_id=a.id, gender="M",
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(zhang); db.add(li); db.flush()
    ids = {"A": a.id, "zhang": zhang.id, "li": li.id}
    db.commit()
    db.close()
    return ids


def _make_leave(client, hdr, sid, approve=False):
    lid = client.post(f"{BASE}/leave", headers=hdr, json={
        "studentId": str(sid), "leaveType": "PERSONAL", "startTime": "2026-03-01",
        "endTime": "2026-03-02", "reason": "回家有事"}).json()["data"]["id"]
    if approve:
        client.post(f"{BASE}/leave/{lid}/approve", headers=hdr)
    return lid


def test_mb1_leave_my_sees_own(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _make_leave(client, admin, ids["zhang"])
    r = client.get(f"{MB}/affairs/leave/my", headers=_stu_token("张三", "MB13A01")).json()
    assert r["code"] == 0 and len(r["data"]["items"]) == 1


def test_mb2_student_isolation(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _make_leave(client, admin, ids["zhang"])
    # 李四看不到张三的请假
    r = client.get(f"{MB}/affairs/leave/my", headers=_stu_token("李四", "MB13A02")).json()
    assert len(r["data"]["items"]) == 0


def test_mb3_discipline_count_only(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    cid = client.post(f"{BASE}/discipline/cases", headers=admin, json={
        "studentId": str(ids["zhang"]), "discType": "WARNING", "reason": "违纪事实说明足够长"}).json()["data"]["caseId"]
    client.post(f"{BASE}/discipline/cases/{cid}/submit", headers=admin)
    client.post(f"{BASE}/discipline/cases/{cid}/review", headers=admin, json={"action": "APPROVE"})
    client.post(f"{BASE}/discipline/cases/{cid}/review", headers=admin, json={"action": "APPROVE"})
    d = client.get(f"{MB}/affairs/discipline/my", headers=_stu_token("张三", "MB13A01")).json()["data"]
    assert d["activeCount"] == 1 and "detailNote" in d  # 仅数量+提示，无明细


def test_mb4_dorm_self_select_toggle_flow(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # 建男寝 + 铺床
    bid = client.post(f"{BASE}/dorm/buildings", headers=admin, json={
        "buildingName": "紫荆1号楼", "genderLimit": "MALE",
        "floors": 1, "roomsPerFloor": 2, "bedsPerRoom": 4}).json()["data"]["buildingId"]
    stu = _stu_token("张三", "MB13A01")
    # 默认关：选项含提醒、无楼；我的宿舍显示未放开
    opt = client.get(f"{MB}/affairs/dorm/select-options", headers=stu).json()["data"]
    assert opt["selfSelectEnabled"] is False and opt["buildings"] == [] and "辅导员" in opt["studentNotice"]
    rooms = client.get(f"{BASE}/dorm/buildings/{bid}/rooms?floor=1", headers=admin).json()["data"]["items"]
    beds = client.get(f"{BASE}/dorm/rooms/{rooms[0]['roomId']}/beds", headers=admin).json()["data"]["items"]
    assert client.post(f"{MB}/affairs/dorm/beds/{beds[0]['bedId']}/self-select", headers=stu).status_code == 403
    # 关闭时学生也不能浏览房/床 → 403
    assert client.get(f"{MB}/affairs/dorm/buildings/{bid}/rooms", headers=stu).status_code == 403
    # 学校放开
    client.put(f"{BASE}/dorm/config/self-select", headers=admin, json={"enabled": True})
    opt2 = client.get(f"{MB}/affairs/dorm/select-options", headers=stu).json()["data"]
    assert opt2["selfSelectEnabled"] is True and len(opt2["buildings"]) == 1
    # 放开后学生走 mobile 级联浏览房→床
    mrooms = client.get(f"{MB}/affairs/dorm/buildings/{bid}/rooms", headers=stu).json()["data"]["items"]
    assert len(mrooms) == 2  # 1层2间
    mbeds = client.get(f"{MB}/affairs/dorm/rooms/{mrooms[0]['roomId']}/beds", headers=stu).json()["data"]["items"]
    # 学生自选入住本人
    r = client.post(f"{MB}/affairs/dorm/beds/{mbeds[0]['bedId']}/self-select", headers=stu).json()
    assert r["data"]["status"] == "OCCUPIED"
    mine = client.get(f"{MB}/affairs/dorm/my", headers=stu).json()["data"]
    assert mine["hasBed"] is True and mine["myBed"]["building"] == "紫荆1号楼"


def test_mb5_teacher_affairs_cards(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _make_leave(client, admin, ids["zhang"])  # 产生 LEAVE_APPROVAL 待办
    r = client.get(f"{MB}/teacher/affairs", headers=_hdr(client, "counselor01")).json()
    assert r["code"] == 0 and r["data"]["total"] >= 1
    assert any(c["todoType"] == "LEAVE_APPROVAL" for c in r["data"]["cards"])


def test_mb6_non_student_403(client, db_mode):
    _seed(db_mode)
    # 教师调学生自视图 → 403
    r = client.get(f"{MB}/affairs/leave/my", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403
