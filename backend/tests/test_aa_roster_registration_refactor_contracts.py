"""D2-S 学籍名册 + 注册管理 Move Only 结构合同。"""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.core.security import require_staff
from app.modules.academic_affairs.routers import academic_affairs_bundle, roster_registration_router


def _methods(route: APIRoute) -> set[str]:
    return set(route.methods or set()) - {"HEAD", "OPTIONS"}


def _first_route(path: str, method: str) -> APIRoute:
    for route in academic_affairs_bundle.build_router().routes:
        if isinstance(route, APIRoute) and route.path == path and method in _methods(route):
            return route
    raise AssertionError(f"missing route {method} {path}")


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


def test_d2_public_shapes_are_owned_by_roster_registration_router():
    expected = "app.modules.academic_affairs.routers.roster_registration_router"
    children = [r for r in roster_registration_router.router.routes if isinstance(r, APIRoute)]
    assert children
    for child in children:
        for method in _methods(child):
            public = _first_route(child.path, method)
            assert public.endpoint.__module__ == expected, (method, child.path, public.endpoint.__module__)


def test_d2_export_compat_shapes_keep_task_backed_owner():
    expected = "app.modules.academic_affairs.routers.academic_export_compat_router"
    for path in (
        "/academic-affairs/roster/export",
        "/academic-affairs/registration/archive/{batchId}/export",
        "/academic-affairs/registration/unregistered/export",
    ):
        route = _first_route(path, "POST")
        assert route.endpoint.__module__ == expected, (path, route.endpoint.__module__)


def test_d2_router_does_not_duplicate_export_compat_shapes():
    child_shapes = {
        (route.path, method)
        for route in roster_registration_router.router.routes
        if isinstance(route, APIRoute)
        for method in _methods(route)
    }
    for path in (
        "/academic-affairs/roster/export",
        "/academic-affairs/registration/archive/{batchId}/export",
        "/academic-affairs/registration/unregistered/export",
    ):
        assert (path, "POST") not in child_shapes, path


def test_d2_literal_roster_routes_stay_before_student_parameter_route():
    paths = [r.path for r in roster_registration_router.router.routes if isinstance(r, APIRoute)]
    parameter_index = paths.index("/academic-affairs/roster/{studentId}")
    for literal in (
        "/academic-affairs/roster/status-summary",
        "/academic-affairs/roster/import/template",
        "/academic-affairs/roster/import/dry-run",
        "/academic-affairs/roster/import/xlsx",
        "/academic-affairs/roster/import/errors-xlsx",
        "/academic-affairs/roster/import/confirm",
        "/academic-affairs/roster/corrections",
    ):
        assert paths.index(literal) < parameter_index, literal


def test_d2_permission_dependencies_remain_exact():
    expected = {
        ("/academic-affairs/roster", "GET"): {"academicAffairs.roster.view"},
        ("/academic-affairs/roster/status-summary", "GET"): {"academicAffairs.roster.view"},
        ("/academic-affairs/roster/import/template", "GET"): {"academicAffairs.roster.import"},
        ("/academic-affairs/roster/import/dry-run", "POST"): {"academicAffairs.roster.import"},
        ("/academic-affairs/roster/import/xlsx", "POST"): {"academicAffairs.roster.import"},
        ("/academic-affairs/roster/import/errors-xlsx", "POST"): {"academicAffairs.roster.import"},
        ("/academic-affairs/roster/import/confirm", "POST"): {"academicAffairs.roster.import"},
        ("/academic-affairs/roster/corrections", "POST"): {"academicAffairs.roster.correction.apply"},
        ("/academic-affairs/roster/corrections", "GET"): {
            "academicAffairs.roster.correction.view", "academicAffairs.roster.correction.review"
        },
        ("/academic-affairs/roster/corrections/{correctionId}/review", "POST"): {
            "academicAffairs.roster.correction.review"
        },
        ("/academic-affairs/roster/{studentId}", "GET"): {"academicAffairs.roster.view"},
        ("/academic-affairs/registration-batches", "POST"): {"academicAffairs.registration.manage"},
        ("/academic-affairs/registration-batches", "GET"): {"academicAffairs.registration.view"},
        ("/academic-affairs/registration-batches/{batchId}/register", "POST"): {
            "academicAffairs.registration.manage"
        },
        ("/academic-affairs/registration-batches/{batchId}/registrations", "GET"): {
            "academicAffairs.registration.view"
        },
        ("/academic-affairs/registration-batches/{batchId}/close", "POST"): {
            "academicAffairs.registration.archive.manage"
        },
        ("/academic-affairs/registration-batches/{batchId}/archive", "POST"): {
            "academicAffairs.registration.archive.manage"
        },
        ("/academic-affairs/registration/archive", "GET"): {"academicAffairs.registration.archive.view"},
        ("/academic-affairs/registration/archive/{batchId}", "GET"): {
            "academicAffairs.registration.archive.view"
        },
        ("/academic-affairs/registration-batches/{batchId}/eligibility", "GET"): {
            "academicAffairs.registration.eligibility.view"
        },
        ("/academic-affairs/registration-batches/{batchId}/eligibility/{studentId}/verify", "POST"): {
            "academicAffairs.registration.eligibility.verify"
        },
        ("/academic-affairs/registration/unregistered", "GET"): {
            "academicAffairs.registration.unregistered.view"
        },
        ("/academic-affairs/registration-batches/{batchId}/scan-unregistered", "POST"): {
            "academicAffairs.registration.unregistered.scan"
        },
        ("/academic-affairs/registration-batches/{batchId}/deferrals", "POST"): {
            "academicAffairs.registration.deferral.apply"
        },
        ("/academic-affairs/registration/deferrals", "GET"): {
            "academicAffairs.registration.deferral.view"
        },
        ("/academic-affairs/registration/deferrals/{deferralId}/review", "POST"): {
            "academicAffairs.registration.deferral.approve"
        },
        ("/academic-affairs/registration-batches/{batchId}/exceptions", "POST"): {
            "academicAffairs.registration.exception.create"
        },
        ("/academic-affairs/registration/exceptions", "GET"): {
            "academicAffairs.registration.exception.view"
        },
        ("/academic-affairs/registration/exceptions/{exceptionId}/resolve", "POST"): {
            "academicAffairs.registration.exception.resolve"
        },
    }
    for key, codes in expected.items():
        route = _first_route(*key)
        assert _permission_codes(route) == codes, (key, _permission_codes(route), codes)

    reveal = _first_route("/academic-affairs/roster/{studentId}/reveal", "POST")
    assert _permission_codes(reveal) == set()
    assert any(dep.call is require_staff for dep in reveal.dependant.dependencies)


def test_d2_routes_are_visible_in_final_openapi():
    from app.core.config import settings
    from app.main import app

    schema = app.openapi()
    for child in roster_registration_router.router.routes:
        if not isinstance(child, APIRoute):
            continue
        public_path = f"{settings.API_V1_PREFIX}{child.path}"
        assert public_path in schema["paths"], public_path
        for method in _methods(child):
            assert method.lower() in schema["paths"][public_path], (method, public_path)


def test_d2_move_only_reuses_legacy_dto_objects():
    from app.modules.academic_affairs.routers import academic_affairs as legacy

    for name in (
        "ExcelImportRows", "ExcelErrorRows", "RosterCorrectionCreate", "RosterCorrectionReview",
        "RosterRevealBody", "RegBatchCreate", "RegisterBody", "EligibilityVerifyBody",
        "DeferralApplyBody", "DeferralReviewBody", "ExceptionCreateBody", "ExceptionResolveBody",
    ):
        assert getattr(roster_registration_router, name) is getattr(legacy, name), name
