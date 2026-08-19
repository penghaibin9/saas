"""D4-S 课程 / 培养方案 / 教学任务 Move Only 结构合同。"""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.modules.academic_affairs.routers import (
    academic_affairs as legacy,
    academic_affairs_bundle,
    course_program_task_router,
    program_quality_router,
    teaching_class_router,
)
from app.modules.academic_affairs.services import academic_affairs_course_public_service as course_public_svc


def _methods(route: APIRoute) -> set[str]:
    return set(route.methods or set()) - {"HEAD", "OPTIONS"}


def _first_route(path: str, method: str) -> APIRoute:
    for route in academic_affairs_bundle.build_router().routes:
        if isinstance(route, APIRoute) and route.path == path and method in _methods(route):
            return route
    raise AssertionError(f"missing route {method} {path}")


def _first_in(router, path: str, method: str) -> APIRoute:
    for route in router.routes:
        if isinstance(route, APIRoute) and route.path == path and method in _methods(route):
            return route
    raise AssertionError(f"missing child route {method} {path}")


def _collect_permission_codes(value) -> set[str]:
    if isinstance(value, str):
        return {value} if value.startswith("academicAffairs.") else set()
    if isinstance(value, (list, tuple, set, frozenset)):
        out: set[str] = set()
        for item in value:
            out.update(_collect_permission_codes(item))
        return out
    return set()


def _permission_codes(route: APIRoute) -> set[str]:
    codes: set[str] = set()
    stack = list(route.dependant.dependencies)
    seen: set[int] = set()
    while stack:
        dep = stack.pop()
        if id(dep) in seen:
            continue
        seen.add(id(dep))
        call = getattr(dep, "call", None)
        for cell in getattr(call, "__closure__", None) or ():
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            codes.update(_collect_permission_codes(value))
        stack.extend(getattr(dep, "dependencies", None) or [])
    return codes


def test_d4_public_legacy_shapes_are_owned_by_course_program_task_router():
    expected = "app.modules.academic_affairs.routers.course_program_task_router"
    children = [r for r in course_program_task_router.router.routes if isinstance(r, APIRoute)]
    assert children
    for child in children:
        for method in _methods(child):
            public = _first_route(child.path, method)
            assert public.endpoint.__module__ == expected, (method, child.path, public.endpoint.__module__)


def test_d4_move_only_preserves_legacy_permission_codes_and_route_contract_metadata():
    for child in course_program_task_router.router.routes:
        if not isinstance(child, APIRoute):
            continue
        for method in _methods(child):
            old = _first_in(legacy.router, child.path, method)
            assert _permission_codes(child) == _permission_codes(old), (method, child.path)
            assert child.summary == old.summary, (method, child.path)
            assert child.status_code == old.status_code, (method, child.path)
            assert child.response_model == old.response_model, (method, child.path)


def test_d4_existing_program_quality_and_teaching_class_extensions_keep_owner():
    program_quality = _first_route("/academic-affairs/programs/{program_id}/validation", "GET")
    assert program_quality.endpoint.__module__ == "app.modules.academic_affairs.routers.program_quality_router"

    teaching_classes = _first_route("/academic-affairs/teaching-classes", "GET")
    assert teaching_classes.endpoint.__module__ == "app.modules.academic_affairs.routers.teaching_class_router"

    d4_shapes = {
        (route.path, method)
        for route in course_program_task_router.router.routes
        if isinstance(route, APIRoute)
        for method in _methods(route)
    }
    for extension in (program_quality_router.router, teaching_class_router.router):
        for route in extension.routes:
            if not isinstance(route, APIRoute):
                continue
            for method in _methods(route):
                assert (route.path, method) not in d4_shapes


def test_d4_routes_are_visible_in_final_openapi():
    from app.core.config import settings
    from app.main import app

    schema = app.openapi()
    for child in course_program_task_router.router.routes:
        if not isinstance(child, APIRoute):
            continue
        public_path = f"{settings.API_V1_PREFIX}{child.path}"
        assert public_path in schema["paths"], public_path
        for method in _methods(child):
            assert method.lower() in schema["paths"][public_path], (method, public_path)


def test_d4_move_only_reuses_legacy_contract_objects_and_services():
    aliases = (
        "ProgramCreate",
        "ProgramUpdate",
        "ProgramCourseBody",
        "ProgramCourseUpdate",
        "AaReviewBody",
        "BindGradeBody",
        "CreditRequirementsBody",
        "GraduationRequirementCreate",
        "GraduationRequirementUpdate",
        "PracticeSegmentCreate",
        "PracticeSegmentUpdate",
        "ProgramChangeStatusBody",
        "ProgramChangeBody",
        "CourseCreate",
        "CourseMaterialCreate",
        "TaskBatchGenerate",
        "AssignBody",
        "TeacherActBody",
        "MergeTasksBody",
        "AdjustTaskBody",
    )
    for name in aliases:
        assert getattr(course_program_task_router, name) is getattr(legacy, name), name

    assert course_program_task_router.prog_svc is legacy.prog_svc
    assert course_program_task_router.task_svc is legacy.task_svc
    assert course_program_task_router.course_svc is course_public_svc
    # A-W2 only replaces the ENABLED -> v+1 writer; all other course capabilities remain
    # a transparent compatibility pass-through to the mature legacy course service.
    assert course_public_svc.create_course is legacy.course_svc.create_course
    assert course_public_svc.list_courses is legacy.course_svc.list_courses
    assert course_public_svc.review_course is legacy.course_svc.review_course
    assert course_public_svc.update_course is not legacy.course_svc.update_course
    assert course_program_task_router._PROG_VIEW is legacy._PROG_VIEW
    assert course_program_task_router._COURSE_VIEW is legacy._COURSE_VIEW
