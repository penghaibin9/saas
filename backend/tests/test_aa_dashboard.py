"""13B 教务看板（aa-dashboard）· 首页汇总 + 提醒聚合。

发现背景：`test_academic.py::test_credits_and_dashboard_audit` 打的是旧前缀
`/api/v1/academic/dashboard`（app/api/v1/academic.py，遗留模块，对应旧前端
AdminAcademicLayout/AcademicDashboardView 已不在任何路由里，orphaned），并不是
navPlan.js 里真实在用的教务看板（/academic-affairs/dashboard）。真实看板此前只有
一条 403 权限检查（test_aa_term.py），没有验证过真实返回数据，本文件补上。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaRegistration, AaTerm, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    t = AaTerm(tenant_id=TID, year_code="2026-2027", term_no=1, status="PUBLISHED", is_current=True)
    db.add(t); db.flush()
    c = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2601", grade="2026", status="ACTIVE")
    db.add(c); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="DB001", real_name="看板甲", class_id=c.id,
                       current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    db.add(AaRegistration(tenant_id=TID, batch_id=1, student_id=s.id, status="REGISTERED"))
    db.flush()
    db.commit()
    tid = t.id
    db.close()
    return tid


def test_dashboard_summary_reflects_real_data(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/dashboard", headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["currentTerm"] is not None
    cards = {c["key"]: c["value"] for c in data["summaryCards"]}
    assert cards["studentTotal"] >= 1
    assert cards["registered"] >= 1
    assert isinstance(data["moduleCards"], list) and len(data["moduleCards"]) > 0


def test_dashboard_reminders_aggregates_six_panels(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/dashboard/reminders", headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    for key in ("gradeProgress", "examReminders", "statusChangeReminders",
               "warningReminders", "graduationWarnings", "todos", "generatedAt"):
        assert key in data, f"缺少面板：{key}"


def test_dashboard_student_forbidden_403(client, db_mode):
    from app.core.security import create_access_token
    stu_hdr = {"Authorization": "Bearer " + create_access_token({
        "userId": "u-db001", "realName": "看板甲", "studentNo": "DB001", "userType": "STUDENT",
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx", "currentRoleCode": "STUDENT",
        "clientType": "MP"})}
    assert client.get(f"{BASE}/dashboard", headers=stu_hdr).status_code == 403


# ═══════════ 第三轮续工五卡：今日教学运行/今日课程/调停课提醒/教学资源占用/教务数据趋势 ═══════════

def test_dashboard_reminders_five_new_panels_present_and_graceful_empty(client, db_mode):
    """无已发布课表批次/无当前学期教学周配置时：五卡必须出现在响应里，且用 note 说明原因，
    不得报错、也不得编造数据（今日课程/调停课提醒必须是空列表而不是假数据）。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/dashboard/reminders", headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    for key in ("todayTeaching", "todayCourses", "scheduleChangeReminders", "resourceOccupancy", "dataTrends"):
        assert key in data, f"缺少面板：{key}"
    assert data["todayCourses"]["items"] == []
    assert data["todayTeaching"]["note"], "无教学周上下文时今日教学运行必须给出空态说明"
    assert data["scheduleChangeReminders"]["items"] == []
    assert isinstance(data["dataTrends"]["series"], list) and len(data["dataTrends"]["series"]) == 4
    assert isinstance(data["dataTrends"]["days"], list) and len(data["dataTrends"]["days"]) == 14


def _seed_today_panels(db_mode):
    """种一条今天必命中的课表项 + 教室占用 + 在途调停课 + 已提交成绩任务 + 新增预警，
    验证五卡是真实聚合既有业务表，不是空壳/mock。作息节次开成 00:00~23:59，
    使课次运行状态在任意执行时刻都稳定落在 IN_PROGRESS，避免按墙钟时间产生偶发 flaky。"""
    from datetime import datetime, timedelta
    from app.db.session import get_sessionmaker
    from app.models import (AaClassroom, AaClassroomBooking, AaGradeTask, AaScheduleBatch,
                            AaScheduleChange, AaScheduleItem, AaTerm, AaTimeSlot, AcademicWarning)
    db = get_sessionmaker()()
    local_today = (datetime.utcnow() + timedelta(hours=8))
    weekday = local_today.isoweekday()
    term_start = datetime(local_today.year, local_today.month, local_today.day)
    t = AaTerm(tenant_id=TID, year_code="2026-2027", term_no=1, status="PUBLISHED", is_current=True,
              start_date=term_start, teaching_weeks=18)
    db.add(t); db.flush()
    batch = AaScheduleBatch(tenant_id=TID, term_id=t.id, batch_name="看板联调批次", status="PUBLISHED",
                            publish_at=datetime.utcnow())
    db.add(batch); db.flush()
    db.add(AaTimeSlot(tenant_id=TID, slot_no=1, slot_name="第1节", start_time="00:00", end_time="23:59"))
    db.add(AaScheduleItem(tenant_id=TID, batch_id=batch.id, course_name="看板联调课", class_name="软件2601",
                          class_id=9001, teacher_key="T-DB01", teacher_name="看板教师", weekday=weekday,
                          slot_no=1, start_week=1, end_week=18, week_parity="ALL",
                          classroom_text="看板楼A101", status="EFFECTIVE"))
    # 教室字典登记的是「看板楼A101」（与上面课表项 classroom_text 精确同名，验证占用率分子只认字典匹配项）；
    # 另建一条课表项用不在字典里的自由文本教室，验证占用率不把它算进分子、只计入 unmatchedCount（红线用例）。
    db.add(AaScheduleItem(tenant_id=TID, batch_id=batch.id, course_name="看板联调课·未登记教室", class_name="软件2601",
                          class_id=9001, teacher_key="T-DB01", teacher_name="看板教师", weekday=weekday,
                          slot_no=1, start_week=1, end_week=18, week_parity="ALL",
                          classroom_text="看板楼未登记教室X9", status="EFFECTIVE"))
    room_a101 = AaClassroom(tenant_id=TID, building_code="DB", building_name="看板楼", room_code="A101",
                            capacity=50, room_type="LECTURE", status="AVAILABLE")
    room_b102 = AaClassroom(tenant_id=TID, building_code="DB", building_name="看板楼", room_code="B102",
                            capacity=50, room_type="LECTURE", status="AVAILABLE")
    db.add(room_a101); db.add(room_b102); db.flush()
    db.add(AaClassroomBooking(tenant_id=TID, classroom_id=room_b102.id, classroom_text="看板楼B102",
                              booking_date=local_today.date().isoformat(), slot_no=2, purpose="看板联调预约",
                              applicant_key="T-DB01", applicant_name="看板教师", status="APPROVED"))
    db.add(AaScheduleChange(tenant_id=TID, term_id=t.id, change_type="ADJUST", course_name="看板联调课",
                            class_name="软件2601", teacher_key="T-DB01", teacher_name="看板教师",
                            status="SUBMITTED", current_node="COLLEGE_REVIEW", reason="看板联调用例"))
    db.add(AaGradeTask(tenant_id=TID, term_id=t.id, course_name="看板联调课", class_id=9001,
                       teacher_key="T-DB01", status="SUBMITTED", submitted_at=datetime.utcnow()))
    db.add(AcademicWarning(tenant_id=TID, acad_student_id=1, warn_type="MULTI_FAIL", level="HIGH",
                           reason="看板联调预警", status="PENDING_HANDLE"))
    db.commit()
    db.close()


def test_dashboard_today_panels_reflect_seeded_schedule(client, db_mode):
    """正常路径：今天有已发布课表项/教室占用/在途调停课/已提交成绩/新增预警时，五卡必须反映真实数值。"""
    _seed_today_panels(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/dashboard/reminders", headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    tt = data["todayTeaching"]
    assert tt["totalToday"] >= 2  # 两条今日课表项（含一条未登记字典教室）
    assert tt["teacherCount"] >= 1
    assert tt["roomCount"] >= 2
    assert tt["inProgress"] >= 2  # 作息 00:00~23:59，任何执行时刻都应判定进行中
    assert "examCount" in tt and "adjustedCount" in tt

    tc = data["todayCourses"]
    assert tc["count"] >= 2
    hit = next((i for i in tc["items"] if i["courseName"] == "看板联调课"), None)
    assert hit is not None, "今日课程未反映已发布课表项"
    assert hit["runStatus"] == "IN_PROGRESS"
    assert hit["className"] == "软件2601" and hit["teacherName"] == "看板教师"
    assert "changed" in hit  # 调停课标记字段存在（本条未经调停课改写，应为 False）
    assert hit["changed"] is False

    scr = data["scheduleChangeReminders"]
    assert scr["count"] >= 1
    assert any(i["courseName"] == "看板联调课" and i["changeTypeLabel"] == "调课" for i in scr["items"])

    ro = data["resourceOccupancy"]
    assert ro["totalRooms"] == 2  # 教室字典仅登记 A101/B102 两间
    assert ro["occupiedToday"] >= 2, "课表占用教室(A101) + 已批教室预约(B102) 应各计一间"
    assert ro["occupiedToday"] <= ro["totalRooms"], "占用率分子不得超过字典教室总数（红线：不得伪造占用率）"
    assert ro["unmatchedCount"] >= 1, "未登记字典的排课教室文本应计入 unmatchedCount，不得悄悄丢弃或误计入占用率"

    dt = data["dataTrends"]
    by_key = {s["key"]: s for s in dt["series"]}
    assert by_key["scheduleChange"]["points"][-1]["value"] >= 1
    assert by_key["gradeSubmit"]["points"][-1]["value"] >= 1
    assert by_key["warning"]["points"][-1]["value"] >= 1


def test_dashboard_reminders_student_forbidden_403(client, db_mode):
    """越权路径：学生不进 PC 管理端教务看板，/dashboard/reminders（五卡同一端点）对学生必须 403。"""
    from app.core.security import create_access_token
    stu_hdr = {"Authorization": "Bearer " + create_access_token({
        "userId": "u-db001", "realName": "看板甲", "studentNo": "DB001", "userType": "STUDENT",
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx", "currentRoleCode": "STUDENT",
        "clientType": "MP"})}
    assert client.get(f"{BASE}/dashboard/reminders", headers=stu_hdr).status_code == 403
