"""第四阶段：最终集成分支真实 MySQL + FastAPI 最小业务冒烟。

不调用 /auth/mock-login，不替换 service，不伪造接口结果；身份仅通过正式 JWT 编码函数生成，
所有读取均进入真实 FastAPI 路由、权限依赖、SQLAlchemy 和 MySQL 测试库。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

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
    # FastAPI method + path 必须唯一；同时确认四个业务中心和两类移动端入口真实挂载。
    seen: set[tuple[str, str]] = set()
    paths: set[str] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        paths.add(route.path)
        for method in (route.methods or set()) - {"HEAD", "OPTIONS"}:
            key = (method, route.path)
            assert key not in seen, f"重复路由: {key}"
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
    for token in ("academicAffairs", "internship", "graduation", "studentAffairs"):
        assert token.lower() in admin_menu.lower()
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
