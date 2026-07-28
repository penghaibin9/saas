"""教务扩展不得覆盖主线路由安全守卫，也不得继续修改共享注册文件。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app/api/v1/route_registration.py").read_text(encoding="utf-8")
PACKAGE = (ROOT / "app/modules/academic_affairs/routers/__init__.py").read_text(encoding="utf-8")
BUNDLE = (ROOT / "app/modules/academic_affairs/routers/academic_affairs_bundle.py").read_text(encoding="utf-8")


def test_graduation_and_internship_main_security_routes_are_preserved():
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


def test_shared_main_registry_contains_no_branch_compatibility_fork():
    for forbidden in (
        "find_spec",
        "_module_exists",
        "_academic_affairs_extension_routers",
        "register_academic_affairs_extensions",
        "mobile_security_modules",
        "student_portal_security_modules",
    ):
        assert forbidden not in SOURCE
    assert 'api_router.include_router(academic_affairs.router, dependencies=deps["aa"])' in SOURCE


def test_academic_extensions_are_aggregated_inside_the_domain_package():
    assert "academic_affairs_bundle as academic_affairs" in PACKAGE
    assert "router.include_router(base_router.router)" in BUNDLE
    for token in (
        "dashboard_readiness_router",
        "dynamic_grade_router",
        "exam_incident_closure_router",
        "grade_task_identity_router",
        "mobile_grade_entry_router",
        "program_quality_router",
        "semester_pilot_router",
        "stats_snapshot_router",
        "student_evaluation_router",
        "student_exam_router",
        "teaching_class_router",
        "teaching_task_workbench_router",
        "term_detail_router",
        "textbook_closure_router",
    ):
        assert token in BUNDLE
    assert "sys.modules" not in BUNDLE
    assert "routes.remove" not in BUNDLE


def test_existing_main_registration_order_is_unchanged():
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
        "register_platform_routes(api_router)",
    ]
    positions = [SOURCE.index(token) for token in ordered]
    assert positions == sorted(positions)
