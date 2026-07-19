"""自动排课引擎（/academic-affairs/scheduling/batches/{id}/auto 等）端点测试。

覆盖重点不是"能跑通"，而是"不会排错"：
- 排出来的课表本身零冲突（教师/班级/教室三维 + 容量）
- 硬约束不会被悄悄放宽（宁可漏排也不排出冲突）
- **重排只清 AUTO 项，人工排的课绝不被覆盖**（本引擎最重要的安全边界）
- 漏排必须归因到根因，且原因可执行
- 已发布课表拒绝自动排课（409）
- 学生越权 403

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


def _seed(db_mode, *, tasks, rooms):
    """建 学期+课表批次+教室+教学任务。tasks/rooms 为轻量 dict 列表。"""
    from app.db.session import get_sessionmaker
    from app.models import AaClassroom, AaScheduleBatch, AaTeachingTask, AaTerm
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2024-2025", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    b = AaScheduleBatch(tenant_id=TID, term_id=term.id, batch_name="自动排课测试批次", status="DRAFT")
    db.add(b); db.flush()
    room_ids = []
    for r in rooms:
        c = AaClassroom(tenant_id=TID, building_code=r.get("bld", "A"), building_name=r.get("bld", "A") + "栋",
                        room_code=r["code"], capacity=r.get("cap", 60),
                        room_type=r.get("type", "LECTURE"),
                        is_exclusive=r.get("exclusive", False),
                        exam_seats=r.get("examSeats"),
                        status=r.get("status", "AVAILABLE"))
        db.add(c); db.flush()
        room_ids.append(c.id)
    task_ids = []
    for t in tasks:
        x = AaTeachingTask(tenant_id=TID, batch_id=b.id, course_id=t.get("courseId", 1),
                           course_name=t["course"], class_id=t.get("classId", 1),
                           teaching_class_name=t.get("className", "软件2401"),
                           teacher_key=t.get("teacher"), teacher_name=t.get("teacherName", "王老师"),
                           expected_students=t.get("headcount", 40),
                           weekly_hours=t.get("weekly", 2),
                           required_room_type=t.get("roomType"),
                           no_auto_schedule=t.get("noAuto", False),
                           status="CONFIRMED")
        db.add(x); db.flush()
        task_ids.append(x.id)
    db.commit()
    ids = {"term": term.id, "batch": b.id, "rooms": room_ids, "tasks": task_ids}
    db.close()
    return ids


def _items(batch_id):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem
    db = get_sessionmaker()()
    rows = db.query(AaScheduleItem).filter(
        AaScheduleItem.batch_id == batch_id, AaScheduleItem.is_deleted.is_(False)).all()
    out = [{"id": r.id, "task": r.task_id, "wd": r.weekday, "slot": r.slot_no,
            "teacher": r.teacher_key, "class": r.class_id, "room": r.classroom_id,
            "roomText": r.classroom_text, "source": r.source,
            "sw": r.start_week, "ew": r.end_week, "par": r.week_parity} for r in rows]
    db.close()
    return out


# ── 基本编排 ──

def test_auto_schedule_places_sessions(client, db_mode):
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": "t01", "weekly": 2, "headcount": 40}],
                rooms=[{"code": "101", "cap": 60}])
    r = client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["placedSessions"] == 2, d
    assert d["missedTasks"] == 0
    its = _items(ids["batch"])
    assert len(its) == 2
    assert all(i["source"] == "AUTO" for i in its)
    # 教室字典必须被真正关联（不是只写文本）
    assert all(i["room"] == ids["rooms"][0] for i in its)
    assert all(i["roomText"] for i in its)


def test_dry_run_does_not_persist(client, db_mode):
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": "t01", "weekly": 2}],
                rooms=[{"code": "101", "cap": 60}])
    r = client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto?dryRun=true",
                    headers=_hdr(client, "school_admin01"))
    assert r.status_code == 200
    assert r.json()["data"]["placedSessions"] == 2
    assert r.json()["data"]["dryRun"] is True
    assert _items(ids["batch"]) == []  # 只算不落


# ── 硬约束：排出来的课表必须零冲突 ──

def test_no_teacher_conflict_in_result(client, db_mode):
    """同一教师两门课，绝不能被排到同一时段。"""
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": "t01", "classId": 1, "weekly": 4},
                       {"course": "英语", "teacher": "t01", "classId": 2, "weekly": 4}],
                rooms=[{"code": "101", "cap": 60}, {"code": "102", "cap": 60}])
    client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    its = _items(ids["batch"])
    seen = set()
    for i in its:
        key = (i["teacher"], i["wd"], i["slot"])
        assert key not in seen, f"教师时间冲突: {key}"
        seen.add(key)


def test_no_room_double_booking(client, db_mode):
    """两个班同时段，只有一间教室 → 不能把两节课塞进同一间教室同一时段。"""
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": "t01", "classId": 1, "weekly": 2},
                       {"course": "英语", "teacher": "t02", "classId": 2, "weekly": 2}],
                rooms=[{"code": "101", "cap": 60}])
    client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    its = _items(ids["batch"])
    seen = set()
    for i in its:
        key = (i["room"], i["wd"], i["slot"])
        assert key not in seen, f"教室重复占用: {key}"
        seen.add(key)


def test_capacity_respected_not_silently_relaxed(client, db_mode):
    """人数 100 但只有 30 座教室 → 必须漏排并归因 ROOM_TOO_SMALL，不许硬塞。"""
    ids = _seed(db_mode,
                tasks=[{"course": "大课", "teacher": "t01", "weekly": 2, "headcount": 100}],
                rooms=[{"code": "101", "cap": 30}])
    r = client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    d = r.json()["data"]
    assert d["placedSessions"] == 0
    assert d["missedTasks"] == 1
    assert d["misses"][0]["reason"] == "ROOM_TOO_SMALL"
    assert "拆班" in d["misses"][0]["detail"]
    assert _items(ids["batch"]) == []


def test_room_type_match(client, db_mode):
    """任务要求机房，只有普通教室 → 漏排 NO_ROOM_TYPE，不许拿普通教室凑数。"""
    ids = _seed(db_mode,
                tasks=[{"course": "程序设计", "teacher": "t01", "weekly": 2, "roomType": "COMPUTER"}],
                rooms=[{"code": "101", "cap": 60, "type": "LECTURE"}])
    r = client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    d = r.json()["data"]
    assert d["missedTasks"] == 1
    assert d["misses"][0]["reason"] == "NO_ROOM_TYPE"


def test_exclusive_room_skipped(client, db_mode):
    """专用教室不参与自动排课 → 只有专用教室时漏排。"""
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": "t01", "weekly": 2}],
                rooms=[{"code": "R01", "cap": 60, "exclusive": True}])
    r = client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    assert r.json()["data"]["missedTasks"] == 1
    assert r.json()["data"]["roomPoolSize"] == 0


def test_no_teacher_assigned_reported(client, db_mode):
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": None, "weekly": 2}],
                rooms=[{"code": "101", "cap": 60}])
    r = client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    m = r.json()["data"]["misses"][0]
    assert m["reason"] == "NO_TEACHER"
    assert "分配任课教师" in m["detail"]


def test_no_auto_schedule_task_excluded(client, db_mode):
    """顶岗实习类任务标记 no_auto_schedule → 既不排课也不算漏排。"""
    ids = _seed(db_mode,
                tasks=[{"course": "顶岗实习", "teacher": "t01", "weekly": 20, "noAuto": True}],
                rooms=[{"code": "101", "cap": 60}])
    r = client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    d = r.json()["data"]
    assert d["placedSessions"] == 0
    assert d["missedTasks"] == 0, "标记不排课的任务不应计入漏排"


# ── 安全边界：人工排课不可被覆盖（本引擎最重要的一条）──

def test_clear_auto_preserves_manual(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": "t01", "weekly": 2}],
                rooms=[{"code": "101", "cap": 60}])
    # 教务员手工排的一节（source=MANUAL）
    db = get_sessionmaker()()
    db.add(AaScheduleItem(tenant_id=TID, batch_id=ids["batch"], course_name="手工排的课",
                          class_id=9, class_name="手工班", teacher_key="manual01",
                          weekday=5, slot_no=8, start_week=1, end_week=18, week_parity="ALL",
                          classroom_text="手工教室", status="EFFECTIVE", source="MANUAL"))
    db.commit(); db.close()

    client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    assert len([i for i in _items(ids["batch"]) if i["source"] == "AUTO"]) == 2

    r = client.delete(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    assert r.status_code == 200
    assert r.json()["data"]["cleared"] == 2
    left = _items(ids["batch"])
    assert len(left) == 1
    assert left[0]["source"] == "MANUAL"
    assert left[0]["roomText"] == "手工教室", "人工排课必须原样保留"


def test_auto_avoids_manual_occupied_slot(client, db_mode):
    """自动排课必须绕开人工已占用的教师时段，不能覆盖也不能撞车。"""
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": "t01", "weekly": 1}],
                rooms=[{"code": "101", "cap": 60}])
    db = get_sessionmaker()()
    # 人工把 t01 周一第1节占了
    db.add(AaScheduleItem(tenant_id=TID, batch_id=ids["batch"], course_name="人工课",
                          class_id=8, teacher_key="t01", weekday=1, slot_no=1,
                          start_week=1, end_week=18, week_parity="ALL",
                          status="EFFECTIVE", source="MANUAL"))
    db.commit(); db.close()
    client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    auto = [i for i in _items(ids["batch"]) if i["source"] == "AUTO"]
    assert len(auto) == 1
    assert not (auto[0]["wd"] == 1 and auto[0]["slot"] == 1), "自动排课撞上了人工排课的时段"


# ── 增量续排 ──

def test_incremental_does_not_duplicate(client, db_mode):
    """连点两次自动排课，不应把同一任务排两遍（增量语义）。"""
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": "t01", "weekly": 2}],
                rooms=[{"code": "101", "cap": 60}])
    h = _hdr(client, "school_admin01")
    client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=h)
    r2 = client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=h)
    assert r2.json()["data"]["placedSessions"] == 0, "第二次不应重复排课"
    assert len(_items(ids["batch"])) == 2


# ── 漏排报告 ──

def test_miss_report_groups_by_reason(client, db_mode):
    ids = _seed(db_mode,
                tasks=[{"course": "大课", "teacher": "t01", "weekly": 2, "headcount": 999},
                       {"course": "机房课", "teacher": "t02", "weekly": 2, "roomType": "COMPUTER"}],
                rooms=[{"code": "101", "cap": 30, "type": "LECTURE"}])
    r = client.get(f"{BASE}/scheduling/batches/{ids['batch']}/miss-report", headers=_hdr(client, "school_admin01"))
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["missedTasks"] == 2
    reasons = {s["reason"] for s in d["summary"]}
    assert reasons == {"ROOM_TOO_SMALL", "NO_ROOM_TYPE"}
    assert all(s["reasonLabel"] for s in d["summary"]), "原因必须有人话标签"
    assert _items(ids["batch"]) == [], "miss-report 是只读的，不得落库"


def test_rule_catalog(client, db_mode):
    r = client.get(f"{BASE}/scheduling/rule-catalog", headers=_hdr(client, "school_admin01"))
    assert r.status_code == 200
    d = r.json()["data"]
    assert len(d["items"]) >= 8
    assert d["defaults"]["capacityCheck"] is True


# ── 参数生效 ──

def test_forbidden_slots_respected(client, db_mode):
    """禁排周一 → 排出来的课不能落在周一。"""
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleRule
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": "t01", "weekly": 2}],
                rooms=[{"code": "101", "cap": 60}])
    db = get_sessionmaker()()
    db.add(AaScheduleRule(tenant_id=TID, batch_id=ids["batch"], rule_key="AUTO_FORBIDDEN",
                          rule_value_json='[{"weekday":1}]', status="ENABLED"))
    db.commit(); db.close()
    client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    assert all(i["wd"] != 1 for i in _items(ids["batch"])), "禁排时段被违反"


def test_teacher_availability_respected(client, db_mode):
    """教师已采纳的不可排时间必须被绕开。"""
    from app.db.session import get_sessionmaker
    from app.models import AaTeacherAvailability
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": "t01", "weekly": 1}],
                rooms=[{"code": "101", "cap": 60}])
    db = get_sessionmaker()()
    db.add(AaTeacherAvailability(tenant_id=TID, teacher_key="t01", term_id=ids["term"],
                                 weekday=1, slot_no=1, status="ADOPTED"))
    db.commit(); db.close()
    client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    its = _items(ids["batch"])
    assert not any(i["wd"] == 1 and i["slot"] == 1 for i in its)


# ── 状态与权限 ──

def test_published_batch_rejects_auto(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleBatch
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": "t01", "weekly": 2}],
                rooms=[{"code": "101", "cap": 60}])
    db = get_sessionmaker()()
    b = db.get(AaScheduleBatch, ids["batch"])
    b.status = "PUBLISHED"
    db.commit(); db.close()
    r = client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto", headers=_hdr(client, "school_admin01"))
    assert r.status_code == 409, r.text


def test_student_forbidden(client, db_mode):
    ids = _seed(db_mode,
                tasks=[{"course": "高数", "teacher": "t01", "weekly": 2}],
                rooms=[{"code": "101", "cap": 60}])
    r = client.post(f"{BASE}/scheduling/batches/{ids['batch']}/auto",
                    headers=_stu_token("张三", "2024001"))
    assert r.status_code == 403, r.text
