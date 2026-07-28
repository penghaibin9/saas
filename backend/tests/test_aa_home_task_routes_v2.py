"""V2 R6 四端首页任务化与学生PC独立路由合同。"""
from pathlib import Path


def test_student_pc_todo_route_resolves_exact_academic_workspaces():
    from app.student_portal.services.home_service import _todo_route

    assert _todo_route(
        source_module="academic-affairs",
        source_biz_type="AA_GRADE_RECHECK",
        todo_type="GRADE_RECHECK_RETURNED",
    ) == "/academic/recheck"
    assert _todo_route(
        source_module="academic-affairs",
        source_biz_type="AA_REGISTRATION",
        todo_type="REGISTRATION_PENDING",
    ) == "/academic/registration"
    assert _todo_route(
        source_module="academic-affairs",
        source_biz_type="AA_WARNING",
        todo_type="WARNING_FOLLOW",
    ) == "/academic/warning"
    assert _todo_route(
        source_module="academic-affairs",
        source_biz_type="AA_UNKNOWN",
        todo_type="UNKNOWN",
    ) == "/academic"
    assert _todo_route(source_module="internship") == "/internship"


def test_student_pc_has_task_home_and_independent_academic_routes():
    root = Path(__file__).resolve().parents[2]
    shared_router = (root / "student-portal/src/router/index.js").read_text(encoding="utf-8")
    academic_routes = (root / "student-portal/src/router/academicRoutes.js").read_text(encoding="utf-8")
    main = (root / "student-portal/src/main.js").read_text(encoding="utf-8")
    home = (root / "student-portal/src/views/academic/StudentAcademicHomeView.vue").read_text(encoding="utf-8")
    wrapper = (root / "student-portal/src/views/academic/AcademicSectionRouteView.vue").read_text(encoding="utf-8")

    assert "StudentAcademicHomeView.vue" in academic_routes
    for route in (
        "registration", "selection", "evaluation", "recheck", "status", "exam", "makeup",
        "attendance", "calendar", "clearance", "credits", "warning", "textbook",
        "level-exam", "major-split", "recognition", "graduation",
    ):
        assert f"'{route}'" in academic_routes
    assert "installAcademicRoutes(router)" in main
    assert "./router/academicRoutes" in main
    assert "StudentAcademicHomeView.vue" not in shared_router
    assert "Promise.allSettled" in home
    assert "当前需要我处理" in home
    assert "academicTab" in wrapper
    assert "AcademicView" in wrapper
    assert ":deep(.sp-tabs) { display: none; }" in wrapper


def test_student_pc_home_prefers_exact_todo_route():
    root = Path(__file__).resolve().parents[2]
    home = (root / "student-portal/src/views/home/HomeView.vue").read_text(encoding="utf-8")

    assert "t.route || t.link || t.module" in home
    assert "topAlert.value?.route" in home
    assert "function goTarget" in home


def test_teacher_and_student_wechat_academic_homes_are_task_oriented():
    root = Path(__file__).resolve().parents[2]
    teacher = (root / "miniapp/src/pages/teacher/academic-affairs/index.vue").read_text(encoding="utf-8")
    student = (root / "miniapp/src/pages/student/academic-affairs/index.vue").read_text(encoding="utf-8")

    assert "taskTarget" in teacher
    assert "?id=${encodeURIComponent(id)}" in teacher
    assert "点击直达第一条具体任务" in teacher
    assert "taskCues" in student
    assert "当前需要我处理" in student
    for route in (
        "/pages/student/academic-affairs/registration",
        "/pages/student/academic-affairs/evaluation",
        "/pages/student/academic-affairs/warning",
        "/pages/student/academic-affairs/exam",
        "/pages/student/academic-affairs/makeup",
    ):
        assert route in student


def test_teacher_wechat_pages_consume_workbench_task_ids():
    root = Path(__file__).resolve().parents[2]
    pages = {
        "academic_task": root / "miniapp/src/pages/teacher/academic-task/index.vue",
        "schedule_review": root / "miniapp/src/pages/teacher/academic-affairs/schedule-change-review.vue",
        "defer": root / "miniapp/src/pages/teacher/exam-defer/index.vue",
        "warning": root / "miniapp/src/pages/teacher/academic-warning/index.vue",
        "grade": root / "miniapp/src/pages/teacher/academic-affairs/grade-entry.vue",
    }
    sources = {name: path.read_text(encoding="utf-8") for name, path in pages.items()}

    assert "options.id || options.taskId" in sources["academic_task"]
    assert "options.id || options.changeId" in sources["schedule_review"]
    assert "options.id || options.deferId" in sources["defer"]
    assert "options.id || options.warningId" in sources["warning"]
    assert "options.id || options.taskId" in sources["grade"]
    for name in ("academic_task", "schedule_review", "defer", "warning"):
        source = sources[name]
        assert "focusTarget" in source
        assert "is-target" in source
        assert "从工作台直达" in source
        assert "不存在、已处理或不在" in source


def test_admin_pc_keeps_real_todo_workbench_and_drill_routes():
    root = Path(__file__).resolve().parents[2]
    dashboard = (root / "frontend/src/modules/academicAffairs/views/AaDashboardView.vue").read_text(encoding="utf-8")

    assert 'id="adb-todos"' in dashboard
    assert "点击直达处理页面" in dashboard
    assert "t.drillRoute" in dashboard
    assert "getDashboardReminders" in dashboard
