"""第四阶段：最终集成分支真实 MySQL + FastAPI 最小业务冒烟。

不调用 /auth/mock-login，不替换 service，不伪造接口结果；身份仅通过正式 JWT 编码函数生成，
所有读取均进入真实 FastAPI 路由、权限依赖、SQLAlchemy 和 MySQL 测试库。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.route_introspection import iter_effective_api_routes
from app.core.security import create_access_token
from app.db.session import get_sessionmaker
from app.main import app
from app.models import AaTerm


TID = 1000000000000000001
ROOT = Path(__file__).resolve().parents[2]


def _headers(role: str, *, user_type: str = "TEACHER", login_name: str = "stage4-user",
             real_name: str = "第四阶段验收用户", student_no: str | None = None) -> dict:
    claims = {
        "userId": f"stage4-{role.lower()}",
        "loginName": login_name,
        "realName": real_name,
        "userType": user_type,
        "currentRoleCode": role,
        "clientType": "PC" if user_type != "STUDENT" else "MP",
        "tid": str(TID),
        "tenantId": str(TID),
        "activeContextId": f"stage4-{role.lower()}-context",
    }
    if student_no:
        claims["studentNo"] = student_no
    return {"Authorization": "Bearer " + create_access_token(claims)}


def _assert_ok(response, label: str) -> dict:
    assert response.status_code == 200, f"{label}: HTTP {response.status_code} {response.text}"
    payload = response.json()
    assert payload.get("code") == 0, f"{label}: {payload}"
    return payload.get("data") or {}


def _assert_forbidden(response, label: str) -> None:
    assert response.status_code == 403, f"{label}: HTTP {response.status_code} {response.text}"
    assert response.json().get("code") in {403001, 403002}, f"{label}: {response.json()}"


def _ensure_term() -> int:
    db = get_sessionmaker()()
    try:
        term = AaTerm(
            tenant_id=TID,
            year_code="2026-2027",
            term_no=1,
            term_name="第四阶段验收学期",
            start_date=datetime(2026, 9, 1),
            end_date=datetime(2027, 1, 20),
            teaching_weeks=20,
            exam_week_start=18,
            is_current=True,
            status="PUBLISHED",
        )
        db.add(term)
        db.commit()
        db.refresh(term)
        return int(term.id)
    finally:
        db.close()


def test_stage4_route_model_and_cross_module_contracts():
    # FastAPI 0.139+ 将 include_router 保存为嵌套节点；必须遍历最终有效路由上下文。
    # 本闸门只裁决教务路由唯一性；毕设、实习、学工由各自生产闸门负责。
    academic_prefixes = (
        "/api/v1/academic-affairs",
        "/api/v1/academic/",
        "/api/v1/portal/academic/",
        "/api/v1/mobile/academic/",
        "/api/v1/mobile/teacher/academic/",
        "/api/v1/teacher/academic/",
    )
    seen: set[tuple[str, str]] = set()
    paths: set[str] = set()
    for route in iter_effective_api_routes(app.routes):
        paths.add(route.path)
        if not any(route.path == prefix.rstrip("/") or route.path.startswith(prefix) for prefix in academic_prefixes):
            continue
        for method in (route.methods or set()) - {"HEAD", "OPTIONS"}:
            key = (method, route.path)
            assert key not in seen, f"重复教务路由: {key}"
            seen.add(key)

    required = {
        "/api/v1/academic-affairs/dashboard",
        "/api/v1/academic-affairs/terms",
        "/api/v1/academic-affairs/teaching-task-batches",
        "/api/v1/academic-affairs/teaching-tasks",
        "/api/v1/academic-affairs/teaching-classes",
        "/api/v1/academic-affairs/schedule-batches",
        "/api/v1/academic-affairs/exam/batches",
        "/api/v1/academic-affairs/grade-tasks",
        "/api/v1/academic-affairs/makeup/batches",
        "/api/v1/academic-affairs/archive/precheck",
        "/api/v1/portal/academic/schedule",
        "/api/v1/portal/academic/transcript",
        "/api/v1/portal/academic/exam",
        "/api/v1/portal/academic/makeup",
        "/api/v1/mobile/academic/my",
        "/api/v1/mobile/academic/exam-v2/my",
        "/api/v1/mobile/teacher/academic/tasks",
        "/api/v1/mobile/teacher/academic/schedule/mine",
    }
    assert required <= paths, f"缺少路由: {sorted(required - paths)}"
    for prefix in ("/api/v1/graduation", "/api/v1/internship", "/api/v1/academic-affairs"):
        assert any(path.startswith(prefix) for path in paths), f"缺少跨模块入口: {prefix}"
    assert any("affairs" in path and path.startswith("/api/v1/") for path in paths), "缺少学工/事务入口"

    # SQLAlchemy 注册必须包含教务 V2 核心表，不允许只注册 Router 而漏模型。
    from app.models.base import Base
    for table in (
        "t_aa_term",
        "t_aa_teaching_class",
        "t_aa_teaching_class_roster_version",
        "t_aa_effective_grade_policy_snapshot",
    ):
        assert table in Base.metadata.tables, f"模型未注册: {table}"

    # 公共菜单与三大既有模块入口必须保留；未知前端 URL 必须有显式兜底。
    admin_router = (ROOT / "frontend/src/router/index.js").read_text(encoding="utf-8")
    admin_main = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")
    student_router = (ROOT / "student-portal/src/router/index.js").read_text(encoding="utf-8")
    admin_menu = (ROOT / "frontend/src/config/adminMenu.js").read_text(encoding="utf-8")
    for token in ("academicAffairsRoutes", "internshipRoutes", "graduationRoutes", "studentAffairsRoutes"):
        assert token in admin_router
    for token in ("NAV_PLAN", "academic-affairs", "internship", "graduation", "student-affairs"):
        assert token in admin_menu
    assert "unknown-route-fallback" in admin_main
    assert "/:pathMatch(.*)*" in admin_main
    assert "/:pathMatch(.*)*" in student_router


def test_stage4_real_mysql_admin_teacher_student_smoke(db_mode):
    term_id = _ensure_term()
    admin = _headers("ACADEMIC_ADMIN", login_name="academic-admin-stage4")
    teacher = _headers("ACADEMIC_TEACHER", login_name="T-STAGE4", real_name="第四阶段任课教师")
    student = _headers(
        "STUDENT", user_type="STUDENT", login_name="2023115001",
        real_name="赵一凡", student_no="2023115001",
    )

    with TestClient(app) as client:
        # 教务管理员：真实读取九个核心入口。
        for path, label in (
            ("/api/v1/academic-affairs/dashboard", "教务工作台"),
            ("/api/v1/academic-affairs/terms", "学期读取"),
            ("/api/v1/academic-affairs/teaching-task-batches", "教学任务读取"),
            ("/api/v1/academic-affairs/teaching-classes", "教学班与名单读取"),
            ("/api/v1/academic-affairs/schedule-batches", "排课入口"),
            ("/api/v1/academic-affairs/exam/batches", "考务入口"),
            ("/api/v1/academic-affairs/grade-tasks", "成绩管理入口"),
            ("/api/v1/academic-affairs/makeup/batches", "补考重修入口"),
            (f"/api/v1/academic-affairs/archive/precheck?termId={term_id}", "归档预检入口"),
        ):
            _assert_ok(client.get(path, headers=admin), label)

        # 任课教师：本人任务、课表、成绩录入队列可读；学校级发布动作必须拒绝。
        _assert_ok(client.get("/api/v1/academic-affairs/teaching-tasks?mine=true", headers=teacher), "教师本人教学任务")
        _assert_ok(client.get("/api/v1/mobile/teacher/academic/schedule/mine", headers=teacher), "教师本人课表")
        _assert_ok(client.get("/api/v1/academic-affairs/grade-tasks", headers=teacher), "教师成绩录入入口")
        _assert_forbidden(
            client.post(f"/api/v1/academic-affairs/terms/{term_id}/publish", headers=teacher),
            "教师不得发布学期",
        )

        # 学生 PC：课表、成绩、考试、补考均走真实门户接口。
        for path, label in (
            ("/api/v1/portal/academic/schedule", "学生PC课表"),
            ("/api/v1/portal/academic/transcript", "学生PC成绩"),
            ("/api/v1/portal/academic/exam", "学生PC考试"),
            ("/api/v1/portal/academic/makeup", "学生PC补考"),
            ("/api/v1/mobile/academic/my", "学生小程序成绩概览"),
            ("/api/v1/mobile/academic/exam-v2/my", "学生小程序考试"),
        ):
            _assert_ok(client.get(path, headers=student), label)

        # 学生不能进入教师或学校管理接口；未知后端路由明确 404，不产生 500。
        _assert_forbidden(client.get("/api/v1/academic-affairs/dashboard", headers=student), "学生不得进入教务管理")
        _assert_forbidden(client.get("/api/v1/mobile/teacher/academic/tasks", headers=student), "学生不得进入教师接口")
        unknown = client.get("/api/v1/__stage4_unknown_route__", headers=admin)
        assert unknown.status_code == 404


def test_stage4_warning_reminder_persists_real_message_type(db_mode):
    """接口报告已通知时，学生与辅导员提醒必须真实按 ACAD_WARNING_REMIND 落库。"""
    from sqlalchemy import select
    from app.models import (
        AcademicGrade,
        AcademicStudent,
        AcademicWarning,
        SchoolClass,
        StudentProfile,
        UnifiedMessage,
    )

    db = get_sessionmaker()()
    try:
        school_class = SchoolClass(
            tenant_id=TID,
            major_id=1,
            class_name="第四阶段预警验收班",
            grade="2026",
            status="ACTIVE",
            counselor_id=98533,
        )
        db.add(school_class)
        db.flush()
        student = StudentProfile(
            tenant_id=TID,
            student_no="STAGE4-WARNING-001",
            real_name="第四阶段预警学生",
            class_id=school_class.id,
            current_stage="ON_CAMPUS",
            student_status="REGISTERED",
            status="ACTIVE",
        )
        db.add(student)
        db.flush()
        academic_student = AcademicStudent(
            tenant_id=TID,
            student_id=student.id,
            student_no=student.student_no,
            name=student.real_name,
            class_name=school_class.class_name,
        )
        db.add(academic_student)
        db.flush()
        for course_name in ("第四阶段高等数学", "第四阶段大学英语"):
            db.add(AcademicGrade(
                tenant_id=TID,
                acad_student_id=academic_student.id,
                course_name=course_name,
                term="2026-2027-1",
                nature="REQUIRED",
                credit_value=4,
                score=45,
                pass_status="FAILED",
                exam_type="FINAL",
                record_status="ACTIVE",
            ))
        db.commit()
        student_id = int(student.id)
        academic_student_id = int(academic_student.id)
    finally:
        db.close()

    admin = _headers("ACADEMIC_ADMIN", login_name="academic-warning-stage4")
    with TestClient(app) as client:
        scan = _assert_ok(
            client.post("/api/v1/academic-affairs/warnings/scan", headers=admin),
            "预警扫描",
        )
        assert int(scan.get("created") or 0) >= 1

        db = get_sessionmaker()()
        try:
            warning = db.scalar(select(AcademicWarning).where(
                AcademicWarning.tenant_id == TID,
                AcademicWarning.acad_student_id == academic_student_id,
                AcademicWarning.source_code == "EXAM_FAIL",
                AcademicWarning.is_deleted.is_(False),
            ))
            assert warning is not None
            warning_id = int(warning.id)
        finally:
            db.close()

        reminded = _assert_ok(
            client.post(f"/api/v1/academic-affairs/warnings/{warning_id}/remind", headers=admin),
            "预警提醒",
        )
        assert reminded["remindCount"] == 1
        assert reminded["notified"] == 2

    db = get_sessionmaker()()
    try:
        rows = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == TID,
            UnifiedMessage.source_module == "academic-affairs",
            UnifiedMessage.source_biz_id == warning_id,
            UnifiedMessage.message_type == "ACAD_WARNING_REMIND",
            UnifiedMessage.is_deleted.is_(False),
        )).all()
        assert {int(row.receiver_id) for row in rows} == {student_id, 98533}
        assert all("提醒" in row.title for row in rows)
    finally:
        db.close()
