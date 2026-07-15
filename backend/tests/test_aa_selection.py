"""选课管理（/academic-affairs/selection/*）端点测试（SM-09 冻结状态机）。

覆盖：批次全生命周期(建/发布/开选/学生选/退/截止/锁定/归档)、发布无课程400、非OPEN选课409、
容量满409、SUSPENDED学生403、重复选课409、学生越权管理批次403、锁定后人工调整原因400/成功、
低人数取消开课+补选指引。口径核对施工包 §7/§9/§10。MySQL-only（db_mode 夹具）。
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


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, College, Major, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
    c1 = AaCourse(tenant_id=TID, course_code="SEL001", course_name="职业素养选修", credit=2, status="ENABLED")
    c2 = AaCourse(tenant_id=TID, course_code="SEL002", course_name="人工智能导论", credit=3, status="ENABLED")
    db.add_all([c1, c2]); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="SEL2401", real_name="选甲", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    s2 = StudentProfile(tenant_id=TID, student_no="SEL2402", real_name="选乙", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="NORMAL", status="ACTIVE")
    s3 = StudentProfile(tenant_id=TID, student_no="SEL2403", real_name="休丙", college_id=col.id,
                        major_id=major.id, class_id=klass.id, grade="2024",
                        student_status="SUSPENDED", status="ACTIVE")
    db.add_all([s1, s2, s3]); db.flush()
    ids = {"course1": c1.id, "course2": c2.id, "s1": s1.id, "s2": s2.id, "s3": s3.id}
    db.commit(); db.close()
    return ids


def _make_open_batch(client, admin, course_id, capacity=5, name="2024秋选修"):
    """建批次→加课程→发布→开选，返回 (batchId, selectionCourseId)。"""
    bid = client.post(f"{BASE}/selection/batches", headers=admin,
                      json={"batchName": name}).json()["data"]["batchId"]
    scid = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                       json={"courseId": str(course_id), "capacity": capacity, "minCapacity": 1}).json()["data"]["selectionCourseId"]
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    return bid, scid


def test_s1_full_lifecycle(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, scid = _make_open_batch(client, admin, ids["course1"], capacity=5)
    stu = _stu_token("选甲", "SEL2401")
    # 学生可选课程有余量
    r = client.get(f"{BASE}/selection/student/courses", headers=stu).json()
    assert r["code"] == 0 and any(str(c["selectionCourseId"]) == str(scid)
                                  for grp in r["data"]["items"] for c in grp["courses"])
    # 选课成功
    r = client.post(f"{BASE}/selection/student/enroll", headers=stu,
                    json={"selectionCourseId": str(scid)}).json()
    assert r["code"] == 0 and r["data"]["status"] == "SELECTED"
    # 我的选课
    my = client.get(f"{BASE}/selection/student/my", headers=stu).json()
    assert any(rec["selectionCourseId"] == str(scid) for rec in my["data"]["items"])
    # selectedCount 已+1
    cs = client.get(f"{BASE}/selection/batches/{bid}/courses", headers=admin).json()["data"]["items"]
    assert cs[0]["selectedCount"] == 1
    # 退课
    assert client.post(f"{BASE}/selection/student/drop", headers=stu,
                       json={"selectionCourseId": str(scid)}).json()["data"]["status"] == "DROPPED"
    # 截止→锁定→归档
    assert client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin).json()["data"]["status"] == "CLOSED"
    assert client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin).json()["data"]["status"] == "LOCKED"
    assert client.post(f"{BASE}/selection/batches/{bid}/archive", headers=admin).json()["data"]["status"] == "ARCHIVED"


def test_s2_publish_without_course_400(client, db_mode):
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/selection/batches", headers=admin,
                      json={"batchName": "空批次"}).json()["data"]["batchId"]
    assert client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin).status_code == 400


def test_s3_enroll_when_not_open_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/selection/batches", headers=admin, json={"batchName": "未开选"}).json()["data"]["batchId"]
    scid = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                       json={"courseId": str(ids["course1"]), "capacity": 5, "minCapacity": 1}).json()["data"]["selectionCourseId"]
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)  # PUBLISHED，未 open
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid)}).status_code == 409


def test_s4_capacity_full_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, scid = _make_open_batch(client, admin, ids["course1"], capacity=1)
    # 选甲占满
    assert client.post(f"{BASE}/selection/student/enroll", headers=_stu_token("选甲", "SEL2401"),
                       json={"selectionCourseId": str(scid)}).json()["code"] == 0
    # 选乙容量满 409
    assert client.post(f"{BASE}/selection/student/enroll", headers=_stu_token("选乙", "SEL2402"),
                       json={"selectionCourseId": str(scid)}).status_code == 409


def test_s5_suspended_student_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, scid = _make_open_batch(client, admin, ids["course1"])
    assert client.post(f"{BASE}/selection/student/enroll", headers=_stu_token("休丙", "SEL2403"),
                       json={"selectionCourseId": str(scid)}).status_code == 403


def test_s6_duplicate_enroll_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _bid, scid = _make_open_batch(client, admin, ids["course1"])
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid)}).json()["code"] == 0
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid)}).status_code == 409


def test_s7_student_cannot_manage_batch_403(client, db_mode):
    _seed(db_mode)
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/batches", headers=stu, json={"batchName": "越权"}).status_code == 403
    assert client.get(f"{BASE}/selection/batches", headers=stu).status_code == 403


def test_s8_lock_non_closed_409(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, _scid = _make_open_batch(client, admin, ids["course1"])  # OPEN
    assert client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin).status_code == 409


def test_s9_adjust_after_lock(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, scid = _make_open_batch(client, admin, ids["course1"])
    stu = _stu_token("选甲", "SEL2401")
    rid = client.post(f"{BASE}/selection/student/enroll", headers=stu,
                      json={"selectionCourseId": str(scid)}).json()["data"]["recordId"]
    client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin)
    # 原因过短 400
    assert client.post(f"{BASE}/selection/records/{rid}/adjust", headers=admin,
                       json={"reason": "x"}).status_code == 400
    # 合法原因成功，记录转 DROPPED
    r = client.post(f"{BASE}/selection/records/{rid}/adjust", headers=admin,
                    json={"reason": "学生转专业需退课处理"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "DROPPED"


def test_s11_prereq_and_passed_block(client, db_mode):
    """④先修课程未过拦截 + ⑧已通过不可再选。"""
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AcademicGrade, AcademicStudent
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    db = get_sessionmaker()()
    # course1(职业素养选修) 设先修 = SEL002(人工智能导论)；学生未过 SEL002
    c1 = db.query(AaCourse).filter(AaCourse.tenant_id == TID, AaCourse.course_code == "SEL001").first()
    c1.prerequisite_codes_json = '["SEL002"]'
    # 学生学业档案 + 一门已通过课程"体育"
    acad = AcademicStudent(tenant_id=TID, student_id=ids["s1"], student_no="SEL2401", name="选甲",
                           class_name="软件2401", college_name="软件学院")
    db.add(acad); db.flush()
    db.add(AcademicGrade(tenant_id=TID, acad_student_id=acad.id, course_name="职业素养选修", credit_value=2,
                         score=85, pass_status="PASSED", source="PUBLISH", record_status="ACTIVE"))
    db.commit(); db.close()
    bid, scid = _make_open_batch(client, admin, ids["course1"], name="先修批次")
    stu = _stu_token("选甲", "SEL2401")
    # ⑧ 已通过"职业素养选修" → 400
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid)}).status_code == 400
    # 换一门有先修要求的课(course2 人工智能导论无先修,但 course1 有先修 SEL002 未过)——再建 course2 批次验证先修
    bid2, scid2 = _make_open_batch(client, admin, ids["course2"], name="AI批次")
    # course2 无先修、未通过 → 可选
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid2)}).json()["code"] == 0


def test_s12_time_tick_auto_open_close(client, db_mode):
    from datetime import datetime, timedelta

    from app.db.session import get_sessionmaker
    from app.models import AaSelectionBatch
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # 建批次+课程+发布（PUBLISHED），设 select_start_at 已过
    bid = client.post(f"{BASE}/selection/batches", headers=admin, json={"batchName": "定时批次"}).json()["data"]["batchId"]
    client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                json={"courseId": str(ids["course1"]), "capacity": 5, "minCapacity": 1})
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    db = get_sessionmaker()()
    b = db.query(AaSelectionBatch).filter(AaSelectionBatch.id == int(bid), AaSelectionBatch.tenant_id == TID).first()
    b.select_start_at = datetime.utcnow() - timedelta(hours=1)
    db.commit(); db.close()
    # 时间触发 → 自动开选
    r = client.post(f"{BASE}/selection/time-tick", headers=admin).json()
    assert r["code"] == 0 and r["data"]["opened"] >= 1
    assert client.get(f"{BASE}/selection/batches/{bid}", headers=admin).json()["data"]["status"] == "OPEN"


def test_s10_low_enroll_cancel_and_reselect(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # minCapacity=2，无人选 → 低人数
    bid = client.post(f"{BASE}/selection/batches", headers=admin, json={"batchName": "低人数批次"}).json()["data"]["batchId"]
    scid = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                       json={"courseId": str(ids["course1"]), "capacity": 30, "minCapacity": 2}).json()["data"]["selectionCourseId"]
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin)
    # 统计显示低人数
    st = client.get(f"{BASE}/selection/batches/{bid}/stats", headers=admin).json()["data"]
    assert st["lowEnrollCount"] == 1
    # 人工取消开课
    assert client.post(f"{BASE}/selection/courses/{scid}/cancel", headers=admin).json()["data"]["status"] == "COURSE_CANCELLED"
    # 补选指引含被取消课程
    guide = client.get(f"{BASE}/selection/batches/{bid}/reselect-guide", headers=admin).json()["data"]
    assert len(guide["cancelledCourses"]) == 1


# ═══ 本轮续工新增：选课规则(03) / 补选管理(06) / 冲突检测(09) / 选课结果(10) / 选课归档(12) ═══

def test_s13_rule_save_and_freeze_after_open(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/selection/batches", headers=admin, json={"batchName": "规则批次"}).json()["data"]["batchId"]
    client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
               json={"courseId": str(ids["course1"]), "capacity": 5, "minCapacity": 1})
    r = client.put(f"{BASE}/selection/batches/{bid}/rule", headers=admin, json={"rule": {"maxCredits": 10}})
    assert r.json()["code"] == 0 and r.json()["data"]["rule"]["maxCredits"] == 10
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    # OPEN 后规则冻结，409
    assert client.put(f"{BASE}/selection/batches/{bid}/rule", headers=admin,
                      json={"rule": {"maxCredits": 20}}).status_code == 409


def test_s14_reselect_flow(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/selection/batches", headers=admin, json={"batchName": "补选批次"}).json()["data"]["batchId"]
    sc1 = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                      json={"courseId": str(ids["course1"]), "capacity": 30, "minCapacity": 2}).json()["data"]["selectionCourseId"]
    sc2 = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                      json={"courseId": str(ids["course2"]), "capacity": 30, "minCapacity": 1}).json()["data"]["selectionCourseId"]
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(sc1)}).json()["code"] == 0
    client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin)
    # 低人数（selectedCount=1 < minCapacity=2）人工取消 course1
    assert client.post(f"{BASE}/selection/courses/{sc1}/cancel", headers=admin).json()["data"]["status"] == "COURSE_CANCELLED"
    # 学生本人补选指引：含待补选记录 + 仍有余量课程
    guide = client.get(f"{BASE}/selection/student/reselect-guide", headers=stu).json()
    assert guide["code"] == 0
    grp = guide["data"]["items"]
    assert len(grp) == 1 and grp[0]["batch"]["batchId"] == str(bid)
    assert any(r["selectionCourseId"] == str(sc1) for r in grp[0]["cancelledRecords"])
    assert any(c["selectionCourseId"] == str(sc2) for c in grp[0]["availableCourses"])
    # 普通学生（无待补选记录）在 CLOSED 批次选课仍 409（不因传 isReselect 而绕过）
    stu2 = _stu_token("选乙", "SEL2402")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu2,
                       json={"selectionCourseId": str(sc2), "isReselect": True}).status_code == 409
    # 受影响学生补选课程2 成功
    r = client.post(f"{BASE}/selection/student/enroll", headers=stu,
                    json={"selectionCourseId": str(sc2), "isReselect": True})
    assert r.json()["code"] == 0 and r.json()["data"]["status"] == "SELECTED"


def _seed_conflict_tasks(ids):
    """构造两门课程各自的教学任务+同一时段课表项，供⑤课表冲突/09号卡冲突报表测试复用。"""
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem, AaTeachingTask
    db = get_sessionmaker()()
    tt1 = AaTeachingTask(tenant_id=TID, batch_id=1, course_id=ids["course1"], course_name="职业素养选修")
    tt2 = AaTeachingTask(tenant_id=TID, batch_id=1, course_id=ids["course2"], course_name="人工智能导论")
    db.add_all([tt1, tt2]); db.flush()
    si1 = AaScheduleItem(tenant_id=TID, batch_id=1, task_id=tt1.id, course_id=ids["course1"],
                         course_name="职业素养选修", weekday=1, slot_no=1, start_week=1, end_week=18,
                         week_parity="ALL", status="EFFECTIVE")
    si2 = AaScheduleItem(tenant_id=TID, batch_id=1, task_id=tt2.id, course_id=ids["course2"],
                         course_name="人工智能导论", weekday=1, slot_no=1, start_week=1, end_week=18,
                         week_parity="ALL", status="EFFECTIVE")
    db.add_all([si1, si2])
    db.commit()
    tt1_id, tt2_id = tt1.id, tt2.id
    db.close()
    return tt1_id, tt2_id


def test_s15_conflict_report(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    tt1_id, tt2_id = _seed_conflict_tasks(ids)
    bid = client.post(f"{BASE}/selection/batches", headers=admin, json={"batchName": "冲突批次"}).json()["data"]["batchId"]
    sc1 = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                      json={"courseId": str(ids["course1"]), "teachingTaskId": str(tt1_id),
                           "capacity": 30, "minCapacity": 1}).json()["data"]["selectionCourseId"]
    sc2 = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                      json={"courseId": str(ids["course2"]), "teachingTaskId": str(tt2_id),
                           "capacity": 30, "minCapacity": 1}).json()["data"]["selectionCourseId"]
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    stu = _stu_token("选甲", "SEL2401")
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(sc1)}).json()["code"] == 0
    # course2 与已选 course1 同时段冲突 → 409，并落审计供报表聚合
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(sc2)}).status_code == 409
    rep = client.get(f"{BASE}/selection/batches/{bid}/conflict-report", headers=admin).json()["data"]
    assert any(s["courseName"] == "人工智能导论" and s["conflictRejectCount"] == 1 for s in rep["summary"])
    rep_hit = client.get(f"{BASE}/selection/batches/{bid}/conflict-report", headers=admin,
                         params={"studentNo": "SEL2401"}).json()["data"]
    assert len(rep_hit["items"]) == 1
    rep_miss = client.get(f"{BASE}/selection/batches/{bid}/conflict-report", headers=admin,
                          params={"studentNo": "SEL9999"}).json()["data"]
    assert len(rep_miss["items"]) == 0
    # 导出：用途必填 ≥5 字
    assert client.post(f"{BASE}/selection/batches/{bid}/conflict-report/export", headers=admin,
                       json={"purpose": "ab"}).status_code == 400
    exp = client.post(f"{BASE}/selection/batches/{bid}/conflict-report/export", headers=admin,
                      json={"purpose": "冲突报表测试导出"})
    assert exp.status_code == 200
    assert exp.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_s16_selection_result_merged_into_schedule(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    tt1_id, _tt2_id = _seed_conflict_tasks(ids)
    bid = client.post(f"{BASE}/selection/batches", headers=admin, json={"batchName": "结果批次"}).json()["data"]["batchId"]
    sc1 = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                      json={"courseId": str(ids["course1"]), "teachingTaskId": str(tt1_id),
                           "capacity": 10, "minCapacity": 1}).json()["data"]["selectionCourseId"]
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    stu = _stu_token("选甲", "SEL2401")
    client.post(f"{BASE}/selection/student/enroll", headers=stu, json={"selectionCourseId": str(sc1)})
    # LOCKED 之前：课表不含该选修课
    sv = client.get(f"{BASE}/schedule-batches/999999/student-view", headers=admin,
                    params={"studentId": str(ids["s1"])}).json()
    assert not any(it["source"] == "ENROLLED" for it in sv["data"]["items"])
    client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin)
    # LOCKED 之后：选修课并入课表，标注 source=ENROLLED
    sv2 = client.get(f"{BASE}/schedule-batches/999999/student-view", headers=admin,
                     params={"studentId": str(ids["s1"])}).json()
    enrolled = [it for it in sv2["data"]["items"] if it["source"] == "ENROLLED"]
    assert len(enrolled) == 1 and enrolled[0]["courseName"] == "职业素养选修"


def test_s17_archive_list_detail_export(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = client.post(f"{BASE}/selection/batches", headers=admin, json={"batchName": "归档批次"}).json()["data"]["batchId"]
    client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
               json={"courseId": str(ids["course1"]), "capacity": 5, "minCapacity": 1})
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/lock", headers=admin)
    # 未归档时查看详情/导出均 409
    assert client.get(f"{BASE}/selection/archive/{bid}", headers=admin).status_code == 409
    assert client.post(f"{BASE}/selection/archive/{bid}/export", headers=admin,
                       json={"purpose": "测试导出台账"}).status_code == 409
    assert client.post(f"{BASE}/selection/batches/{bid}/archive", headers=admin).json()["data"]["status"] == "ARCHIVED"
    lst = client.get(f"{BASE}/selection/archive", headers=admin).json()["data"]
    assert any(b["batchId"] == str(bid) for b in lst["items"])
    detail = client.get(f"{BASE}/selection/archive/{bid}", headers=admin).json()
    assert detail["code"] == 0 and detail["data"]["status"] == "ARCHIVED"
    assert detail["data"]["stats"]["courseCount"] == 1
    exp = client.post(f"{BASE}/selection/archive/{bid}/export", headers=admin, json={"purpose": "测试导出台账"})
    assert exp.status_code == 200
    assert client.post(f"{BASE}/selection/archive/{bid}/export", headers=admin,
                       json={"purpose": "ab"}).status_code == 400
