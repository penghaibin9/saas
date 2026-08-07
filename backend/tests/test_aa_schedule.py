"""13B-P4 课表 · 端到端（三重冲突检测 + 单双周 + 三视图 + 发布）。

S1 教师冲突409；S2 班级冲突409；S3 教室冲突409；S4 单双周不冲突；S5 导入带冲突清单；
S6 发布通知；S7 三视图；S8 作废重发。

历史版本硬编码 termId="1" 并且隐式依赖别的测试/别的会话在共享 MySQL 测试库里遗留的
教学任务行来让 `_resolve_task()` 模糊匹配命中——这在长期复用的 student_lifecycle_test
库上并不成立（自增计数器早已远超 1，也没有任何持久遗留的 READY 教学任务）。本文件改为
自建学期 + 教学任务批次 + 五个 READY 教学任务，覆盖全部用例实际用到的
(课程, 教师, 行政班) 组合，测试自身完全自包含。
"""
from __future__ import annotations

from datetime import date, timedelta

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _term(client, hdr) -> str:
    """建一个已发布(current)学期；不能假设 AaTerm 自增 id=1。"""
    start = date(2026, 9, 1)
    tid = client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": "2099-2100", "termNo": 1, "termName": "课表回归测试学期",
        "startDate": start.isoformat(), "endDate": (start + timedelta(days=200)).isoformat(),
        "teachingWeeks": 18}).json()["data"]["termId"]
    client.post(f"{BASE}/terms/{tid}/publish", headers=hdr)
    return str(tid)


def _seed(db_mode, term_id: str):
    """建行政班/学生 + 一条 APPROVED 教学任务批次 + 全部用例实际用到的
    (courseName=高数, teacherKey, classId) 组合各一条 READY 教学任务。"""
    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTimeSlot, College,
                            SchoolClass, StudentProfile)
    db = get_sessionmaker()()
    for slot_no in range(1, 6):
        db.add(AaTimeSlot(tenant_id=TID, slot_no=slot_no, slot_name=f"第{slot_no}节",
                          start_time="00:00", end_time="23:59", enabled=True, status="ENABLED"))
    col = College(tenant_id=TID, college_name="课表回归测试学院", status="ACTIVE")
    db.add(col); db.flush()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2601", grade="2026", status="ACTIVE")
    db.add(a); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="SC001", real_name="课表甲", class_id=a.id,
                       current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    course = AaCourse(tenant_id=TID, course_code="GS_SCHED_TEST", course_name="高数", credit=4)
    db.add(course); db.flush()

    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=int(term_id), batch_name="课表回归测试教学任务批次",
                             college_id=col.id, status="APPROVED")
    db.add(tb); db.flush()

    def _task(teacher_key, teacher_name, class_id, class_name):
        db.add(AaTeachingTask(
            tenant_id=TID, batch_id=tb.id, course_id=course.id, course_name="高数", class_id=int(class_id),
            teaching_class_name=class_name, teacher_key=teacher_key, teacher_name=teacher_name,
            status="READY", weekly_hours=8, total_hours=144, start_week=1, end_week=18,
        ))

    # 覆盖全部用例实际用到的 (teacherKey, classId) 组合。
    _task("T1", "王老师", 100, "软件2601")
    _task("T1", "王老师", 200, "软件2602")
    _task("T2", "李老师", 100, "软件2601")
    _task("T2", "李老师", 200, "软件2602")
    _task("T1", "王老师", a.id, "软件2601")  # test_s7 用真实行政班 id
    db.flush()
    ids = {"class": a.id, "student": s.id}
    db.commit()
    db.close()
    return ids


def _batch(client, hdr, term_id: str):
    return client.post(f"{BASE}/schedule-batches", headers=hdr, json={"termId": term_id}).json()["data"]["batchId"]


def _item(client, hdr, bid, **kw):
    body = {"weekday": 1, "slotNo": 1, "startWeek": 1, "endWeek": 18, "weekParity": "ALL",
            "teacherKey": "T1", "teacherName": "王老师", "classId": "100", "className": "软件2601",
            "classroom": "A101", "courseName": "高数", **kw}
    return client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json=body)


def _setup(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    term_id = _term(client, hdr)
    ids = _seed(db_mode, term_id)
    bid = _batch(client, hdr, term_id)
    return hdr, bid, ids


def _seed_single_publishable_task(term_id: str) -> int:
    """预发布关卡要求批次学期下全部 READY 教学任务都排满 weekly_hours——S1-S5 共用的
    5 个任务(weekly_hours=8)只排 1 节课必然"漏排"。S6/S8 需要独立的、weekly_hours=1
    且只有这一条任务的最小化数据，才能让批次真正达到可发布状态；同时挂一个真实行政班
    +学生，"发布通知"才有真实接收对象（notified>=1），不是排到一个查无此人的假班级号。"""
    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTimeSlot, College,
                            SchoolClass, StudentProfile, User)
    db = get_sessionmaker()()
    db.add(AaTimeSlot(tenant_id=TID, slot_no=1, slot_name="第1节",
                      start_time="00:00", end_time="23:59", enabled=True, status="ENABLED"))
    # 发布通知按 teacher_key 匹配 User.login_name 找接收账号——没有真实教师账号，
    # notified 永远是 0，"发布通知"这条断言就验证不到任何东西。
    db.add(User(tenant_id=TID, login_name="T1", real_name="王老师", user_type="TEACHER", status="ACTIVE",
               password_hash="x"))
    col = College(tenant_id=TID, college_name="课表发布测试学院", status="ACTIVE")
    db.add(col); db.flush()
    cls = SchoolClass(tenant_id=TID, major_id=1, class_name="发布测试班", grade="2026", status="ACTIVE")
    db.add(cls); db.flush()
    db.add(StudentProfile(tenant_id=TID, student_no="PUB001", real_name="发布测试生", class_id=cls.id,
                          current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE"))
    course = AaCourse(tenant_id=TID, course_code="GS_PUBLISH_TEST", course_name="高数", credit=4)
    db.add(course); db.flush()
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=int(term_id), batch_name="课表发布测试教学任务批次",
                             college_id=col.id, status="APPROVED")
    db.add(tb); db.flush()
    db.add(AaTeachingTask(
        tenant_id=TID, batch_id=tb.id, course_id=course.id, course_name="高数", class_id=cls.id,
        teaching_class_name="发布测试班", teacher_key="T1", teacher_name="王老师",
        status="READY", weekly_hours=1, total_hours=18, start_week=1, end_week=18,
    ))
    db.commit()
    db.close()
    return cls.id


def _setup_publishable(client, db_mode):
    """只建 1 个 weekly_hours=1 的教学任务，排 1 节课即可满足预发布"全部任务已排满"的要求。"""
    hdr = _hdr(client, "school_admin01")
    term_id = _term(client, hdr)
    class_id = _seed_single_publishable_task(term_id)
    bid = _batch(client, hdr, term_id)
    return hdr, bid, class_id


def test_s1_teacher_conflict(client, db_mode):
    hdr, bid, _ids = _setup(client, db_mode)
    assert _item(client, hdr, bid).status_code == 200
    # 同教师同时段，换班换教室 → 教师冲突
    r = _item(client, hdr, bid, classId="200", classroom="B202")
    assert r.status_code == 409 and "TEACHER" in r.json()["message"]


def test_s2_class_conflict(client, db_mode):
    hdr, bid, _ids = _setup(client, db_mode)
    _item(client, hdr, bid)
    r = _item(client, hdr, bid, teacherKey="T2", teacherName="李老师", classroom="B202")
    assert r.status_code == 409 and "CLASS" in r.json()["message"]


def test_s3_classroom_conflict(client, db_mode):
    hdr, bid, _ids = _setup(client, db_mode)
    _item(client, hdr, bid)
    r = _item(client, hdr, bid, teacherKey="T2", teacherName="李老师", classId="200", className="X")
    assert r.status_code == 409 and "CLASSROOM" in r.json()["message"]


def test_s4_parity_no_conflict(client, db_mode):
    hdr, bid, _ids = _setup(client, db_mode)
    # 单周排 T1，双周同时段同教师排 → 不冲突（单双周错开）
    assert _item(client, hdr, bid, weekParity="ODD").status_code == 200
    assert _item(client, hdr, bid, weekParity="EVEN").status_code == 200
    # 但单周再排同教师 → 冲突
    assert _item(client, hdr, bid, weekParity="ODD").status_code == 409


def test_s5_import_reports_conflicts(client, db_mode):
    """默认 atomic=True：整批中 1 行冲突则整批不写入（P1 批次B——ATOMIC/PARTIAL 契约默认从严）。"""
    hdr, bid, _ids = _setup(client, db_mode)
    r = client.post(f"{BASE}/schedule-batches/{bid}/import", headers=hdr, json={"items": [
        {"courseName": "高数", "weekday": 2, "slotNo": 1, "teacherKey": "T1", "classId": "100", "classroom": "A101"},
        {"courseName": "高数", "weekday": 2, "slotNo": 1, "teacherKey": "T1", "classId": "200", "classroom": "B202"},  # 教师冲突
    ]}).json()
    assert r["data"]["imported"] == 0 and len(r["data"]["conflicts"]) == 1
    assert r["data"]["atomic"] is True and r["data"]["committed"] is False
    # 两行都没有真正写入课表——不是只挡住冲突的第 2 行
    view = client.get(f"{BASE}/schedule-batches/{bid}/teacher-view?teacherKey=T1", headers=hdr).json()
    assert len(view["data"]["items"]) == 0


def test_s5b_import_partial_mode_commits_valid_rows(client, db_mode):
    """显式 atomic=False：允许逐行尽力导入，成功行落库、失败行进 conflicts。"""
    hdr, bid, _ids = _setup(client, db_mode)
    r = client.post(f"{BASE}/schedule-batches/{bid}/import", headers=hdr, json={
        "atomic": False,
        "items": [
            {"courseName": "高数", "weekday": 2, "slotNo": 1, "teacherKey": "T1", "classId": "100", "classroom": "A101"},
            {"courseName": "高数", "weekday": 2, "slotNo": 1, "teacherKey": "T1", "classId": "200", "classroom": "B202"},  # 教师冲突
        ],
    }).json()
    assert r["data"]["imported"] == 1 and len(r["data"]["conflicts"]) == 1
    assert r["data"]["atomic"] is False and r["data"]["committed"] is True
    view = client.get(f"{BASE}/schedule-batches/{bid}/teacher-view?teacherKey=T1", headers=hdr).json()
    assert len(view["data"]["items"]) == 1


def test_s6_publish_notifies(client, db_mode):
    hdr, bid, class_id = _setup_publishable(client, db_mode)
    item_r = _item(client, hdr, bid, classId=str(class_id))
    assert item_r.status_code == 200, item_r.text
    pre_r = client.post(f"{BASE}/schedule-batches/{bid}/pre-publish", headers=hdr)
    assert pre_r.status_code == 200, pre_r.text
    r = client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=hdr).json()
    assert r["data"]["status"] == "PUBLISHED" and r["data"]["notified"] >= 1


def test_s7_three_views(client, db_mode):
    hdr, bid, ids = _setup(client, db_mode)
    _item(client, hdr, bid, classId=str(ids["class"]))
    cv = client.get(f"{BASE}/schedule-batches/{bid}/class-view?classId={ids['class']}", headers=hdr).json()
    tv = client.get(f"{BASE}/schedule-batches/{bid}/teacher-view?teacherKey=T1", headers=hdr).json()
    sv = client.get(f"{BASE}/schedule-batches/{bid}/student-view?studentId={ids['student']}", headers=hdr).json()
    assert len(cv["data"]["items"]) == 1 and len(tv["data"]["items"]) == 1
    assert len(sv["data"]["items"]) == 1  # 学生按行政班推导出本班课表


def test_s8_void_reissue(client, db_mode):
    hdr, bid, class_id = _setup_publishable(client, db_mode)
    _item(client, hdr, bid, classId=str(class_id))
    client.post(f"{BASE}/schedule-batches/{bid}/pre-publish", headers=hdr)
    client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=hdr)
    r = client.post(f"{BASE}/schedule-batches/{bid}/void-reissue", headers=hdr,
                    json={"reason": "临时调整教学安排"}).json()
    assert r["data"]["status"] == "ARCHIVED"
