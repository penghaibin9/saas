"""教务扩展不得回退主线路由安全守卫或改变既有注册顺序。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app/api/v1/route_registration.py").read_text(encoding="utf-8")


def test_graduation_sensitive_and_mobile_guards_are_preserved():
    for token in (
        "require_mobile_graduation_request_permission",
        "install_consistency_guards()",
        "graduation_p0_guard.router",
        "graduation_sensitive_router.router",
        "graduation_archive_sensitive_router.router",
        "graduation_material_sensitive_router.router",
        "install_mobile_resolver()",
        "install_mobile_stable_bridge()",
        "install_mobile_taskbook_list_bridge()",
        "mobile_graduation_guard.router",
        "mobile_internship_context.router",
        "mobile_internship_leave_context.router",
        "mobile_internship_student.router",
        "student_portal_graduation_guard.router",
        "student_portal_internship_router",
        "enforce_student_portal_module_access",
    ):
        assert token in SOURCE


def test_academic_extensions_are_explicit_and_keep_module_gate():
    for token in (
        "def _academic_affairs_extension_routers():",
        "student_evaluation_router",
        "dashboard_readiness_router",
        "teaching_class_router",
        "mobile_grade_entry_router",
        "textbook_closure_router",
        'dependencies=deps["aa"]',
        "register_academic_affairs_extensions(api_router, deps)",
    ):
        assert token in SOURCE
    assert "sys.modules" not in SOURCE
    assert "routes.remove" not in SOURCE


def test_existing_main_registration_order_is_not_rearranged():
    ordered = [
        "register_internship_routes(api_router, deps)",
        'api_router.include_router(orientation.router, dependencies=deps["orientation"])',
        'api_router.include_router(campus_service.router, dependencies=deps["cs"])',
        'api_router.include_router(academic.router, dependencies=deps["academic_legacy"])',
        "register_graduation_routes(api_router, deps)",
        "api_router.include_router(excel.router)",
        'api_router.include_router(employment.router, dependencies=deps["employment"])',
        'api_router.include_router(student_affairs.router, dependencies=deps["sa"])',
        'api_router.include_router(academic_affairs.router, dependencies=deps["aa"])',
        "register_academic_affairs_extensions(api_router, deps)",
        "register_platform_routes(api_router)",
    ]
    positions = [SOURCE.index(token) for token in ordered]
    assert positions == sorted(positions)
