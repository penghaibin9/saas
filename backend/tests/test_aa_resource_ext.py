"""教学资源续卡（13B-R4续卡）· 实训室资源/设备资源/实训室预约/资源占用/资源冲突/资源维修/资源统计
端到端（真实 DB 模式）。复用教室字典(t_aa_classroom)已验证的字段/状态机/冲突检测框架。

L1 实训室建/列/详情；L2 实训室重复409；L3 实训室改/状态/删；L4 实训室越权403；
E1 设备建/列/位置解析；E2 设备重复+校验；
B1 实训室预约申请→审核→冲突409；
R1 维修报修→联动MAINTENANCE→开始→完成→联动恢复AVAILABLE；R2 维修取消+越权；
O1 资源占用（预约+课表跨源聚合）；C1 资源冲突（预约vs已发布课表跨源冲突）；
S1 资源统计聚合口径。
"""
from __future__ import annotations

from datetime import date, timedelta

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _mk_lab(client, hdr, lab_code="L101", **kw):
    body = {"labCode": lab_code, "labName": kw.get("labName", "机械实训室"),
            "capacity": kw.get("capacity", 30), "labType": kw.get("labType", "MECHANICAL")}
    body.update({k: v for k, v in kw.items() if k in ("buildingName", "responsibleName", "responsibleKey", "remark")})
    return client.post(f"{BASE}/labs", headers=hdr, json=body)


def _mk_equipment(client, hdr, code="EQ001", **kw):
    body = {"equipmentCode": code, "equipmentName": kw.get("equipmentName", "数控车床"),
            "quantity": kw.get("quantity", 1), "ownerKind": kw.get("ownerKind", "NONE")}
    body.update({k: v for k, v in kw.items() if k in ("specModel", "ownerId", "responsibleName",
                                                       "purchaseDate", "status", "remark")})
    return client.post(f"{BASE}/equipment", headers=hdr, json=body)


def _mk_classroom(client, hdr, building_code="Z", room_code="101", **kw):
    body = {"buildingCode": building_code, "buildingName": kw.get("buildingName", building_code),
            "roomCode": room_code, "capacity": kw.get("capacity", 60),
            "roomType": kw.get("roomType", "MULTIMEDIA")}
    return client.post(f"{BASE}/classrooms", headers=hdr, json=body)


# ═══════════ 实训室资源 ═══════════

def test_l1_create_list_detail(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    r = _mk_lab(client, hdr, "L101").json()["data"]
    assert r["status"] == "AVAILABLE" and r["capacity"] == 30 and r["labTypeLabel"] == "机械实训室"
    lid = r["labId"]
    lst = client.get(f"{BASE}/labs", headers=hdr, params={"keyword": "机械"}).json()["data"]
    assert lst["total"] >= 1 and any(x["labId"] == lid for x in lst["items"])
    det = client.get(f"{BASE}/labs/{lid}", headers=hdr).json()["data"]
    assert det["labCode"] == "L101"


def test_l2_duplicate_409(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    _mk_lab(client, hdr, "L201")
    assert _mk_lab(client, hdr, "L201").status_code == 409


def test_l3_update_status_delete(client, db_mode):
    # 2026-07-19 权限清单化：ACADEMIC_TEACHER 不再持通配符，实训室增改是管理动作，改用校管理员
    hdr = _hdr(client, "school_admin01")
    lid = _mk_lab(client, hdr, "L301", responsibleName="张管理员").json()["data"]["labId"]
    r = client.put(f"{BASE}/labs/{lid}", headers=hdr, json={"capacity": 40, "responsibleName": "李管理员"}).json()["data"]
    assert r["capacity"] == 40 and r["responsibleName"] == "李管理员"
    r2 = client.post(f"{BASE}/labs/{lid}/status", headers=hdr, json={"status": "MAINTENANCE"}).json()["data"]
    assert r2["status"] == "MAINTENANCE"
    opts = client.get(f"{BASE}/labs/options", headers=hdr).json()["data"]["items"]
    assert all(o["labId"] != lid for o in opts)
    client.post(f"{BASE}/labs/{lid}/status", headers=hdr, json={"status": "AVAILABLE"})
    opts2 = client.get(f"{BASE}/labs/options", headers=hdr).json()["data"]["items"]
    assert any(o["labId"] == lid for o in opts2)
    assert client.delete(f"{BASE}/labs/{lid}", headers=hdr).status_code == 200
    assert client.get(f"{BASE}/labs/{lid}", headers=hdr).status_code == 404


def test_l4_authz_denied(client, db_mode):
    admin = _hdr(client, "school_admin01")
    lid = _mk_lab(client, admin, "L401").json()["data"]["labId"]
    stu = _hdr(client, "student01")
    assert client.get(f"{BASE}/labs", headers=stu).status_code == 403
    assert _mk_lab(client, stu, "L402").status_code == 403
    cnt = _hdr(client, "counselor01")
    assert client.post(f"{BASE}/labs/{lid}/status", headers=cnt, json={"status": "DISABLED"}).status_code == 403
    assert client.delete(f"{BASE}/labs/{lid}", headers=cnt).status_code == 403


# ═══════════ 设备资源 ═══════════

def test_e1_create_list_owner_resolve(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _mk_classroom(client, hdr, "E", "901").json()["data"]["classroomId"]
    r = _mk_equipment(client, hdr, "EQ101", ownerKind="CLASSROOM", ownerId=str(cid),
                      specModel="CK6140").json()["data"]
    assert r["status"] == "IN_USE" and r["ownerLabel"] == "E901" and r["specModel"] == "CK6140"
    lst = client.get(f"{BASE}/equipment", headers=hdr, params={"ownerKind": "CLASSROOM"}).json()["data"]
    assert any(x["equipmentCode"] == "EQ101" for x in lst["items"])


def test_e2_duplicate_and_validation(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    _mk_equipment(client, hdr, "EQ201")
    assert _mk_equipment(client, hdr, "EQ201").status_code == 409
    assert _mk_equipment(client, hdr, "EQ202", quantity=0).status_code == 400
    assert client.post(f"{BASE}/equipment", headers=hdr,
                       json={"equipmentCode": "EQ203", "equipmentName": "x", "ownerKind": "BOGUS"}).status_code == 400
    eid = _mk_equipment(client, hdr, "EQ204").json()["data"]["equipmentId"]
    assert client.post(f"{BASE}/equipment/{eid}/status", headers=hdr, json={"status": "BROKEN"}).status_code == 400
    r = client.post(f"{BASE}/equipment/{eid}/status", headers=hdr, json={"status": "IDLE"}).json()["data"]
    assert r["status"] == "IDLE" and r["statusLabel"] == "闲置"


# ═══════════ 实训室预约 ═══════════

def test_b1_lab_booking_review_conflict(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    lid = _mk_lab(client, hdr, "L801").json()["data"]["labId"]
    b1 = client.post(f"{BASE}/labs/bookings", headers=hdr,
                     json={"labId": str(lid), "bookingDate": "2027-06-20", "slotNo": 1,
                          "purpose": "技能竞赛集训"}).json()
    assert b1["code"] == 0 and b1["data"]["status"] == "PENDING"
    bid1 = b1["data"]["bookingId"]
    assert client.post(f"{BASE}/labs/bookings/{bid1}/review", headers=hdr,
                       json={"action": "APPROVE"}).json()["data"]["status"] == "APPROVED"
    assert client.post(f"{BASE}/labs/bookings", headers=hdr,
                       json={"labId": str(lid), "bookingDate": "2027-06-20", "slotNo": 1}).status_code == 409
    b3 = client.post(f"{BASE}/labs/bookings", headers=hdr,
                     json={"labId": str(lid), "bookingDate": "2027-06-20", "slotNo": 2}).json()
    assert b3["code"] == 0
    assert client.post(f"{BASE}/labs/bookings/{b3['data']['bookingId']}/review", headers=hdr,
                       json={"action": "REJECT", "reason": "x"}).status_code == 400
    lid2 = _mk_lab(client, hdr, "L802").json()["data"]["labId"]
    client.post(f"{BASE}/labs/{lid2}/status", headers=hdr, json={"status": "MAINTENANCE"})
    assert client.post(f"{BASE}/labs/bookings", headers=hdr,
                       json={"labId": str(lid2), "bookingDate": "2027-06-21", "slotNo": 1}).status_code == 409


# ═══════════ 资源维修 ═══════════

def test_r1_repair_lifecycle_links_status(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    lid = _mk_lab(client, hdr, "L901").json()["data"]["labId"]
    assert client.get(f"{BASE}/labs/{lid}", headers=hdr).json()["data"]["status"] == "AVAILABLE"
    rr = client.post(f"{BASE}/resources/repairs", headers=hdr,
                     json={"resourceKind": "LAB", "resourceId": str(lid), "faultDesc": "空压机异响"}).json()
    assert rr["code"] == 0 and rr["data"]["status"] == "REPORTED"
    rid = rr["data"]["repairId"]
    assert client.get(f"{BASE}/labs/{lid}", headers=hdr).json()["data"]["status"] == "MAINTENANCE"
    assert client.post(f"{BASE}/resources/repairs/{rid}/start", headers=hdr).json()["data"]["status"] == "IN_REPAIR"
    done = client.post(f"{BASE}/resources/repairs/{rid}/complete", headers=hdr,
                       json={"repairNote": "更换空压机皮带"}).json()
    assert done["data"]["status"] == "DONE" and done["data"]["resolvedAt"]
    assert client.get(f"{BASE}/labs/{lid}", headers=hdr).json()["data"]["status"] == "AVAILABLE"
    lst = client.get(f"{BASE}/resources/repairs", headers=hdr, params={"resourceKind": "LAB"}).json()["data"]
    assert any(x["repairId"] == rid for x in lst["items"])


def test_r2_repair_cancel_and_authz(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    lid = _mk_lab(client, hdr, "L902").json()["data"]["labId"]
    rid = client.post(f"{BASE}/resources/repairs", headers=hdr,
                      json={"resourceKind": "LAB", "resourceId": str(lid), "faultDesc": "灯管损坏"}
                      ).json()["data"]["repairId"]
    assert client.post(f"{BASE}/resources/repairs/{rid}/cancel", headers=hdr,
                       json={"reason": "误报"}).json()["data"]["status"] == "CANCELLED"
    assert client.post(f"{BASE}/resources/repairs/{rid}/start", headers=hdr).status_code == 409
    cnt = _hdr(client, "counselor01")
    rid2 = client.post(f"{BASE}/resources/repairs", headers=hdr,
                       json={"resourceKind": "LAB", "resourceId": str(lid), "faultDesc": "再次报修"}
                       ).json()["data"]["repairId"]
    assert client.post(f"{BASE}/resources/repairs/{rid2}/start", headers=cnt).status_code == 403


# ═══════════ 资源占用 / 资源冲突（预约 vs 已发布课表跨源聚合） ═══════════

def _seed_ready_schedule_task(term_id, slot_no):
    """按当前正式排课合同种 READY 教学任务和启用节次，禁止 free-text 绕过任务身份。"""
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTimeSlot

    db = get_sessionmaker()()
    slot = db.query(AaTimeSlot).filter(
        AaTimeSlot.tenant_id == TID,
        AaTimeSlot.slot_no == int(slot_no),
        AaTimeSlot.is_deleted.is_(False),
    ).first()
    if slot:
        slot.enabled = True
        slot.status = "ENABLED"
    else:
        db.add(AaTimeSlot(tenant_id=TID, slot_no=int(slot_no), slot_name=f"第{slot_no}节",
                          enabled=True, status="ENABLED"))
    course = AaCourse(tenant_id=TID, course_code=f"RES{term_id}{slot_no}",
                      course_name="资源冲突测试课", credit=2, status="ENABLED")
    db.add(course); db.flush()
    task_batch = AaTeachingTaskBatch(tenant_id=TID, term_id=int(term_id),
                                     batch_name=f"资源冲突任务批次{slot_no}", status="APPROVED")
    db.add(task_batch); db.flush()
    task = AaTeachingTask(tenant_id=TID, batch_id=task_batch.id,
                          course_id=course.id, course_code=course.course_code,
                          course_name=course.course_name, teacher_key="T-RES",
                          teacher_name="冲突检测老师", weekly_hours=1,
                          start_week=1, end_week=18, status="READY")
    db.add(task); db.flush()
    task_id = int(task.id)
    db.commit(); db.close()
    return task_id


def _setup_term_and_schedule(client, hdr, classroom_text, weekday, slot_no, target_date_iso):
    """建正式当前学期 + READY 教学任务 + 已发布课表项，供占用/冲突查询命中。"""
    start = date(2026, 9, 1)
    t = client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": "2099-2100", "termNo": 1, "termName": "资源冲突测试学期",
        "startDate": start.isoformat(), "endDate": (start + timedelta(days=200)).isoformat(),
        "teachingWeeks": 18}).json()["data"]["termId"]
    client.post(f"{BASE}/terms/{t}/publish", headers=hdr)
    task_id = _seed_ready_schedule_task(int(t), slot_no)
    bid = client.post(f"{BASE}/schedule-batches", headers=hdr, json={"termId": str(t)}).json()["data"]["batchId"]
    item = client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json={
        "taskId": str(task_id), "weekday": weekday, "slotNo": slot_no,
        "startWeek": 1, "endWeek": 18, "weekParity": "ALL", "classroom": classroom_text})
    assert item.status_code == 200, item.text
    pre = client.post(f"{BASE}/schedule-batches/{bid}/pre-publish", headers=hdr)
    assert pre.status_code == 200, pre.text
    pub = client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=hdr)
    assert pub.status_code == 200, pub.text
    return t, bid


def test_o1_resource_occupancy_aggregates_booking_and_schedule(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    start = date(2026, 9, 1)
    target = start + timedelta(days=14)
    weekday = target.isoweekday()
    cid = _mk_classroom(client, hdr, "O", "501").json()["data"]["classroomId"]
    _setup_term_and_schedule(client, hdr, "O501", weekday, 5, target.isoformat())
    b = client.post(f"{BASE}/classrooms/bookings", headers=hdr,
                    json={"classroomId": str(cid), "bookingDate": target.isoformat(), "slotNo": 6,
                         "purpose": "资源占用测试预约"}).json()
    client.post(f"{BASE}/classrooms/bookings/{b['data']['bookingId']}/review", headers=hdr, json={"action": "APPROVE"})
    occ = client.get(f"{BASE}/resources/occupancy", headers=hdr, params={"date": target.isoformat()}).json()
    assert occ["code"] == 0
    sources = {it["source"] for it in occ["data"]["items"]}
    assert "BOOKING" in sources and "SCHEDULE" in sources
    assert any(it["resourceLabel"] == "O501" and it["slotNo"] == 5 and it["source"] == "SCHEDULE"
              for it in occ["data"]["items"])
    assert any(it["resourceLabel"] == "O501" and it["slotNo"] == 6 and it["source"] == "BOOKING"
              for it in occ["data"]["items"])


def test_c1_resource_conflict_booking_overlaps_schedule(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    start = date(2026, 9, 1)
    target = start + timedelta(days=21)
    weekday = target.isoweekday()
    cid = _mk_classroom(client, hdr, "C", "601").json()["data"]["classroomId"]
    _setup_term_and_schedule(client, hdr, "C601", weekday, 7, target.isoformat())
    b = client.post(f"{BASE}/classrooms/bookings", headers=hdr,
                    json={"classroomId": str(cid), "bookingDate": target.isoformat(), "slotNo": 7,
                         "purpose": "资源冲突测试预约"}).json()
    client.post(f"{BASE}/classrooms/bookings/{b['data']['bookingId']}/review", headers=hdr, json={"action": "APPROVE"})
    conf = client.get(f"{BASE}/resources/conflicts", headers=hdr,
                      params={"dateFrom": target.isoformat()}).json()
    assert conf["code"] == 0 and conf["data"]["total"] >= 1
    hit = [c for c in conf["data"]["items"] if c["resourceLabel"] == "C601" and c["slotNo"] == 7]
    assert hit and hit[0]["scheduleCourseName"] == "资源冲突测试课"
    assert client.get(f"{BASE}/resources/conflicts", headers=hdr,
                      params={"dateFrom": target.isoformat(),
                              "dateTo": (target + timedelta(days=40)).isoformat()}).status_code == 400


# ═══════════ 资源统计 ═══════════

def test_s1_resource_stats_reflects_fixtures(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    _mk_lab(client, hdr, "S101")
    lid2 = _mk_lab(client, hdr, "S102").json()["data"]["labId"]
    client.post(f"{BASE}/labs/{lid2}/status", headers=hdr, json={"status": "DISABLED"})
    _mk_equipment(client, hdr, "SEQ01")
    r = client.get(f"{BASE}/resources/stats", headers=hdr).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["lab"]["total"] >= 2
    assert d["lab"]["byStatus"].get("AVAILABLE", 0) >= 1
    assert d["lab"]["byStatus"].get("DISABLED", 0) >= 1
    assert d["equipment"]["total"] >= 1
    assert "classroom" in d and "classroomBooking" in d and "labBooking" in d and "repair" in d


def test_s2_stats_authz_denied(client, db_mode):
    stu = _hdr(client, "student01")
    assert client.get(f"{BASE}/resources/stats", headers=stu).status_code == 403
