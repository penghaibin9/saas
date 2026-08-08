"""自动排考消费冻结名单回归（批次A·frozen roster）。

原实现 `_roster()` 直接按 `StudentProfile.class_id == ExamCourse.class_id` 查行政班学生，
选修课、重修跟班、分层教学、跨专业课程里，教学班成员从来不等于行政班成员——这里构造一门
挂靠在行政班A名下、但真正考生来自选课锁定名单（且选中的学生分布在另一个行政班）的课程：
- 旧实现会把行政班A的全部学生当考生（人数、身份都错）；
- 新实现读的是 confirm 时冻结的 EXAM_COURSE 消费者快照，与手工铺位(assign_seats)同一权威
  来源，只认真正选中的学生。

MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (AaClassroom, AaCourse, AaSelectionBatch, AaSelectionCourse,
                            AaSelectionRecord, AaTeachingTask, AaTeachingTaskBatch, AaTerm,
                            College, Major, SchoolClass, StudentProfile)
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2024-2025", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    # 课程挂靠的行政班A：2 名学生，谁都没有选这门课
    class_a = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024",
                          status="ACTIVE")
    # 真正选中这门课的学生所在的行政班B：与课程挂靠的行政班完全不同
    class_b = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2402", grade="2024",
                          status="ACTIVE")
    db.add_all([class_a, class_b]); db.flush()
    course = AaCourse(tenant_id=TID, course_code="FR_ELECTIVE", course_name="跨班选修课",
                      credit=2, status="ENABLED")
    db.add(course); db.flush()
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=term.id, batch_name="2024秋教学任务",
                             college_id=col.id, status="ACTIVE")
    db.add(tb); db.flush()
    task = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=course.id, course_name="跨班选修课",
                          class_id=class_a.id, teaching_class_name="软件2401选修班",
                          teacher_key="teacher_x", teacher_name="选修课老师")
    db.add(task); db.flush()

    a1 = StudentProfile(tenant_id=TID, student_no="FR2401", real_name="行政班A甲", college_id=col.id,
                        major_id=major.id, class_id=class_a.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    a2 = StudentProfile(tenant_id=TID, student_no="FR2402", real_name="行政班A乙", college_id=col.id,
                        major_id=major.id, class_id=class_a.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    b1 = StudentProfile(tenant_id=TID, student_no="FR2501", real_name="行政班B选课生", college_id=col.id,
                        major_id=major.id, class_id=class_b.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    db.add_all([a1, a2, b1]); db.flush()

    # 选课批次已锁定：只有 b1 选了这门课，a1/a2 从未选课
    sel_batch = AaSelectionBatch(tenant_id=TID, term_id=term.id, batch_name="2024秋选课批次",
                                 status="LOCKED")
    db.add(sel_batch); db.flush()
    sel_course = AaSelectionCourse(tenant_id=TID, batch_id=sel_batch.id, course_id=course.id,
                                   teaching_task_id=task.id, course_name=course.course_name,
                                   teacher_key="teacher_x", capacity=30, min_capacity=1,
                                   selected_count=1, status="OPEN")
    db.add(sel_course); db.flush()
    db.add(AaSelectionRecord(tenant_id=TID, batch_id=sel_batch.id, selection_course_id=sel_course.id,
                             course_id=course.id, course_name=course.course_name,
                             student_id=b1.id, student_no=b1.student_no, student_name=b1.real_name,
                             status="LOCKED"))
    room = AaClassroom(tenant_id=TID, building_code="F", building_name="F楼", room_code="101",
                       capacity=30, is_exclusive=False, room_type="LECTURE", status="AVAILABLE")
    db.add(room); db.flush()
    db.commit()

    # 真实流程里，选课批次锁定的同一时刻会把锁定名单投影进独立教学班版本（否则学院确认考试
    # 课程时读到的教学班仍是"尚未投影"状态，与本测试要验证的自动排考逻辑无关，先做掉）。
    from app.core.context import set_current_user, set_tenant
    from app.modules.academic_affairs.services.academic_affairs_selection_roster_projection_service import (
        project_selection_batch_locked,
    )

    set_tenant({"tenantId": str(TID)})
    set_current_user({"userId": "1", "tenantId": str(TID), "realName": "教务处",
                      "currentRoleCode": "ACADEMIC_ADMIN", "activeContextId": "ctx"})
    project_selection_batch_locked(db, sel_batch.id)
    db.commit()
    ids = {"term": term.id, "task": task.id, "classA1": a1.id, "classA2": a2.id, "classBSelector": b1.id}
    db.close()
    return ids


def test_autoexam_consumes_selection_roster_not_administrative_class(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/exam/batches", headers=admin,
                      json={"batchName": "跨班选修回归批次", "termId": str(ids["term"])}).json()["data"]["batchId"]
    cid = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=admin,
                      json={"teachingTaskId": str(ids["task"])}).json()["data"]["examCourseId"]
    confirmed = client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=admin, json={"action": "CONFIRM"})
    assert confirmed.status_code == 200, confirmed.text
    client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=admin,
              json={"examDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00",
                    "durationMinutes": 90})
    client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=admin)

    r = client.post(f"{BASE}/exam/batches/{bid}/auto-arrange", headers=admin)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["arrangedCourses"] == 1 and d["missedCourses"] == 0

    rooms = client.get(f"{BASE}/exam/courses/{cid}/rooms", headers=admin).json()["data"]["items"]
    assert len(rooms) == 1
    seats = client.get(f"{BASE}/exam/rooms/{rooms[0]['examRoomId']}/seats",
                       headers=admin).json()["data"]["items"]
    seated_students = {s["studentNo"] for s in seats}
    # 只有真正选课并锁定的 b1 应该被排进考场——不是挂靠行政班A的 2 名从未选课的学生
    assert seated_students == {"FR2501"}, (
        f"自动排考仍在按行政班猜考生，排进了 {seated_students}，应只有选课锁定的 FR2501")


def test_autoexam_reports_no_roster_when_snapshot_missing_students(client, db_mode):
    """选课批次没有任何学生选中这门课时，冻结快照为空——如实报 NO_ROSTER，不回退行政班。"""
    from app.db.session import get_sessionmaker
    from app.models import AaSelectionRecord

    ids = _seed(db_mode)
    db = get_sessionmaker()()
    db.query(AaSelectionRecord).filter(AaSelectionRecord.tenant_id == TID).delete()
    db.commit(); db.close()

    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/exam/batches", headers=admin,
                      json={"batchName": "空选课回归批次", "termId": str(ids["term"])}).json()["data"]["batchId"]
    cid = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=admin,
                      json={"teachingTaskId": str(ids["task"])}).json()["data"]["examCourseId"]
    confirmed = client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=admin, json={"action": "CONFIRM"})
    # 选课名单为空时，教学班当前正式名单也是空——学院确认阶段本身就该挡在这里，
    # 不应该出现"确认成功但自动排考时才发现没人"的情况。
    assert confirmed.status_code == 409, confirmed.text
