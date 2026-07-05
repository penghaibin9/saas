"""教师范围精确化测试：有权限 / 无权限 / 跨租户 / 写操作范围 / mock-login 生产关闭。"""
from __future__ import annotations

MAIN = 1000000000000000001
DEMO = 1000000000000000003


def _token(user_id, real_name, role, user_type="TEACHER", tenant_id=MAIN, tid="demo"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": user_id, "realName": real_name, "userType": user_type,
        "tid": tid, "tenantId": str(tenant_id), "activeContextId": "ctx",
        "currentRoleCode": role, "clientType": "MP"})}


def _seed_scope_case(_db_mode):
    """两个班：软件2301班（学生 甲一）/ 机电2301班（学生 乙二）。
    counselorA 只带软件2301班；mentorB 只指导 甲一（毕设 advisor_name=mentorB 本名）。"""
    from app.db.session import get_sessionmaker
    from app.models import (AcademicStudent, AcademicWarning, GraduationStudent,
                            InternshipRecord, StudentProfile, TeacherStudentScope, WeeklyReport)
    db = get_sessionmaker()()
    try:
        sa = StudentProfile(tenant_id=MAIN, student_no="SC0001", real_name="甲一", grade="2023",
                            current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        sb = StudentProfile(tenant_id=MAIN, student_no="SC0002", real_name="乙二", grade="2023",
                            current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE")
        db.add_all([sa, sb])
        db.flush()
        # 域记录（班级冗余）
        aa = AcademicStudent(tenant_id=MAIN, name="甲一", student_no="SC0001", class_name="软件2301班",
                             gpa=2.0, academic_status="WARNING", warning_level="HIGH")
        ab = AcademicStudent(tenant_id=MAIN, name="乙二", student_no="SC0002", class_name="机电2301班",
                             gpa=2.0, academic_status="WARNING", warning_level="HIGH")
        db.add_all([aa, ab])
        db.flush()
        wa = AcademicWarning(tenant_id=MAIN, acad_student_id=aa.id, warn_type="GPA", level="HIGH",
                             reason="甲一预警", status="PENDING_HANDLE", record_status="ACTIVE")
        wb = AcademicWarning(tenant_id=MAIN, acad_student_id=ab.id, warn_type="GPA", level="HIGH",
                             reason="乙二预警", status="PENDING_HANDLE", record_status="ACTIVE")
        db.add_all([wa, wb])
        rec = InternshipRecord(tenant_id=MAIN, student_id=sa.id, enterprise_name="范围测试企业",
                               position_name="实习生", advisor_name="孟导师", status="ONBOARD",
                               risk_level="LOW")
        db.add(rec)
        db.flush()
        wr = WeeklyReport(tenant_id=MAIN, internship_id=rec.id, week_number=1,
                          work_content="范围测试周报内容" * 3, status="PENDING_REVIEW")
        db.add(wr)
        db.add(GraduationStudent(tenant_id=MAIN, name="甲一", student_no="SC0001",
                                 class_name="软件2301班", topic_title="范围测试课题",
                                 advisor_name="孟导师", stage="GUIDING"))
        # 范围行
        db.add(TeacherStudentScope(tenant_id=MAIN, teacher_key="counselorA", teacher_name="辅导员A",
                                   role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2301班",
                                   status="ACTIVE"))
        db.add(TeacherStudentScope(tenant_id=MAIN, teacher_key="mentorB", teacher_name="孟导师",
                                   role_code=None, scope_type="ADVISOR", ref_value="孟导师",
                                   status="ACTIVE"))
        db.commit()
        db.refresh(wa); db.refresh(wb); db.refresh(wr)
        return {"sa": sa.id, "sb": sb.id, "wa": wa.id, "wb": wb.id, "wr": wr.id}
    finally:
        db.close()


def test_scoped_counselor_student_detail(client, db_mode):
    ids = _seed_scope_case(db_mode)
    h = _token("counselorA", "辅导员A", "COUNSELOR")
    ok = client.get(f"/api/v1/mobile/teacher/student/{ids['sa']}", headers=h).json()
    assert ok["code"] == 0 and ok["data"]["hasData"] is True  # 本班学生可看
    deny = client.get(f"/api/v1/mobile/teacher/student/{ids['sb']}", headers=h).json()
    assert deny["code"] == 403001  # 非本班学生 403


def test_fallback_teacher_still_tenant_visible(client, db_mode):
    ids = _seed_scope_case(db_mode)
    h = _token("u-other-teacher", "无范围老师", "COUNSELOR")
    r = client.get(f"/api/v1/mobile/teacher/student/{ids['sb']}", headers=h).json()
    assert r["code"] == 0  # 无范围行 → TENANT_FALLBACK（试点兜底）


def test_scoped_risk_students_filtered(client, db_mode):
    _seed_scope_case(db_mode)
    h = _token("counselorA", "辅导员A", "COUNSELOR")
    r = client.get("/api/v1/mobile/teacher/risk-students", headers=h).json()
    assert r["code"] == 0
    names = [x["name"] for x in r["data"]["list"]]
    assert "乙二" not in names  # 非本班风险学生不可见
    assert r["data"]["scopeMode"] == "SCOPED"


def test_scoped_cross_tenant_404(client, db_mode):
    ids = _seed_scope_case(db_mode)
    h = _token("counselorA", "辅导员A", "COUNSELOR", tenant_id=DEMO, tid="demo-school")
    r = client.get(f"/api/v1/mobile/teacher/student/{ids['sa']}", headers=h).json()
    assert r["code"] == 404001  # 跨租户按不存在处理


def test_mobile_weekly_review_scope_and_conflict(client, db_mode):
    ids = _seed_scope_case(db_mode)
    mentor = _token("mentorB", "孟导师", "INTERN_MENTOR")
    outsider = _token("counselorC", "外班辅导员", "COUNSELOR")
    # 外班 SCOPED 教师批阅 → 403
    from app.db.session import get_sessionmaker
    from app.models import TeacherStudentScope
    db = get_sessionmaker()()
    db.add(TeacherStudentScope(tenant_id=MAIN, teacher_key="counselorC", teacher_name="外班辅导员",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="机电2301班",
                               status="ACTIVE"))
    db.commit(); db.close()
    deny = client.post(f"/api/v1/mobile/teacher/internship/weekly/{ids['wr']}/review",
                       headers=outsider, json={"action": "APPROVE"}).json()
    assert deny["code"] == 403001
    # 指导老师批阅 → 200；重复批阅 → 409
    ok = client.post(f"/api/v1/mobile/teacher/internship/weekly/{ids['wr']}/review",
                     headers=mentor, json={"action": "APPROVE", "comment": "写得不错"}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"
    dup = client.post(f"/api/v1/mobile/teacher/internship/weekly/{ids['wr']}/review",
                      headers=mentor, json={"action": "APPROVE"}).json()
    assert dup["code"] == 409001


def test_mobile_warning_handle_scope(client, db_mode):
    ids = _seed_scope_case(db_mode)
    h = _token("counselorA", "辅导员A", "COUNSELOR")
    deny = client.post(f"/api/v1/mobile/teacher/academic/warning/{ids['wb']}/handle",
                       headers=h, json={"action": "CLOSE", "note": "已联系家长处理"}).json()
    assert deny["code"] == 403001  # 非本班预警不可处理
    ok = client.post(f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/handle",
                     headers=h, json={"action": "CLOSE", "note": "已谈话并制定帮扶计划"}).json()
    assert ok["code"] == 0
    dup = client.post(f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/handle",
                      headers=h, json={"action": "CLOSE", "note": "再次关闭应该冲突"}).json()
    assert dup["code"] == 409001


def test_mobile_write_requires_teacher(client, db_mode):
    ids = _seed_scope_case(db_mode)
    stu = _token("u-stu", "甲一", "STUDENT", user_type="STUDENT")
    r = client.post(f"/api/v1/mobile/teacher/internship/weekly/{ids['wr']}/review",
                    headers=stu, json={"action": "APPROVE"}).json()
    assert r["code"] == 403001


def test_mock_login_disabled_in_prod(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MOCK_LOGIN_ENABLED", "false")
    r = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "student01", "password": "demo"})
    assert r.status_code == 403
    body = r.json()
    assert body["code"] == 403001 and "accessToken" not in (body.get("data") or {})
    monkeypatch.setattr(settings, "MOCK_LOGIN_ENABLED", "")
    ok = client.post("/api/v1/auth/mock-login",
                     json={"loginName": "student01", "password": "demo"}).json()
    assert ok["code"] == 0 and ok["data"]["accessToken"]


def test_mock_token_carries_tenant(client):
    """mock 令牌必须带 tenantId：X-Tenant 头不能把已登录用户切到其它租户。"""
    import jwt as _jwt
    from app.core.config import settings
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "counselor01", "password": "demo"}).json()["data"]
    claims = _jwt.decode(data["accessToken"], settings.jwt_secret,
                         algorithms=[settings.jwt_algorithm])
    assert claims.get("tenantId") == "1000000000000000001"
    # student01 令牌带学号（学生本人解析不再仅靠姓名）
    d2 = client.post("/api/v1/auth/mock-login",
                     json={"loginName": "student01", "password": "demo"}).json()["data"]
    c2 = _jwt.decode(d2["accessToken"], settings.jwt_secret,
                     algorithms=[settings.jwt_algorithm])
    assert c2.get("studentNo") == "2023100001"


def test_header_cannot_switch_tenant_with_token(client, db_mode):
    """带主租户令牌 + X-Tenant: demo-school 头 → 数据仍是主租户（令牌优先）。"""
    _seed_scope_case(db_mode)
    h = _token("u-teacher", "王辅导", "COUNSELOR")
    h["X-Tenant"] = "demo-school"
    r = client.get("/api/v1/mobile/teacher/risk-students", headers=h).json()
    assert r["code"] == 0
    names = [x["name"] for x in r["data"]["list"]]
    assert "甲一" in names or "乙二" in names  # 看到的仍是主租户数据（头没有生效）
