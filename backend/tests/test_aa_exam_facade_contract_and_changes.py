"""考务批次A回归：Facade 去 fallback / 监考巡考显式变更 / canonical 教室并发安全。

- Facade 去 fallback：运行时断言公开入口不再靠 __getattr__ 动态穿透到 legacy，
  新增 legacy 函数不会自动出现在 Router 可调用范围内。
- 监考/巡考：发布后普通指定入口必须 409，只能走 change_invigilator/change_patrol；
  两个并发请求抢同一个老师的监考名额只能有一个成功。
- 考场：add_room 支持 canonical classroomId；并发建考场的室号分配不撞号
  （真实 MySQL 并发验证）。

MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

import threading

import pytest

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    response = client.post("/api/v1/auth/mock-login", json={"loginName": login_name, "password": "any"})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (AaClassroom, AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm,
                            College, Major, SchoolClass, StudentProfile, User)
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2024-2025", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
    course = AaCourse(tenant_id=TID, course_code="FA_MATH", course_name="高等数学", credit=4,
                      version=1, status="ENABLED")
    db.add(course); db.flush()
    room_a = AaClassroom(tenant_id=TID, building_code="A", building_name="A楼", room_code="101",
                         room_name="A101", capacity=50, status="AVAILABLE")
    db.add(room_a); db.flush()
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name="2024秋教学任务",
                             college_id=col.id, status="DRAFT")
    db.add(tb); db.flush()
    task = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=course.id, course_code=course.course_code, course_name="高等数学",
                          class_id=klass.id, teaching_class_name="软件2401",
                          teacher_key="teacher_a", teacher_name="甲老师")
    db.add(task); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="FA2401", real_name="考甲", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    db.add(s1); db.flush()
    from tests.test_aa_exam import _seed_exam_review_identity
    _seed_exam_review_identity(db, col.id)
    for login, name, user_type in (("teacher_x", "监考甲", "TEACHER"),
                                   ("teacher_y", "监考乙", "TEACHER"),
                                   ("teacher_z", "监考丙", "TEACHER"),
                                   ("teacher_race", "抢位老师", "TEACHER"),
                                   ("teacher_p", "巡考甲", "STAFF"),
                                   ("teacher_q", "巡考乙", "STAFF")):
        if not db.query(User).filter(User.tenant_id == TID, User.login_name == login).first():
            db.add(User(tenant_id=TID, login_name=login, real_name=name,
                        user_type=user_type, password_hash="x", status="ACTIVE"))
    ids = {"term": term.id, "task": task.id, "s1": s1.id, "roomA": room_a.id}
    db.commit(); db.close()
    return ids


def _confirmed_course(client, admin, ids, name="2024秋期末"):
    from tests.test_aa_exam import _prepare_task_batch_for_exam
    _prepare_task_batch_for_exam(client, admin, ids["task"])
    created = client.post(f"{BASE}/exam/batches", headers=admin, json={"batchName": name, "termId": str(ids["term"])})
    assert created.status_code == 200, created.text
    bid = created.json()["data"]["batchId"]
    added = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=admin, json={"teachingTaskId": str(ids["task"])})
    assert added.status_code == 200, added.text
    cid = added.json()["data"]["examCourseId"]
    confirmed = client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=_hdr(client, "college_admin01"), json={"action": "CONFIRM"})
    assert confirmed.status_code == 200, confirmed.text
    scheduled = client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
               json={"examDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00",
                     "durationMinutes": 120})
    assert scheduled.status_code == 200, scheduled.text
    advanced = client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin)
    assert advanced.status_code == 200, advanced.text
    return bid, cid


# ── Facade 去 fallback ──

def test_facade_has_no_dynamic_fallback():
    """去 fallback 的核心可验证点：模块级 __getattr__ 不存在。

    在此之前，Router 调用任何 legacy 函数（哪怕从未被审查过）都会自动可用；现在新增
    legacy 函数不会自动出现在 Router 可调用范围——必须显式登记才行。
    """
    import app.models  # noqa: F401
    from app.modules.academic_affairs.services import academic_affairs_exam_facade as facade

    assert not hasattr(type(facade), "__getattr__")
    assert "__getattr__" not in vars(facade)


def test_all_router_referenced_names_are_explicit_module_attributes():
    """Router 里每一个 exam_svc.xxx 调用的名字，都必须是 facade 模块的顶层显式属性
    （不是靠 __getattr__ 兜底才存在的）——去掉 fallback 后这本来就是自动成立的，
    这里再显式断言一次，把"router 用到的名字"和"facade 真正声明的名字"钉死成契约。
    """
    import re
    from pathlib import Path

    import app.models  # noqa: F401
    from app.modules.academic_affairs.services import academic_affairs_exam_facade as facade

    router_src = (
        Path(__file__).resolve().parents[1]
        / "app/modules/academic_affairs/routers/academic_affairs.py"
    ).read_text(encoding="utf-8")
    names = sorted(set(re.findall(r"(?<![a-zA-Z_])exam_svc\.([a-zA-Z_]\w*)", router_src)))
    assert names, "没有解析到任何 exam_svc.xxx 调用，正则可能失配"
    missing = [name for name in names if not hasattr(facade, name)]
    assert not missing, f"Router 用到但 facade 没有显式声明的名字：{missing}"


def test_publish_and_incident_and_defer_still_resolve_to_facade_module():
    """抽查几个此前已经加固过的高危函数，运行时确认仍落在 facade 而不是意外落回 legacy。"""
    import app.models  # noqa: F401
    from app.modules.academic_affairs.services import academic_affairs_exam_facade as facade

    for name in ("publish_batch", "record_incident", "defer_apply", "set_course_schedule",
                 "assign_seats", "add_room", "assign_invigilator", "change_invigilator",
                 "assign_patrol", "change_patrol"):
        fn = getattr(facade, name)
        assert fn.__module__.endswith("academic_affairs_exam_facade"), name


# ── canonical classroomId + 并发安全室号分配 ──

def test_add_room_accepts_canonical_classroom_id(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, cid = _confirmed_course(client, admin, ids)
    r = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                    json={"classroomId": str(ids["roomA"]), "capacity": 50})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["classroomText"] == "A101"

    from app.db.session import get_sessionmaker
    from app.models import AaExamRoom
    db = get_sessionmaker()()
    row = db.get(AaExamRoom, int(d["examRoomId"]))
    assert int(row.classroom_id) == int(ids["roomA"])
    db.close()


def test_add_room_rejects_unavailable_classroom(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaClassroom

    ids = _seed(db_mode)
    db = get_sessionmaker()()
    db.get(AaClassroom, ids["roomA"]).status = "MAINTENANCE"
    db.commit(); db.close()

    admin = _hdr(client, "school_admin01")
    _bid, cid = _confirmed_course(client, admin, ids)
    r = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                    json={"classroomId": str(ids["roomA"]), "capacity": 50})
    assert r.status_code == 409


def test_concurrent_add_room_never_duplicates_room_seq(client, db_mode):
    """真实 MySQL 并发：8 个线程同时给同一门课建考场，室号必须是 1..8 不重号。

    原实现是 count()+1 算室号，两个并发请求可能读到同样的 count 再各自 INSERT，
    只能靠事后撞唯一键兜底、体验很差；现在课程行锁把这段串行化。
    """
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, cid = _confirmed_course(client, admin, ids)

    workers = 8
    results, errors = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(workers)

    def _add():
        try:
            barrier.wait(timeout=30)
            r = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                            json={"classroomText": "临时教室", "capacity": 10})
            with lock:
                if r.status_code == 200:
                    results.append(r.json()["data"]["roomSeq"])
                else:
                    errors.append((r.status_code, r.text))
        except Exception as exc:  # noqa: BLE001
            with lock:
                errors.append((None, repr(exc)))

    threads = [threading.Thread(target=_add) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=90)

    assert not errors, f"并发建考场出现异常：{errors}"
    assert len(results) == workers
    assert sorted(results) == list(range(1, workers + 1)), f"室号重号/跳号：{sorted(results)}"


# ── 监考：发布后禁止普通指定，只能显式变更 ──

def test_assign_invigilator_allowed_before_publish(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, cid = _confirmed_course(client, admin, ids)
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomId": str(ids["roomA"]), "capacity": 50}).json()["data"]["examRoomId"]
    r = client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                    json={"teacherKey": "teacher_x", "teacherName": "监考老师"})
    assert r.status_code == 200, r.text


def test_assign_invigilator_requires_current_other_course_teacher(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import User

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, cid = _confirmed_course(client, admin, ids)
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomId": str(ids["roomA"]), "capacity": 50}).json()["data"]["examRoomId"]
    with get_sessionmaker()() as db:
        db.add(User(tenant_id=TID, login_name="inactive_invigilator", real_name="停用教师",
                    user_type="TEACHER", password_hash="x", status="DISABLED"))
        db.add(User(tenant_id=TID, login_name="staff_invigilator", real_name="非教师",
                    user_type="STAFF", password_hash="x", status="ACTIVE"))
        db.commit()
    for key in ("missing_invigilator", "inactive_invigilator", "staff_invigilator", "teacher_a"):
        denied = client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                             json={"teacherKey": key, "teacherName": "客户端伪造姓名"})
        assert denied.status_code in (400, 409), (key, denied.text)
    allowed = client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                          json={"teacherKey": "teacher_x", "teacherName": "客户端伪造姓名"})
    assert allowed.status_code == 200, allowed.text
    listed = client.get(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin).json()["data"]["items"]
    assert listed[0]["teacherName"] == "监考甲"


def test_readiness_and_publish_count_distinct_valid_invigilators(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaExamInvigilator, User

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomId": str(ids["roomA"]), "capacity": 50}).json()["data"]["examRoomId"]
    assert client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin,
                       json={"studentIds": [str(ids["s1"])]}).status_code == 200
    assert client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                       json={"teacherKey": "teacher_x", "teacherName": "监考甲"}).status_code == 200
    with get_sessionmaker()() as db:
        teacher_id = db.query(User.id).filter(User.tenant_id == TID, User.login_name == "teacher_x").scalar()
        db.add(AaExamInvigilator(tenant_id=TID, exam_room_id=int(rid),
                                 teacher_key=f"u_{teacher_id}", teacher_name="旧别名重复",
                                 role="ASSISTANT", confirm_status="ASSIGNED"))
        db.commit()
    readiness = client.get(f"{BASE}/exam/batches/{bid}/readiness", headers=admin).json()["data"]
    assert readiness["invigilatorGapCount"] == 1
    assert readiness["canPublish"] is False
    assert client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin).status_code == 409
    with get_sessionmaker()() as db:
        alias = db.query(AaExamInvigilator).filter(
            AaExamInvigilator.tenant_id == TID,
            AaExamInvigilator.exam_room_id == int(rid),
            AaExamInvigilator.teacher_key == f"u_{teacher_id}",
        ).one()
        alias.is_deleted = True
        db.commit()
    assert client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                       json={"teacherKey": "teacher_y", "teacherName": "监考乙"}).status_code == 200
    readiness = client.get(f"{BASE}/exam/batches/{bid}/readiness", headers=admin).json()["data"]
    assert readiness["invigilatorGapCount"] == 0
    assert readiness["canPublish"] is True
    assert client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin).status_code == 200


def test_existing_exam_rules_apply_to_manual_assignment_and_publish(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleRule

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomId": str(ids["roomA"]), "capacity": 50}).json()["data"]["examRoomId"]
    with get_sessionmaker()() as db:
        db.add(AaScheduleRule(tenant_id=TID, term_id=ids["term"],
                              rule_key="EXAM_AVOID_OWN_COURSE", rule_value_json="false", status="ENABLED"))
        db.add(AaScheduleRule(tenant_id=TID, term_id=ids["term"],
                              rule_key="EXAM_INVIGILATORS_PER_ROOM", rule_value_json="1", status="ENABLED"))
        db.commit()
    assigned = client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                           json={"teacherKey": "teacher_a", "teacherName": "客户端姓名"})
    assert assigned.status_code == 200, assigned.text
    assert client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin,
                       json={"studentIds": [str(ids["s1"])]}).status_code == 200
    readiness = client.get(f"{BASE}/exam/batches/{bid}/readiness", headers=admin).json()["data"]
    assert readiness["invigilatorGapCount"] == 0
    assert readiness["canPublish"] is True
    assert client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin).status_code == 200


def test_change_replaces_historical_invalid_teacher_but_rejects_own_course(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaExamInvigilator

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomId": str(ids["roomA"]), "capacity": 50}).json()["data"]["examRoomId"]
    assert client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin,
                       json={"studentIds": [str(ids["s1"])]}).status_code == 200
    for key in ("teacher_x", "teacher_y"):
        assert client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                           json={"teacherKey": key}).status_code == 200
    assert client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin).status_code == 200
    with get_sessionmaker()() as db:
        row = db.query(AaExamInvigilator).filter(
            AaExamInvigilator.tenant_id == TID, AaExamInvigilator.exam_room_id == int(rid),
            AaExamInvigilator.teacher_key == "teacher_x",
        ).one()
        row.teacher_key = "old_deleted_teacher"
        db.commit()
    own = client.post(f"{BASE}/exam/rooms/{rid}/invigilators/change", headers=admin, json={
        "oldTeacherKey": "old_deleted_teacher", "newTeacherKey": "teacher_a",
        "reason": "旧监考身份已失效需换人",
    })
    assert own.status_code == 409
    changed = client.post(f"{BASE}/exam/rooms/{rid}/invigilators/change", headers=admin, json={
        "oldTeacherKey": "old_deleted_teacher", "newTeacherKey": "teacher_z",
        "newTeacherName": "伪造姓名", "reason": "旧监考身份已失效需换人",
    })
    assert changed.status_code == 200, changed.text
    listed = client.get(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin).json()["data"]["items"]
    assert next(item for item in listed if item["teacherKey"] == "teacher_z")["teacherName"] == "监考丙"


def test_assign_invigilator_after_publish_rejected(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomId": str(ids["roomA"]), "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
               json={"teacherKey": "teacher_x", "teacherName": "监考老师"})
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
               json={"teacherKey": "teacher_y", "teacherName": "监考乙"})
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin, json={"studentIds": [str(ids["s1"])]})
    published = client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
    assert published.status_code == 200, published.text

    r = client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                    json={"teacherKey": "teacher_y", "teacherName": "另一位老师"})
    assert r.status_code == 409
    assert "change_invigilator" in r.text


def test_change_invigilator_after_publish_succeeds_with_reason(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomId": str(ids["roomA"]), "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
               json={"teacherKey": "teacher_x", "teacherName": "原监考"})
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
               json={"teacherKey": "teacher_y", "teacherName": "监考乙"})
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin, json={"studentIds": [str(ids["s1"])]})
    client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)

    r = client.post(f"{BASE}/exam/rooms/{rid}/invigilators/change", headers=admin, json={
        "oldTeacherKey": "teacher_x", "newTeacherKey": "teacher_z",
        "newTeacherName": "新监考", "reason": "原老师临时请假",
    })
    assert r.status_code == 200, r.text
    invs = client.get(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin).json()["data"]["items"]
    keys = {i["teacherKey"] for i in invs}
    assert keys == {"teacher_y", "teacher_z"}

    from app.db.session import get_sessionmaker
    from app.models import AaExamAuditTrail
    db = get_sessionmaker()()
    trail = db.query(AaExamAuditTrail).filter(
        AaExamAuditTrail.tenant_id == TID,
        AaExamAuditTrail.action == "EXAM_INVIGILATOR_CHANGE").first()
    assert trail is not None and "teacher_x" in (trail.before_val or "") and "teacher_z" in (trail.after_val or "")
    db.close()


def test_change_invigilator_requires_reason(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomId": str(ids["roomA"]), "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
               json={"teacherKey": "teacher_x", "teacherName": "原监考"})
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
               json={"teacherKey": "teacher_y", "teacherName": "监考乙"})
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin, json={"studentIds": [str(ids["s1"])]})
    client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)

    r = client.post(f"{BASE}/exam/rooms/{rid}/invigilators/change", headers=admin, json={
        "oldTeacherKey": "teacher_x", "newTeacherKey": "teacher_y", "reason": "太短",
    })
    assert r.status_code == 400


def test_concurrent_assign_invigilator_only_one_wins_the_teacher_slot(client, db_mode):
    """真实 MySQL 并发：两个考场同时抢同一个老师同一时段监考，只能一个成功。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, cid = _confirmed_course(client, admin, ids)
    rid1 = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                       json={"classroomText": "考场甲", "capacity": 50}).json()["data"]["examRoomId"]
    rid2 = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                       json={"classroomText": "考场乙", "capacity": 50}).json()["data"]["examRoomId"]

    results, errors = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def _assign(room_id):
        try:
            barrier.wait(timeout=30)
            r = client.post(f"{BASE}/exam/rooms/{room_id}/invigilators", headers=admin,
                            json={"teacherKey": "teacher_race", "teacherName": "抢位老师"})
            with lock:
                if r.status_code == 200:
                    results.append(room_id)
                else:
                    errors.append((room_id, r.status_code))
        except Exception as exc:  # noqa: BLE001
            with lock:
                errors.append((room_id, repr(exc)))

    threads = [threading.Thread(target=_assign, args=(rid1,)),
               threading.Thread(target=_assign, args=(rid2,))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=90)

    assert len(results) == 1, f"两个考场都抢到了同一个老师同一时段：成功={results} 失败={errors}"
    assert len(errors) == 1 and errors[0][1] == 409


# ── 巡考：发布后禁止普通指定，只能显式变更 ──

def test_patrol_accepts_real_staff_but_rejects_invalid_accounts(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import User

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, _cid = _confirmed_course(client, admin, ids)
    with get_sessionmaker()() as db:
        db.add(User(tenant_id=TID, login_name="inactive_patrol", real_name="停用人员",
                    user_type="STAFF", password_hash="x", status="DISABLED"))
        db.add(User(tenant_id=TID, login_name="student_patrol", real_name="学生",
                    user_type="STUDENT", password_hash="x", status="ACTIVE"))
        for user_type in ("GUARDIAN", "ENTERPRISE_MENTOR", "PLATFORM_OP"):
            db.add(User(tenant_id=TID, login_name=f"{user_type.lower()}_patrol",
                        real_name="非本校教职工", user_type=user_type,
                        password_hash="x", status="ACTIVE"))
        db.add(User(tenant_id=TID, login_name="admin_patrol", real_name="学校管理员",
                    user_type="ADMIN", password_hash="x", status="ACTIVE"))
        db.commit()
    for key in ("missing_patrol", "inactive_patrol", "student_patrol",
                "guardian_patrol", "enterprise_mentor_patrol", "platform_op_patrol"):
        denied = client.post(f"{BASE}/exam/batches/{bid}/patrols", headers=admin, json={
            "teacherKey": key, "patrolDate": "2027-06-20",
            "startTime": "09:00", "endTime": "11:00",
        })
        assert denied.status_code == 400, (key, denied.text)
    allowed = client.post(f"{BASE}/exam/batches/{bid}/patrols", headers=admin, json={
        "teacherKey": "teacher_p", "teacherName": "客户端伪造姓名",
        "patrolDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00",
    })
    assert allowed.status_code == 200, allowed.text
    listed = client.get(f"{BASE}/exam/batches/{bid}/patrols", headers=admin).json()["data"]["items"]
    assert listed[0]["teacherName"] == "巡考甲"
    school_admin = client.post(f"{BASE}/exam/batches/{bid}/patrols", headers=admin, json={
        "teacherKey": "admin_patrol", "patrolDate": "2027-06-20",
        "startTime": "09:00", "endTime": "11:00",
    })
    assert school_admin.status_code == 200, school_admin.text


def test_assign_patrol_after_publish_rejected_then_change_succeeds(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomId": str(ids["roomA"]), "capacity": 50}).json()["data"]["examRoomId"]
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
               json={"teacherKey": "teacher_x", "teacherName": "监考"})
    client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
               json={"teacherKey": "teacher_y", "teacherName": "监考乙"})
    client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin, json={"studentIds": [str(ids["s1"])]})

    patrol = client.post(f"{BASE}/exam/batches/{bid}/patrols", headers=admin, json={
        "teacherKey": "teacher_p", "teacherName": "巡考甲",
        "patrolDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00",
    })
    assert patrol.status_code == 200, patrol.text
    pid = patrol.json()["data"]["patrolId"]

    client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)

    blocked = client.post(f"{BASE}/exam/batches/{bid}/patrols", headers=admin, json={
        "teacherKey": "teacher_q", "teacherName": "巡考乙",
        "patrolDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00",
    })
    assert blocked.status_code == 409
    assert "change_patrol" in blocked.text

    changed = client.post(f"{BASE}/exam/patrols/{pid}/change", headers=admin, json={
        "newTeacherKey": "teacher_q", "newTeacherName": "巡考乙", "reason": "巡考甲临时有事",
    })
    assert changed.status_code == 200, changed.text


def test_patrol_then_invigilation_rejects_same_person_alias(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import User

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomId": str(ids["roomA"]), "capacity": 50}).json()["data"]["examRoomId"]
    with get_sessionmaker()() as db:
        teacher_id = db.query(User.id).filter(User.tenant_id == TID, User.login_name == "teacher_x").scalar()
    patrol = client.post(f"{BASE}/exam/batches/{bid}/patrols", headers=admin, json={
        "teacherKey": f"u_{teacher_id}", "teacherName": "客户端伪造姓名",
        "patrolDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00",
    })
    assert patrol.status_code == 200, patrol.text
    assert patrol.json()["data"]["teacherKey"] == "teacher_x"
    blocked = client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                          json={"teacherKey": "teacher_x"})
    assert blocked.status_code == 409 and "巡考" in blocked.text


def test_invigilation_then_patrol_or_change_rejects_same_person_alias(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import User

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _confirmed_course(client, admin, ids)
    rid = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                      json={"classroomId": str(ids["roomA"]), "capacity": 50}).json()["data"]["examRoomId"]
    for key in ("teacher_x", "teacher_y"):
        assert client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                           json={"teacherKey": key}).status_code == 200
    with get_sessionmaker()() as db:
        teacher_id = db.query(User.id).filter(User.tenant_id == TID, User.login_name == "teacher_x").scalar()
        replacement_id = db.query(User.id).filter(User.tenant_id == TID, User.login_name == "teacher_z").scalar()
    blocked = client.post(f"{BASE}/exam/batches/{bid}/patrols", headers=admin, json={
        "teacherKey": str(teacher_id), "patrolDate": "2027-06-20",
        "startTime": "09:00", "endTime": "11:00",
    })
    assert blocked.status_code == 409 and "监考" in blocked.text
    patrol = client.post(f"{BASE}/exam/batches/{bid}/patrols", headers=admin, json={
        "teacherKey": f"u_{replacement_id}", "teacherName": "客户端伪造姓名",
        "patrolDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00",
    })
    assert patrol.status_code == 200, patrol.text
    pid = patrol.json()["data"]["patrolId"]
    assert patrol.json()["data"]["teacherKey"] == "teacher_z"
    changed_patrol = client.post(f"{BASE}/exam/patrols/{pid}/change", headers=admin, json={
        "newTeacherKey": f"u_{teacher_id}", "reason": "同场监考无法兼做巡考",
    })
    assert changed_patrol.status_code == 409 and "监考" in changed_patrol.text
    changed_invigilator = client.post(f"{BASE}/exam/rooms/{rid}/invigilators/change", headers=admin, json={
        "oldTeacherKey": "teacher_x", "newTeacherKey": f"u_{replacement_id}",
        "reason": "同场巡考无法兼做监考",
    })
    assert changed_invigilator.status_code == 409 and "巡考" in changed_invigilator.text
