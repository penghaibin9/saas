"""教师范围精确化测试：有权限 / 无权限 / 跨租户 / 写操作范围 / mock-login 生产关闭。"""
from __future__ import annotations

from contextlib import contextmanager

MAIN = 1000000000000000001
DEMO = 1000000000000000003


def _token(user_id, real_name, role, user_type="TEACHER", tenant_id=MAIN, tid="demo",
           login_name=None, client_type="MP", active_context_id="ctx"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": user_id, "loginName": login_name or user_id,
        "realName": real_name, "userType": user_type,
        "tid": tid, "tenantId": str(tenant_id), "activeContextId": active_context_id,
        "currentRoleCode": role, "clientType": client_type})}


def _ensure_role_context(db, role_code, permission_codes):
    """Create the minimum real RBAC context needed by a db-* mobile token."""
    from sqlalchemy import select
    from app.models import Permission, Role, RolePermission

    role = db.scalar(select(Role).where(
        Role.tenant_id == MAIN, Role.role_code == role_code, Role.is_deleted.is_(False),
    ))
    if role is None:
        role = Role(tenant_id=MAIN, role_code=role_code, role_name=f"测试{role_code}",
                    role_type="SYSTEM", status="ACTIVE")
        db.add(role)
        db.flush()
    for code in permission_codes:
        permission = db.scalar(select(Permission).where(Permission.permission_code == code))
        if permission is None:
            permission = Permission(permission_code=code, permission_name=code, module_code="academic")
            db.add(permission)
            db.flush()
        linked = db.scalar(select(RolePermission).where(
            RolePermission.tenant_id == MAIN, RolePermission.role_id == role.id,
            RolePermission.permission_id == permission.id, RolePermission.is_deleted.is_(False),
        ))
        if linked is None:
            db.add(RolePermission(tenant_id=MAIN, role_id=role.id, permission_id=permission.id,
                                  status="ACTIVE"))
    db.flush()
    return role


def _seed_scope_case(_db_mode):
    """两个班：软件2301班（学生 甲一）/ 机电2301班（学生 乙二）。
    counselorA 只带软件2301班；mentorB 只指导 甲一（毕设 advisor_name=mentorB 本名）。"""
    from app.db.session import get_sessionmaker
    from app.models import (AcademicStudent, AcademicWarning, GraduationStudent,
                            InternshipRecord, SchoolClass, StudentProfile,
                            TeacherStudentScope, User, UserRole, WeeklyReport)
    db = get_sessionmaker()()
    try:
        counselor_role = _ensure_role_context(
            db, "COUNSELOR", {"academicAffairs.warning.view", "academicAffairs.warning.handle"},
        )
        counselor = User(tenant_id=MAIN, login_name="counselorA", real_name="辅导员A",
                         password_hash="test", user_type="TEACHER", status="ACTIVE")
        db.add(counselor)
        db.flush()
        db.add(UserRole(tenant_id=MAIN, user_id=counselor.id, role_id=counselor_role.id, status="ACTIVE"))
        class_a = SchoolClass(tenant_id=MAIN, major_id=1, class_name="软件2301班", grade="2023",
                              counselor_id=counselor.id, status="ACTIVE")
        class_b = SchoolClass(tenant_id=MAIN, major_id=1, class_name="机电2301班", grade="2023",
                              status="ACTIVE")
        db.add_all([class_a, class_b])
        db.flush()
        sa = StudentProfile(tenant_id=MAIN, student_no="SC0001", real_name="甲一", grade="2023",
                            class_id=class_a.id, current_stage="INTERNSHIP",
                            student_status="NORMAL", status="ACTIVE")
        sb = StudentProfile(tenant_id=MAIN, student_no="SC0002", real_name="乙二", grade="2023",
                            class_id=class_b.id, current_stage="ON_CAMPUS",
                            student_status="NORMAL", status="ACTIVE")
        db.add_all([sa, sb])
        db.flush()
        # 域记录（班级冗余）
        aa = AcademicStudent(tenant_id=MAIN, student_id=sa.id, name="甲一", student_no="SC0001", class_name="软件2301班",
                             gpa=2.0, academic_status="WARNING", warning_level="HIGH")
        ab = AcademicStudent(tenant_id=MAIN, student_id=sb.id, name="乙二", student_no="SC0002", class_name="机电2301班",
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
        return {"sa": sa.id, "sb": sb.id, "wa": wa.id, "wb": wb.id, "wr": wr.id,
                "counselor": counselor.id, "counselorContext": f"role:{counselor_role.id}"}
    finally:
        db.close()


def test_scoped_counselor_student_detail(client, db_mode):
    ids = _seed_scope_case(db_mode)
    h = _token("counselorA", "辅导员A", "COUNSELOR")
    ok = client.get(f"/api/v1/mobile/teacher/student/{ids['sa']}", headers=h).json()
    assert ok["code"] == 0 and ok["data"]["hasData"] is True  # 本班学生可看
    deny = client.get(f"/api/v1/mobile/teacher/student/{ids['sb']}", headers=h).json()
    assert deny["code"] == 403001  # 非本班学生 403


def test_teacher_without_scope_is_denied_by_default(client, db_mode):
    ids = _seed_scope_case(db_mode)
    h = _token("u-other-teacher", "无范围老师", "COUNSELOR")
    r = client.get(f"/api/v1/mobile/teacher/student/{ids['sb']}", headers=h).json()
    assert r["code"] == 403001  # 无范围行 → SCOPED 空范围（默认拒绝，不扩大到全租户）


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
                     headers=mentor,
                     json={"action": "APPROVE", "comment": "写得不错", "expectedVersion": 0}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"
    dup = client.post(f"/api/v1/mobile/teacher/internship/weekly/{ids['wr']}/review",
                      headers=mentor, json={"action": "APPROVE", "expectedVersion": 0}).json()
    assert dup["code"] == 409001


def test_mobile_warning_handle_scope(client, db_mode):
    ids = _seed_scope_case(db_mode)
    h = _token(f"db-{ids['counselor']}", "辅导员A", "COUNSELOR",
               login_name="counselorA", client_type="TEACHER_MINI",
               active_context_id=ids["counselorContext"])
    deny = client.post(f"/api/v1/mobile/teacher/academic/warning/{ids['wb']}/handle",
                       headers=h, json={"action": "CLOSE", "note": "已联系家长处理"}).json()
    assert deny["code"] == 403002  # 非本班预警不可处理（无数据范围）
    ok = client.post(f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/handle",
                     headers=h, json={"action": "CLOSE", "note": "已谈话并制定帮扶计划"}).json()
    assert ok["code"] == 0
    dup = client.post(f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/handle",
                      headers=h, json={"action": "CLOSE", "note": "再次关闭应该冲突"}).json()
    assert dup["code"] == 409001


def test_mobile_warning_escalate_is_idempotently_rejected_after_terminal_action(client, db_mode):
    ids = _seed_scope_case(db_mode)
    h = _token(f"db-{ids['counselor']}", "辅导员A", "COUNSELOR",
               login_name="counselorA", client_type="TEACHER_MINI",
               active_context_id=ids["counselorContext"])
    first = client.post(f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/handle", headers=h,
                        json={"action": "ESCALATE", "note": "已升级为高风险并移交后续跟进"}).json()
    duplicate = client.post(f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/handle", headers=h,
                            json={"action": "ESCALATE", "note": "重复点击不能再次升级写入"}).json()
    assert first["code"] == 0 and first["data"]["status"] == "ESCALATED"
    assert duplicate["code"] == 409001


def test_mobile_warning_pending_queue_uses_server_total_and_excludes_closed_rows(client, db_mode):
    """教师首页只能消费本范围内、服务端已筛好的开放预警汇总。"""
    ids = _seed_scope_case(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import AcademicWarning

    db = get_sessionmaker()()
    try:
        # Make the count larger than the first mobile page.  The latest OPEN row
        # also carries legacy machine enums to ensure the mobile presenter never
        # leaks them to a teacher-facing screen.
        own_warning = db.get(AcademicWarning, ids["wa"])
        assert own_warning is not None
        for index in range(25):
            db.add(AcademicWarning(
                tenant_id=MAIN,
                acad_student_id=own_warning.acad_student_id,
                warn_type="GPA",
                level="HIGH",
                reason=f"第 {index + 1} 条本班预警",
                status="ACTIVE" if index == 24 else "PENDING_HANDLE",
                record_status="ACTIVE",
            ))
        db.add(AcademicWarning(
            tenant_id=MAIN,
            acad_student_id=own_warning.acad_student_id,
            warn_type="GPA",
            level="LOW",
            reason="已关闭的本班预警不能重新混入待处理队列",
            status="CLOSED",
            record_status="ACTIVE",
        ))
        db.commit()
    finally:
        db.close()

    h = _token(f"db-{ids['counselor']}", "辅导员A", "COUNSELOR",
               login_name="counselorA", client_type="TEACHER_MINI",
               active_context_id=ids["counselorContext"])
    summary = client.get("/api/v1/mobile/teacher/academic/warnings/summary", headers=h).json()
    assert summary["code"] == 0
    assert summary["data"]["total"] == 26  # 本班 1 条初始预警 + 25 条开放预警
    assert summary["data"]["first"]["typeLabel"] == "学业预警"
    assert summary["data"]["first"]["statusLabel"] == "状态待确认"

    first_page = client.get(
        "/api/v1/mobile/teacher/academic/warnings?page=1&pageSize=20&pendingOnly=true",
        headers=h,
    ).json()
    assert first_page["code"] == 0
    assert first_page["data"]["total"] == 26
    assert len(first_page["data"]["list"]) == 20
    assert first_page["data"]["hasMore"] is True
    assert all(row["status"] != "CLOSED" for row in first_page["data"]["list"])

    second_page = client.get(
        "/api/v1/mobile/teacher/academic/warnings?page=2&pageSize=20&pendingOnly=true",
        headers=h,
    ).json()
    assert second_page["code"] == 0
    assert second_page["data"]["total"] == 26
    assert len(second_page["data"]["list"]) == 6
    assert second_page["data"]["hasMore"] is False
    assert client.get(
        "/api/v1/mobile/teacher/academic/warnings?pendingOnly=true&status=CLOSED",
        headers=h,
    ).json()["code"] != 0

    closed = client.post(
        f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/handle",
        headers=h,
        json={"action": "CLOSE", "note": "已完成本次帮扶并关闭预警"},
    ).json()
    assert closed["code"] == 0
    after_close = client.get("/api/v1/mobile/teacher/academic/warnings/summary", headers=h).json()
    assert after_close["code"] == 0 and after_close["data"]["total"] == 25


def test_mobile_warning_history_is_paged_and_scope_checked(client, db_mode):
    ids = _seed_scope_case(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import AcademicIntervention
    with get_sessionmaker()() as db:
        for index in range(23):
            db.add(AcademicIntervention(tenant_id=MAIN, warning_id=ids["wa"],
                                       way="TALK", content=f"跟进记录第{index}次", status="OPEN"))
        db.commit()
    h = _token(f"db-{ids['counselor']}", "辅导员A", "COUNSELOR",
               login_name="counselorA", client_type="TEACHER_MINI",
               active_context_id=ids["counselorContext"])
    url = f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/detail"
    first = client.get(url, headers=h).json()
    assert first["code"] == 0
    first = first["data"]
    assert len(first["interventions"]) == 20
    assert first["interventionTotal"] == 23 and first["interventionHasMore"] is True
    second = client.get(url, headers=h, params={"interventionPage": 2}).json()["data"]
    assert len(second["interventions"]) == 3 and second["interventionHasMore"] is False
    assert not ({row["id"] for row in first["interventions"]} & {row["id"] for row in second["interventions"]})
    denied = client.get(f"/api/v1/mobile/teacher/academic/warning/{ids['wb']}/detail",
                        headers=h, params={"interventionPage": 2}).json()
    assert denied["code"] == 403002
    oversized = client.get(url, headers=h, params={"interventionPageSize": 1000})
    assert oversized.status_code == 400
    assert oversized.json()["code"] != 0


def test_mobile_warning_followup_replay_and_receipt_share_business_transaction(client, db_mode):
    ids = _seed_scope_case(db_mode)
    from sqlalchemy import select, func
    from app.db.session import get_sessionmaker
    from app.models import AcademicIntervention
    h = _token(f"db-{ids['counselor']}", "辅导员A", "COUNSELOR",
               login_name="counselorA", client_type="TEACHER_MINI",
               active_context_id=ids["counselorContext"])
    key = "warning_followup_contract_001"
    url = f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/interventions"
    body = {"way": "TALK", "content": "已完成面谈并约定学习计划"}
    missing = client.post(url, headers=h, json=body).json()
    assert missing["code"] != 0
    write_headers = {**h, "Idempotency-Key": key}
    first = client.post(url, headers=write_headers, json=body).json()
    assert first["code"] == 0
    replay = client.post(url, headers=write_headers, json=body).json()
    assert replay["code"] == 0 and replay["data"] == first["data"]
    changed = client.post(url, headers=write_headers, json={**body, "content": "同一编号不能覆盖另一份跟进内容"}).json()
    assert changed["code"] == 409001
    receipt = client.get(f"/api/v1/mobile/teacher/academic/warnings/commands/{key}", headers=h).json()
    assert receipt["code"] == 0 and receipt["data"]["result"] == first["data"]
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(AcademicIntervention).where(
            AcademicIntervention.tenant_id == MAIN, AcademicIntervention.warning_id == ids["wa"])) == 1


def test_mobile_warning_read_only_assignee_cannot_write(client, db_mode):
    """A pending todo may make a warning readable, never writable without warning.handle."""
    ids = _seed_scope_case(db_mode)
    from sqlalchemy import func, select
    from app.db.session import get_sessionmaker
    from app.models import (AcademicIntervention, AcademicWarning, AffairsAuditTrail, UnifiedTodo,
                            User, UserRole)

    db = get_sessionmaker()()
    try:
        viewer_role = _ensure_role_context(db, "ACADEMIC_TEACHER", {"academicAffairs.process.view"})
        viewer = User(tenant_id=MAIN, login_name="academic-readonly", real_name="只读任课老师",
                      password_hash="test", user_type="TEACHER", status="ACTIVE")
        db.add(viewer)
        db.flush()
        db.add(UserRole(tenant_id=MAIN, user_id=viewer.id, role_id=viewer_role.id, status="ACTIVE"))
        db.add(UnifiedTodo(
            tenant_id=MAIN, source_module="academic-affairs", source_biz_type="ACAD_WARNING",
            source_biz_id=ids["wa"], todo_type="ACAD_WARNING_HANDLE", assignee_id=viewer.id,
            title="只读教师可查看的预警", status="PENDING",
        ))
        db.commit()
        before_interventions = int(db.scalar(select(func.count()).select_from(AcademicIntervention).where(
            AcademicIntervention.tenant_id == MAIN, AcademicIntervention.warning_id == ids["wa"],
        )) or 0)
        before_audits = int(db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == MAIN, AffairsAuditTrail.biz_type == "ACAD_WARNING",
            AffairsAuditTrail.biz_id == ids["wa"],
        )) or 0)
        viewer_id, viewer_context = viewer.id, f"role:{viewer_role.id}"
    finally:
        db.close()

    h = _token(f"db-{viewer_id}", "只读任课老师", "ACADEMIC_TEACHER",
               login_name="academic-readonly", client_type="TEACHER_MINI",
               active_context_id=viewer_context)
    listed = client.get("/api/v1/mobile/teacher/academic/warnings", headers=h).json()
    assert listed["code"] == 0
    assert str(ids["wa"]) in {str(item.get("warningId") or item.get("id")) for item in listed["data"]["list"]}
    detail = client.get(f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/detail", headers=h).json()
    assert detail["code"] == 0
    assert detail["data"]["allowedActions"] == []
    assert detail["data"]["warning"]["studentName"] == "甲一"
    assert detail["data"]["warning"]["className"] == "软件2301班"
    assert detail["data"]["warning"]["typeLabel"] == "学业预警"
    assert detail["data"]["warning"]["statusLabel"] == "待处理"

    follow = client.post(f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/interventions", headers=h,
                         json={"way": "TALK", "content": "只读账号不能写入跟进记录"}).json()
    close = client.post(f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/handle", headers=h,
                        json={"action": "CLOSE", "note": "只读账号不能关闭该预警"}).json()
    escalate = client.post(f"/api/v1/mobile/teacher/academic/warning/{ids['wa']}/handle", headers=h,
                           json={"action": "ESCALATE", "note": "只读账号不能升级该预警"}).json()
    assert follow["code"] == close["code"] == escalate["code"] == 403001

    db = get_sessionmaker()()
    try:
        warning = db.get(AcademicWarning, ids["wa"])
        assert warning.status == "PENDING_HANDLE"
        assert int(db.scalar(select(func.count()).select_from(AcademicIntervention).where(
            AcademicIntervention.tenant_id == MAIN, AcademicIntervention.warning_id == ids["wa"],
        )) or 0) == before_interventions
        assert int(db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == MAIN, AffairsAuditTrail.biz_type == "ACAD_WARNING",
            AffairsAuditTrail.biz_id == ids["wa"],
        )) or 0) == before_audits
    finally:
        db.close()


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
    # 本用例只验证租户绑定，使用租户管理员避免普通教师的 DEFAULT_DENY
    # 数据范围把“未越权但无可见记录”误判为切租户。
    h = _token("u-tenant-admin", "租户管理员", "SCHOOL_ADMIN")
    h["X-Tenant"] = "demo-school"
    r = client.get("/api/v1/mobile/teacher/risk-students", headers=h).json()
    assert r["code"] == 0
    names = [x["name"] for x in r["data"]["list"]]
    assert "甲一" in names or "乙二" in names  # 看到的仍是主租户数据（头没有生效）


def test_teacher_name_ambiguity_lookup_failure_fails_closed(monkeypatch):
    from app.services import _mobile_teacher_service_impl as impl

    @contextmanager
    def broken_session():
        raise RuntimeError("identity store unavailable")
        yield

    monkeypatch.setattr(impl, "_session", broken_session)
    assert impl._real_name_is_ambiguous("同名老师") is True
