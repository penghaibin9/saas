"""自动排考引擎（/academic-affairs/exam/batches/{bid}/auto-arrange）端点测试。

覆盖重点：
- 自动切考场（最少考场数 + 末考场就小不就大 + 考试座位数优先于上课容量）
- 座位模式（隔座奇数座位号、容量减半）
- 监考自动分配（主/副角色、任课回避、不足如实报缺口）
- 同教室同时段不复用（跨课程占用冲突）
- 增量跳过已有考场的课程；清除只删 AUTO 考场，人工考场保留
- 漏排归因（NO_TIME / ROOM_SHORT）
- dryRun 不落库；非 COURSE_CONFIRMED 批次 409；学生越权 403

MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode, *, students=4, rooms=(), extra_class=False):
    """学期+学院+班级+课程+教学任务+学生+教室字典。rooms: [(code,cap,examSeats,exclusive)]。"""
    from app.db.session import get_sessionmaker
    from app.models import (AaClassroom, AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm,
                            College, Major, SchoolClass, StudentProfile)
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2024-2025", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
    co1 = AaCourse(tenant_id=TID, course_code="AX_MATH", course_name="高等数学", credit=4, status="ENABLED")
    co2 = AaCourse(tenant_id=TID, course_code="AX_ENG", course_name="大学英语", credit=3, status="ENABLED")
    db.add_all([co1, co2]); db.flush()
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name="2024秋教学任务",
                             college_id=col.id, status="ACTIVE")
    db.add(tb); db.flush()
    tt1 = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=co1.id, course_name="高等数学",
                         class_id=klass.id, teaching_class_name="软件2401",
                         teacher_key="teacher_a", teacher_name="甲老师")
    tt2 = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=co2.id, course_name="大学英语",
                         class_id=klass.id, teaching_class_name="软件2401",
                         teacher_key="teacher_b", teacher_name="乙老师")
    # 第三位教师只为扩充监考池：任课回避排除本课教师后，仍需 ≥2 人可派
    tt0 = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=co1.id, course_name="高等数学B",
                         class_id=klass.id, teaching_class_name="软件2401-B",
                         teacher_key="teacher_c", teacher_name="丙老师")
    db.add_all([tt1, tt2, tt0]); db.flush()
    ids = {"tt1": tt1.id, "tt2": tt2.id, "class": klass.id, "college": col.id, "rooms": {}}
    if extra_class:
        k2 = SchoolClass(tenant_id=TID, major_id=major.id, class_name="空班2402", grade="2024", status="ACTIVE")
        db.add(k2); db.flush()
        tt3 = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=co2.id, course_name="大学英语",
                             class_id=k2.id, teaching_class_name="空班2402",
                             teacher_key="teacher_b", teacher_name="乙老师")
        db.add(tt3); db.flush()
        ids["tt3"] = tt3.id
    for i in range(students):
        db.add(StudentProfile(tenant_id=TID, student_no=f"AX24{i + 1:02d}", real_name=f"考生{i + 1}",
                              college_id=col.id, major_id=major.id, class_id=klass.id,
                              grade="2024", student_status="NORMAL", status="ACTIVE"))
    for (code, cap, exam_seats, exclusive) in rooms:
        r = AaClassroom(tenant_id=TID, building_code="K", building_name="考试楼", room_code=code,
                        capacity=cap, exam_seats=exam_seats, is_exclusive=exclusive,
                        room_type="LECTURE", status="AVAILABLE")
        db.add(r); db.flush()
        ids["rooms"][code] = r.id
    db.commit(); db.close()
    return ids


def _confirmed_batch(client, admin, tt_id, *, with_time=True, name="2024秋期末"):
    bid = client.post(f"{BASE}/exam/batches", headers=admin, json={"batchName": name}).json()["data"]["batchId"]
    cid = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=admin,
                      json={"teachingTaskId": str(tt_id)}).json()["data"]["examCourseId"]
    client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=admin, json={"action": "CONFIRM"})
    if with_time:
        client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
                   json={"examDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00",
                         "durationMinutes": 120})
    client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin)
    return bid, cid


def _rooms_of(client, admin, cid):
    return client.get(f"{BASE}/exam/courses/{cid}/rooms", headers=admin).json()["data"]["items"]


def _seats_of(client, admin, room_id):
    return client.get(f"{BASE}/exam/rooms/{room_id}/seats", headers=admin).json()["data"]["items"]


# ── 基本编排：切考场 + 铺位 + 监考 ──

def test_auto_arrange_basic(client, db_mode):
    """4 名考生 + 1 间 30 座教室 → 1 个考场、4 个座位、2 名监考（主+副）、任课回避。"""
    ids = _seed(db_mode, students=4, rooms=[("101", 30, None, False)])
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_batch(client, admin, ids["tt1"])
    r = client.post(f"{BASE}/exam/batches/{bid}/auto-arrange", headers=admin)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["arrangedCourses"] == 1 and d["missedCourses"] == 0
    rooms = _rooms_of(client, admin, cid)
    assert len(rooms) == 1 and rooms[0]["plannedCount"] == 4
    seats = _seats_of(client, admin, rooms[0]["examRoomId"])
    assert [s["seatNo"] for s in seats] == [1, 2, 3, 4]
    assert len({s["admissionNo"] for s in seats}) == 4, "准考证号不得重号"
    invs = client.get(f"{BASE}/exam/rooms/{rooms[0]['examRoomId']}/invigilators",
                      headers=admin).json()["data"]["items"]
    assert len(invs) == 2
    assert {i["role"] for i in invs} == {"CHIEF", "ASSISTANT"}
    # 任课回避：tt1 的任课教师 teacher_a 不得监考本课程考场
    assert all(i["teacherKey"] != "teacher_a" for i in invs), "任课教师未回避本课程考场"


def test_split_prefers_fewest_then_smallest(client, db_mode):
    """4 人 + 教室 100 座与 6 座 → 1 个考场且选 6 座（末考场就小不就大）。"""
    ids = _seed(db_mode, students=4, rooms=[("big", 100, None, False), ("small", 6, None, False)])
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_batch(client, admin, ids["tt1"])
    client.post(f"{BASE}/exam/batches/{bid}/auto-arrange", headers=admin)
    rooms = _rooms_of(client, admin, cid)
    assert len(rooms) == 1
    assert rooms[0]["capacity"] == 6, f"应选 6 座小教室，实际 {rooms[0]}"


def test_exam_seats_priority_over_capacity(client, db_mode):
    """考试座位数=2 < 上课容量=60 → 4 人必须切成 2 个考场（考务按考试座位数）。"""
    ids = _seed(db_mode, students=4,
                rooms=[("A1", 60, 2, False), ("A2", 60, 2, False), ("A3", 60, 2, False)])
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_batch(client, admin, ids["tt1"])
    client.post(f"{BASE}/exam/batches/{bid}/auto-arrange", headers=admin)
    rooms = _rooms_of(client, admin, cid)
    assert len(rooms) == 2, f"考试座位数 2/间，4 人应切 2 考场，实际 {len(rooms)}"
    assert all(r["capacity"] == 2 for r in rooms)


def test_spaced_seat_mode(client, db_mode):
    """隔座模式：6 座教室有效容纳 3 人，4 人切 2 考场且座位号为奇数。"""
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleRule
    ids = _seed(db_mode, students=4, rooms=[("B1", 6, None, False), ("B2", 6, None, False)])
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_batch(client, admin, ids["tt1"])
    db = get_sessionmaker()()
    db.add(AaScheduleRule(tenant_id=TID, batch_id=bid, rule_key="EXAM_SEAT_MODE",
                          rule_value_json='"SPACED"', status="ENABLED"))
    db.commit(); db.close()
    client.post(f"{BASE}/exam/batches/{bid}/auto-arrange", headers=admin)
    rooms = _rooms_of(client, admin, cid)
    assert len(rooms) == 2, "隔座后 6 座只容 3 人，4 人应切 2 考场"
    for rm in rooms:
        for s in _seats_of(client, admin, rm["examRoomId"]):
            assert s["seatNo"] % 2 == 1, f"隔座座位号必须为奇数，实际 {s['seatNo']}"


def test_room_not_reused_same_time(client, db_mode):
    """两门课同日同时段、只有一间教室 → 第二门 ROOM_SHORT（同教室同时段不可复用）。"""
    ids = _seed(db_mode, students=2, rooms=[("C1", 30, None, False)])
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/exam/batches", headers=admin,
                      json={"batchName": "同时段批次"}).json()["data"]["batchId"]
    cids = []
    for tt in (ids["tt1"], ids["tt2"]):
        cid = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=admin,
                          json={"teachingTaskId": str(tt)}).json()["data"]["examCourseId"]
        client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=admin, json={"action": "CONFIRM"})
        client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
                   json={"examDate": "2027-06-21", "startTime": "09:00", "endTime": "11:00",
                         "durationMinutes": 120})
        cids.append(cid)
    client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin)
    d = client.post(f"{BASE}/exam/batches/{bid}/auto-arrange", headers=admin).json()["data"]
    assert d["arrangedCourses"] == 1
    assert d["missedCourses"] == 1
    assert d["misses"][0]["reason"] == "ROOM_SHORT"
    assert "错开考试时间" in d["misses"][0]["detail"]


def test_no_time_reported(client, db_mode):
    ids = _seed(db_mode, students=2, rooms=[("D1", 30, None, False)])
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_batch(client, admin, ids["tt1"], with_time=False)
    d = client.post(f"{BASE}/exam/batches/{bid}/auto-arrange", headers=admin).json()["data"]
    assert d["missedCourses"] == 1
    assert d["misses"][0]["reason"] == "NO_TIME"
    assert _rooms_of(client, admin, cid) == []


def test_incremental_skips_arranged(client, db_mode):
    ids = _seed(db_mode, students=4, rooms=[("E1", 30, None, False)])
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_batch(client, admin, ids["tt1"])
    client.post(f"{BASE}/exam/batches/{bid}/auto-arrange", headers=admin)
    d2 = client.post(f"{BASE}/exam/batches/{bid}/auto-arrange", headers=admin).json()["data"]
    assert d2["arrangedCourses"] == 0 and d2["skippedCourses"] == 1
    assert len(_rooms_of(client, admin, cid)) == 1, "重复执行不得重复建考场"


def test_dry_run_not_persisted(client, db_mode):
    ids = _seed(db_mode, students=4, rooms=[("F1", 30, None, False)])
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_batch(client, admin, ids["tt1"])
    d = client.post(f"{BASE}/exam/batches/{bid}/auto-arrange?dryRun=true",
                    headers=admin).json()["data"]
    assert d["dryRun"] is True and d["arrangedCourses"] == 1
    assert _rooms_of(client, admin, cid) == [], "试排不得落库"


def test_clear_auto_preserves_manual_room(client, db_mode):
    """课程A手工考场 + 课程B自动考场 → 清除后 A 保留、B 清空（连带座位与监考）。"""
    ids = _seed(db_mode, students=4, rooms=[("G1", 30, None, False)])
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/exam/batches", headers=admin,
                      json={"batchName": "混合批次"}).json()["data"]["batchId"]
    cids = []
    for i, tt in enumerate((ids["tt1"], ids["tt2"])):
        cid = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=admin,
                          json={"teachingTaskId": str(tt)}).json()["data"]["examCourseId"]
        client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=admin, json={"action": "CONFIRM"})
        client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
                   json={"examDate": f"2027-06-2{i + 2}", "startTime": "09:00", "endTime": "11:00",
                         "durationMinutes": 120})
        cids.append(cid)
    client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin)
    # 课程A：手工考场
    client.post(f"{BASE}/exam/courses/{cids[0]}/rooms", headers=admin,
                json={"classroomText": "手工考场9", "capacity": 30})
    # 自动排考：A 已有考场被跳过，B 自动编排
    d = client.post(f"{BASE}/exam/batches/{bid}/auto-arrange", headers=admin).json()["data"]
    assert d["skippedCourses"] == 1 and d["arrangedCourses"] == 1
    # 清除自动结果
    c = client.delete(f"{BASE}/exam/batches/{bid}/auto-arrange", headers=admin).json()["data"]
    assert c["clearedRooms"] == 1
    a_rooms = _rooms_of(client, admin, cids[0])
    assert len(a_rooms) == 1 and a_rooms[0]["classroomText"] == "手工考场9", "手工考场必须保留"
    assert _rooms_of(client, admin, cids[1]) == [], "自动考场应被清除"


def test_draft_batch_rejects(client, db_mode):
    ids = _seed(db_mode, students=2, rooms=[("H1", 30, None, False)])
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/exam/batches", headers=admin,
                      json={"batchName": "草稿批次"}).json()["data"]["batchId"]
    r = client.post(f"{BASE}/exam/batches/{bid}/auto-arrange", headers=admin)
    assert r.status_code == 409, r.text


def test_student_forbidden(client, db_mode):
    ids = _seed(db_mode, students=2, rooms=[("I1", 30, None, False)])
    admin = _hdr(client, "school_admin01")
    bid, _cid = _confirmed_batch(client, admin, ids["tt1"])
    r = client.post(f"{BASE}/exam/batches/{bid}/auto-arrange",
                    headers=_stu_token("张三", "AX2401"))
    assert r.status_code == 403, r.text


def test_assign_times_teacher_slot_overlap(client, db_mode):
    """排考时间编排按时段重叠判撞（而非 start 精确相等）：同教师(teacher_b)跨班两门课，
    场次 09:00-11:00 与 10:00-12:00 重叠。修复前 start 10:00≠09:00 会漏判，把第二门错排到
    10:00 造成同教师时间冲突；修复后第二门须跳到不重叠的 14:00-16:00。"""
    ids = _seed(db_mode, students=4, rooms=[], extra_class=True)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/exam/batches", headers=admin,
                      json={"batchName": "时段重叠回归"}).json()["data"]["batchId"]
    for tt in ("tt2", "tt3"):  # tt2=软件2401·teacher_b, tt3=空班2402·teacher_b（同教师不同班）
        cid = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=admin,
                          json={"teachingTaskId": str(ids[tt])}).json()["data"]["examCourseId"]
        client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=admin, json={"action": "CONFIRM"})
    client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin)
    r = client.post(f"{BASE}/exam/batches/{bid}/auto-times", headers=admin, json={
        "dates": ["2027-06-20"],
        "sessions": [{"start": "09:00", "end": "11:00"}, {"start": "10:00", "end": "12:00"},
                     {"start": "14:00", "end": "16:00"}],
        "maxPerDayPerClass": 1})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["assigned"] == 2 and d["missed"] == 0, d
    times = sorted(i["startTime"] for i in d["items"])
    assert times == ["09:00", "14:00"], f"同教师时段重叠未生效，第二门错排到重叠场次: {times}"
