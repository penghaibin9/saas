"""教务统计第三轮续工（2026-07-16）：08/09/14 号卡（选课/考务/教学资源统计）+ 07 号卡
（调停课统计）在「教务总览」的真实计数卡回归测试。

背景：`docs/03-业务模块设计/教务中心/施工包/教务统计-生产级施工包.md`（2026-07-14 起草）把这 4 项
标为 UNKNOWN/blocked 占位，因起草时底层业务表尚未建成；后续续工轮次已建成
`t_aa_schedule_change`/`t_aa_selection_*`/`t_aa_exam_*`/`t_aa_classroom*` 真实表+完整读写接口
（详见 `academic_affairs_schedule_change_service.py`/`_selection_service.py`/`_exam_service.py`/
`_resource_service.py`），本文件验证 `academic_affairs_stats_service.py` 新增的跨批次聚合口径。

MySQL-only：依赖 db_mode 夹具（TEST_DATABASE_URL）。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_r3(db_mode):
    """种 07/08/09/14 号卡所需数据：1 学期 + 2 学院 + 1 专业 + 1 班级 + 1 学生 +
    2 条调停课 + 1 选课批次(2 供给行:低人数/满额各一+1 选课记录) +
    1 考试批次(2 课程:已确认/待确认各一+1 缺考记录) + 2 教室(可用/停用各一)+1 待审预约。"""
    from app.db.session import get_sessionmaker
    from app.models import (AaClassroom, AaClassroomBooking, AaCourse, AaExamBatch, AaExamCourse,
                            AaExamIncident, AaScheduleChange, AaSelectionBatch, AaSelectionCourse,
                            AaSelectionRecord, AaTerm, College, Major, SchoolClass, StudentProfile,
                            TeacherStudentScope)
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2025-2026", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term)
    db.flush()
    soft = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    other = College(tenant_id=TID, college_name="机械学院", status="ACTIVE")
    db.add_all([soft, other])
    db.flush()
    major = Major(tenant_id=TID, college_id=soft.id, major_name="软件技术", status="ACTIVE")
    db.add(major)
    db.flush()
    cls = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", status="ACTIVE")
    db.add(cls)
    db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="2025101", real_name="周十一",
                        college_id=soft.id, major_id=major.id, class_id=cls.id,
                        student_status="NORMAL", status="ACTIVE")
    db.add(s1)
    db.flush()

    # 07 调停课：1 ADJUST + 1 STOP，均挂本班（软件学院）
    db.add_all([
        AaScheduleChange(tenant_id=TID, term_id=term.id, class_id=cls.id, class_name=cls.class_name,
                         change_type="ADJUST", reason="教师因公出差需调课", status="APPLIED"),
        AaScheduleChange(tenant_id=TID, term_id=term.id, class_id=cls.id, class_name=cls.class_name,
                         change_type="STOP", reason="临时停课通知", status="SUBMITTED"),
    ])

    # 08 选课：1 批次 + 2 供给行（低人数 + 满额）+ 1 选课记录
    course = AaCourse(tenant_id=TID, course_code="SC001", course_name="选课测试课程",
                      category="MAJOR_CORE", nature="ELECTIVE", credit=2,
                      owner_college_id=soft.id, status="ENABLED")
    db.add(course)
    db.flush()
    sel_batch = AaSelectionBatch(tenant_id=TID, term_id=term.id, batch_name="2025秋选课批次", status="OPEN")
    db.add(sel_batch)
    db.flush()
    sc_low = AaSelectionCourse(tenant_id=TID, batch_id=sel_batch.id, course_id=course.id,
                               course_name=course.course_name, capacity=50, min_capacity=10,
                               selected_count=2, status="OPEN")
    sc_full = AaSelectionCourse(tenant_id=TID, batch_id=sel_batch.id, course_id=course.id,
                                teaching_task_id=999, course_name=course.course_name,
                                capacity=1, min_capacity=1, selected_count=1, status="OPEN")
    db.add_all([sc_low, sc_full])
    db.flush()
    db.add(AaSelectionRecord(tenant_id=TID, batch_id=sel_batch.id, selection_course_id=sc_low.id,
                             course_id=course.id, student_id=s1.id, student_no=s1.student_no,
                             student_name=s1.real_name, status="SELECTED"))

    # 09 考务：1 批次 + 2 课程（已确认 + 待确认）+ 1 缺考记录
    exam_batch = AaExamBatch(tenant_id=TID, term_id=term.id, batch_name="2025秋期末考试", status="ARRANGED")
    db.add(exam_batch)
    db.flush()
    ec1 = AaExamCourse(tenant_id=TID, batch_id=exam_batch.id, course_name="高数",
                       college_id=soft.id, status="CONFIRMED")
    ec2 = AaExamCourse(tenant_id=TID, batch_id=exam_batch.id, course_name="英语",
                       college_id=soft.id, status="PENDING_CONFIRM")
    db.add_all([ec1, ec2])
    db.flush()
    db.add(AaExamIncident(tenant_id=TID, exam_course_id=ec1.id, student_id=s1.id,
                          student_no=s1.student_no, student_name=s1.real_name,
                          incident_type="ABSENT", status="ACTIVE"))

    # 14 教学资源：2 间教室（可用/停用）+ 1 条待审预约
    room1 = AaClassroom(tenant_id=TID, building_code="A", building_name="A栋", room_code="101",
                        capacity=60, room_type="LECTURE", status="AVAILABLE")
    room2 = AaClassroom(tenant_id=TID, building_code="A", building_name="A栋", room_code="102",
                        capacity=30, room_type="COMPUTER", status="DISABLED")
    db.add_all([room1, room2])
    db.flush()
    db.add(AaClassroomBooking(tenant_id=TID, classroom_id=room1.id, classroom_text="A栋101",
                              booking_date="2026-09-01", slot_no=1, purpose="社团活动",
                              applicant_name="王老师", status="PENDING"))

    # college_admin01 → 软件学院 数据范围（跨范围测试用，同 test_aa_stats.py 既有惯例）
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01", role_code="COLLEGE_ADMIN",
                              scope_type="COLLEGE", ref_value="软件学院", status="ACTIVE"))
    db.commit()
    ids = {"term": term.id, "soft": soft.id, "other": other.id, "class": cls.id, "student": s1.id}
    db.close()
    return ids


def test_overview_real_values_ok(client, db_mode):
    """教务总览 07/08/09/14 卡片：种子数据下应返回真实非零聚合，而非 MODULE_NOT_ENABLED。"""
    _seed_r3(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/overview", headers=hdr).json()
    assert r["code"] == 0
    by_key = {i["key"]: i for i in r["data"]["indicators"]}
    for k in ("scheduleChange", "courseSelection", "exam", "resource"):
        assert by_key[k]["status"] == "OK"
    assert by_key["scheduleChange"]["value"] == 2
    assert any(g["key"] == "ADJUST" and g["count"] == 1 for g in by_key["scheduleChange"]["groups"])
    assert by_key["courseSelection"]["numerator"] == 3 and by_key["courseSelection"]["denominator"] == 51
    assert by_key["exam"]["numerator"] == 1 and by_key["exam"]["denominator"] == 2
    assert by_key["resource"]["value"] == 2


def test_course_selection_stats_and_detail_ok(client, db_mode):
    _seed_r3(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/course-selection", headers=hdr).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["totalCapacity"] == 51 and d["totalSelected"] == 3
    assert d["lowEnrollCount"] == 1 and d["fullCount"] == 1
    assert d["recordCount"] == 1
    assert any(g["key"] == "OPEN" for g in d["byBatchStatus"])
    det = client.get(f"{BASE}/stats/course-selection/detail", headers=hdr).json()
    assert det["code"] == 0 and det["data"]["total"] == 1
    assert det["data"]["items"][0]["courseName"] == "选课测试课程"
    assert det["data"]["items"][0]["selectedCount"] == 2


def test_exam_stats_and_detail_ok(client, db_mode):
    _seed_r3(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/exam", headers=hdr).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["courseTotal"] == 2 and d["confirmedCount"] == 1 and d["confirmRate"] == 50.0
    assert d["absentCount"] == 1 and d["violationCount"] == 0
    det = client.get(f"{BASE}/stats/exam/detail", headers=hdr).json()
    assert det["code"] == 0 and det["data"]["total"] == 1
    row = det["data"]["items"][0]
    assert row["studentName"] == "周十一"
    assert row["studentNo"] != "2025101"          # 学号脱敏
    assert row["incidentType"] == "ABSENT"


def test_resource_stats_and_detail_ok(client, db_mode):
    _seed_r3(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/resource", headers=hdr).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["classroomTotal"] == 2 and d["bookingTotal"] == 1
    assert any(g["key"] == "AVAILABLE" and g["count"] == 1 for g in d["byStatus"])
    assert any(g["key"] == "DISABLED" and g["count"] == 1 for g in d["byStatus"])
    det = client.get(f"{BASE}/stats/resource/detail", headers=hdr).json()
    assert det["code"] == 0 and det["data"]["total"] == 1
    assert det["data"]["items"][0]["classroomText"] == "A栋101"
    assert det["data"]["items"][0]["status"] == "PENDING"


def test_course_selection_college_scope(client, db_mode):
    """08 号卡跨范围测试：学院教务员只能查本院，越院 403。"""
    ids = _seed_r3(db_mode)
    hdr = _hdr(client, "college_admin01")
    ok = client.get(f"{BASE}/stats/course-selection", headers=hdr, params={"collegeId": ids["soft"]}).json()
    assert ok["code"] == 0 and ok["data"]["totalSelected"] == 3
    denied = client.get(f"{BASE}/stats/course-selection", headers=hdr, params={"collegeId": ids["other"]})
    assert denied.status_code == 403 or denied.json().get("code") == "NO_DATA_SCOPE"


def test_exam_college_scope(client, db_mode):
    """09 号卡跨范围测试：越院 403（`AaExamCourse.college_id` 冗余列收敛）。"""
    ids = _seed_r3(db_mode)
    hdr = _hdr(client, "college_admin01")
    ok = client.get(f"{BASE}/stats/exam", headers=hdr, params={"collegeId": ids["soft"]}).json()
    assert ok["code"] == 0 and ok["data"]["courseTotal"] == 2
    denied = client.get(f"{BASE}/stats/exam", headers=hdr, params={"collegeId": ids["other"]})
    assert denied.status_code == 403 or denied.json().get("code") == "NO_DATA_SCOPE"


def test_r3_student_forbidden(client, db_mode):
    _seed_r3(db_mode)
    hdr = _hdr(client, "student01")
    for path in ("/stats/course-selection", "/stats/course-selection/detail",
                "/stats/exam", "/stats/exam/detail", "/stats/resource", "/stats/resource/detail"):
        assert client.get(f"{BASE}{path}", headers=hdr).status_code == 403


def test_r3_export_domains_ok(client, db_mode):
    """15 号卡导出报表：新增 3 项维度均产出真实 xlsx（PK 魔数）。"""
    _seed_r3(db_mode)
    hdr = _hdr(client, "school_admin01")
    for domain in ("courseSelection", "exam", "resource"):
        r = client.post(f"{BASE}/stats/export", headers=hdr,
                        json={"domain": domain, "purpose": "自动化回归导出测试"})
        assert r.status_code == 200, f"domain={domain} 导出失败：{r.status_code} {r.text[:200]}"
        assert r.content[:2] == b"PK", f"domain={domain} 未产出合法 xlsx"
