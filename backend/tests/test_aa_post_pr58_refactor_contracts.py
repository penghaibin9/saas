"""PR #58 合并后教务 P0 拆分的 S0 / D1-S 结构合同。

这组测试只冻结生产结构真值，不改变业务语义：
- Router 精确 adapter/final 入口必须优先于 legacy 大 Router；
- normalized path + method 不允许重复；
- D1 学期/校历/作息节次/time-bands 的公开 owner 必须真正切到新 Router；
- D1 公开 permission dependency 与最终 OpenAPI 核心合同不得漂移；
- Service 包级公开入口和关键 binding 必须继续指向 canonical/final 实现；
- Model registry 必须保持 model-only；
- #58 已落地的 MySQL DATETIME(6) / TEXT schema 事实不得在 Model 拆分时回退。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from fastapi.routing import APIRoute
from sqlalchemy import Text
from sqlalchemy.dialects import mysql

from app.models.academic_affairs import AaGraduationAuditResult, AaStatusChange
from app.modules.academic_affairs.routers import academic_affairs_bundle, term_calendar_router
from app.modules.academic_affairs.services import (
    academic_affairs_schedule_facade,
    academic_affairs_scheduling_rule_final_facade,
    academic_affairs_stats_contract_facade,
)
from app.modules.academic_affairs import services


def _route_methods(route: APIRoute) -> set[str]:
    return set(route.methods or set()) - {"HEAD", "OPTIONS"}


def _normalized_path(path: str) -> str:
    return re.sub(r"\{[^/{}]+\}", "{}", path)


def _first_route(path: str, method: str) -> APIRoute:
    for route in academic_affairs_bundle.build_router().routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path == path and method in _route_methods(route):
            return route
    raise AssertionError(f"missing academic route: {method} {path}")


def _captured_permission_codes(route: APIRoute) -> set[str]:
    """读取 require_permission(code) 闭包，不依赖函数名或装饰性 metadata。"""
    codes: set[str] = set()
    stack = list(route.dependant.dependencies)
    seen: set[int] = set()
    while stack:
        dependency = stack.pop()
        if id(dependency) in seen:
            continue
        seen.add(id(dependency))
        call = getattr(dependency, "call", None)
        for cell in getattr(call, "__closure__", None) or ():
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            if isinstance(value, str) and value.startswith("academicAffairs."):
                codes.add(value)
        stack.extend(getattr(dependency, "dependencies", None) or [])
    return codes


def _schema_refs(value) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            refs.add(ref)
        for child in value.values():
            refs.update(_schema_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(_schema_refs(child))
    return refs


def test_academic_bundle_has_no_normalized_method_shape_duplicates():
    seen: dict[tuple[str, str], str] = {}
    for route in academic_affairs_bundle.build_router().routes:
        if not isinstance(route, APIRoute):
            continue
        for method in _route_methods(route):
            key = (_normalized_path(route.path), method)
            owner = f"{route.endpoint.__module__}.{route.endpoint.__name__}"
            assert key not in seen, (
                f"duplicate academic route shape {key}: first={seen.get(key)} second={owner}"
            )
            seen[key] = owner


def test_exact_adapters_and_final_routes_win_before_legacy_router():
    expected = {
        ("/academic-affairs/grade-tasks", "POST"): (
            "app.modules.academic_affairs.routers.grade_task_create_v2_router"
        ),
        ("/academic-affairs/selection/batches/{batchId}/publish", "POST"): (
            "app.modules.academic_affairs.routers.academic_selection_final_router"
        ),
        ("/academic-affairs/selection/student/courses", "GET"): (
            "app.modules.academic_affairs.routers.academic_selection_final_router"
        ),
        ("/academic-affairs/selection/student/enroll", "POST"): (
            "app.modules.academic_affairs.routers.academic_selection_final_router"
        ),
        ("/academic-affairs/selection/student/drop", "POST"): (
            "app.modules.academic_affairs.routers.academic_selection_final_router"
        ),
        ("/academic-affairs/scheduling/rules", "PUT"): (
            "app.modules.academic_affairs.routers.scheduling_rule_router"
        ),
        ("/academic-affairs/scheduling/rules", "GET"): (
            "app.modules.academic_affairs.routers.scheduling_rule_router"
        ),
        ("/academic-affairs/scheduling/rules/{rule_id}", "DELETE"): (
            "app.modules.academic_affairs.routers.scheduling_rule_router"
        ),
        ("/academic-affairs/roster/export", "POST"): (
            "app.modules.academic_affairs.routers.academic_export_compat_router"
        ),
        ("/academic-affairs/schedule/export", "POST"): (
            "app.modules.academic_affairs.routers.academic_export_compat_router"
        ),
    }
    for (path, method), module_name in expected.items():
        route = _first_route(path, method)
        assert route.endpoint.__module__ == module_name, (
            f"{method} {path} owner drifted to {route.endpoint.__module__}"
        )


def test_d1_term_calendar_public_shapes_are_owned_by_extracted_router():
    expected_module = "app.modules.academic_affairs.routers.term_calendar_router"
    child_routes = [
        route for route in term_calendar_router.router.routes if isinstance(route, APIRoute)
    ]
    assert child_routes, "term calendar router unexpectedly has no APIRoutes"

    for child in child_routes:
        for method in _route_methods(child):
            public = _first_route(child.path, method)
            assert public.endpoint.__module__ == expected_module, (
                f"D1-S owner drift for {method} {child.path}: "
                f"expected={expected_module} actual={public.endpoint.__module__}"
            )


def test_d1_literal_term_routes_remain_reachable_before_parameter_route():
    routes = [
        route for route in academic_affairs_bundle.build_router().routes if isinstance(route, APIRoute)
    ]
    ordered_paths = [route.path for route in routes]
    parameter_index = ordered_paths.index("/academic-affairs/terms/{termId}")
    for literal_path in (
        "/academic-affairs/terms/current",
        "/academic-affairs/terms/archive-overview",
        "/academic-affairs/terms/years",
        "/academic-affairs/terms/switch-log",
    ):
        assert ordered_paths.index(literal_path) < parameter_index, (
            f"literal route {literal_path} must stay before /terms/{{termId}}"
        )


def test_d1_permission_dependencies_remain_exact():
    expected = {
        ("/academic-affairs/terms", "POST"): "academicAffairs.term.manage",
        ("/academic-affairs/terms", "GET"): "academicAffairs.term.view",
        ("/academic-affairs/terms/current", "GET"): "academicAffairs.term.view",
        ("/academic-affairs/terms/{termId}/publish", "POST"): "academicAffairs.term.manage",
        ("/academic-affairs/terms/{termId}/set-current", "POST"): "academicAffairs.term.manage",
        ("/academic-affairs/terms/{termId}/weeks", "GET"): "academicAffairs.term.view",
        ("/academic-affairs/terms/{termId}/teaching-weeks", "PUT"): "academicAffairs.term.manage",
        ("/academic-affairs/terms/{termId}/freeze", "POST"): "academicAffairs.term.manage",
        ("/academic-affairs/terms/{termId}/unfreeze", "POST"): "academicAffairs.term.manage",
        ("/academic-affairs/terms/archive-overview", "GET"): "academicAffairs.term.view",
        ("/academic-affairs/terms/years", "GET"): "academicAffairs.term.view",
        ("/academic-affairs/terms/switch-log", "GET"): "academicAffairs.term.view",
        ("/academic-affairs/terms/{termId}", "GET"): "academicAffairs.term.view",
        ("/academic-affairs/terms/{termId}/calendar", "POST"): "academicAffairs.calendar.manage",
        ("/academic-affairs/terms/{termId}/calendar", "GET"): "academicAffairs.calendar.view",
        ("/academic-affairs/terms/{termId}/calendar/{eventId}", "PUT"): "academicAffairs.calendar.manage",
        ("/academic-affairs/terms/{termId}/calendar/{eventId}", "DELETE"): "academicAffairs.calendar.manage",
        ("/academic-affairs/terms/{termId}/week-calendar", "GET"): "academicAffairs.calendar.view",
        ("/academic-affairs/terms/{termId}/calendar/publish", "POST"): "academicAffairs.calendarPublish.manage",
        ("/academic-affairs/time-slots", "POST"): "academicAffairs.timeslot.manage",
        ("/academic-affairs/time-slots", "GET"): "academicAffairs.timeslot.view",
        ("/academic-affairs/time-slots/{slotId}", "PUT"): "academicAffairs.timeslot.manage",
        ("/academic-affairs/time-slots/{slotId}", "DELETE"): "academicAffairs.timeslot.manage",
        ("/academic-affairs/time-slots/{slotId}/time-bands", "POST"): "academicAffairs.classTimeBand.manage",
        ("/academic-affairs/time-slots/{slotId}/time-bands", "GET"): "academicAffairs.classTimeBand.view",
        ("/academic-affairs/time-bands/{bandId}", "PUT"): "academicAffairs.classTimeBand.manage",
        ("/academic-affairs/time-bands/{bandId}", "DELETE"): "academicAffairs.classTimeBand.manage",
    }

    for (path, method), permission in expected.items():
        route = _first_route(path, method)
        assert _captured_permission_codes(route) == {permission}, (
            f"permission drift for {method} {path}: "
            f"expected={permission} actual={sorted(_captured_permission_codes(route))}"
        )


def test_d1_routes_are_visible_in_final_app_openapi():
    from app.core.config import settings
    from app.main import app

    schema = app.openapi()
    for child in term_calendar_router.router.routes:
        if not isinstance(child, APIRoute):
            continue
        public_path = f"{settings.API_V1_PREFIX}{child.path}"
        assert public_path in schema["paths"], f"OpenAPI missing D1 path: {public_path}"
        for method in _route_methods(child):
            assert method.lower() in schema["paths"][public_path], (
                f"OpenAPI missing D1 operation: {method} {public_path}"
            )


def test_d1_openapi_core_request_parameter_and_response_contracts():
    from app.core.config import settings
    from app.main import app

    schema = app.openapi()

    def operation(path: str, method: str):
        return schema["paths"][f"{settings.API_V1_PREFIX}{path}"][method.lower()]

    def assert_contract(
        path: str,
        method: str,
        *,
        body_schema: str | None = None,
        parameters: dict[tuple[str, str], bool] | None = None,
    ) -> None:
        op = operation(path, method)
        assert "200" in op.get("responses", {}), f"missing 200 response: {method} {path}"
        actual_params = {
            (item["name"], item["in"]): bool(item.get("required", False))
            for item in op.get("parameters", [])
        }
        for key, required in (parameters or {}).items():
            assert actual_params.get(key) is required, (
                f"parameter drift for {method} {path} {key}: "
                f"expected required={required} actual={actual_params.get(key)}"
            )
        if body_schema:
            body = op.get("requestBody", {})
            assert body.get("required") is True, f"request body became optional: {method} {path}"
            json_schema = body.get("content", {}).get("application/json", {}).get("schema", {})
            refs = _schema_refs(json_schema)
            assert any(ref.endswith(f"/{body_schema}") for ref in refs), (
                f"request schema drift for {method} {path}: expected={body_schema} refs={sorted(refs)}"
            )

    assert_contract(
        "/academic-affairs/terms",
        "GET",
        parameters={("status", "query"): False, ("page", "query"): False, ("pageSize", "query"): False},
    )
    assert_contract("/academic-affairs/terms", "POST", body_schema="TermCreate")
    assert_contract(
        "/academic-affairs/terms/{termId}",
        "GET",
        parameters={("termId", "path"): True},
    )
    assert_contract(
        "/academic-affairs/terms/{termId}/teaching-weeks",
        "PUT",
        body_schema="TeachingWeeksBody",
        parameters={("termId", "path"): True},
    )
    assert_contract(
        "/academic-affairs/terms/{termId}/unfreeze",
        "POST",
        body_schema="TermUnfreezeBody",
        parameters={("termId", "path"): True},
    )
    assert_contract(
        "/academic-affairs/terms/{termId}/calendar",
        "POST",
        body_schema="CalendarEventBody",
        parameters={("termId", "path"): True},
    )
    assert_contract(
        "/academic-affairs/terms/{termId}/calendar/{eventId}",
        "PUT",
        body_schema="CalendarEventUpdate",
        parameters={("termId", "path"): True, ("eventId", "path"): True},
    )
    assert_contract("/academic-affairs/time-slots", "POST", body_schema="TimeSlotCreate")
    assert_contract(
        "/academic-affairs/time-slots",
        "GET",
        parameters={("includeDisabled", "query"): False},
    )
    assert_contract(
        "/academic-affairs/time-slots/{slotId}",
        "PUT",
        body_schema="TimeSlotUpdate",
        parameters={("slotId", "path"): True},
    )
    assert_contract(
        "/academic-affairs/time-slots/{slotId}/time-bands",
        "POST",
        body_schema="TimeBandCreate",
        parameters={("slotId", "path"): True},
    )
    assert_contract(
        "/academic-affairs/time-bands/{bandId}",
        "PUT",
        body_schema="TimeBandUpdate",
        parameters={("bandId", "path"): True},
    )


def test_public_service_entrypoints_keep_final_facade_ownership():
    expected = {
        "academic_affairs_service": (
            "app.modules.academic_affairs.services.academic_affairs_dashboard_scope_facade"
        ),
        "academic_affairs_stats_service": (
            "app.modules.academic_affairs.services.academic_affairs_stats_public_service"
        ),
        "academic_affairs_selection_service": (
            "app.modules.academic_affairs.services.academic_affairs_selection_final_service"
        ),
        "academic_affairs_scheduling_service": (
            "app.modules.academic_affairs.services.academic_affairs_scheduling_public_service"
        ),
        "academic_affairs_autoschedule_service": (
            "app.modules.academic_affairs.services.academic_affairs_autoschedule_final_service"
        ),
        "academic_affairs_schedule_service": (
            "app.modules.academic_affairs.services.academic_affairs_schedule_final_service"
        ),
        "academic_affairs_exam_service": (
            "app.modules.academic_affairs.services.academic_affairs_exam_facade"
        ),
        "academic_affairs_textbook_service": (
            "app.modules.academic_affairs.services.academic_affairs_textbook_final_facade"
        ),
        "academic_affairs_org_service": (
            "app.modules.academic_affairs.services.academic_affairs_org_fact_facade"
        ),
        "mobile_academic_affairs_service": (
            "app.modules.academic_affairs.services.mobile_academic_affairs_public_service"
        ),
    }
    for public_name, module_name in expected.items():
        assert getattr(services, public_name).__name__ == module_name


def test_canonical_service_bindings_remain_installed():
    assert services.academic_affairs_stats_service.resource_stats is (
        academic_affairs_stats_contract_facade.resource_stats
    )
    assert services.academic_affairs_stats_service.resource_detail is (
        academic_affairs_stats_contract_facade.resource_detail
    )
    assert services.academic_affairs_schedule_service.student_view is (
        academic_affairs_schedule_facade.student_view
    )
    assert services.academic_affairs_autoschedule_service._load_params is (
        academic_affairs_scheduling_rule_final_facade.load_effective_params
    )
    assert services.academic_affairs_scheduling_service.save_rule is (
        academic_affairs_scheduling_rule_final_facade.save_rule
    )
    assert services.academic_affairs_scheduling_service.delete_rule is (
        academic_affairs_scheduling_rule_final_facade.delete_rule
    )


def test_academic_registry_is_model_only():
    registry_path = (
        Path(__file__).resolve().parents[1] / "app/models/academic_affairs_registry.py"
    )
    tree = ast.parse(registry_path.read_text(encoding="utf-8"))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
    forbidden = [name for name in imported_modules if ".services" in name]
    assert not forbidden, f"academic model registry must stay model-only: {forbidden}"


def test_post_pr58_schema_contracts_are_preserved_in_metadata():
    effective_date_type = AaStatusChange.__table__.c.effective_date.type
    assert effective_date_type.compile(dialect=mysql.dialect()).upper() == "DATETIME(6)"

    audit_json_type = AaGraduationAuditResult.__table__.c.item_results_json.type
    assert isinstance(audit_json_type, Text)
    assert audit_json_type.compile(dialect=mysql.dialect()).upper() == "TEXT"
