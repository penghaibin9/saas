"""Stage D 正式选课路由必须命中 final service 的运行时合同。"""
from __future__ import annotations

import inspect

from app.modules.academic_affairs.routers import academic_affairs_bundle as bundle
from app.modules.academic_affairs.routers import academic_selection_final_router as adapter
from app.modules.academic_affairs.services import academic_affairs_selection_final_service as final_service


def _first_endpoint(path: str, method: str):
    public = bundle.build_router()
    for route in public.routes:
        methods = getattr(route, "methods", set()) or set()
        if getattr(route, "path", None) == path and method in methods:
            return route.endpoint
    raise AssertionError(f"route not found: {method} {path}")


def test_selection_final_adapter_wins_before_legacy_router():
    expected = {
        ("POST", "/academic-affairs/selection/batches/{batchId}/publish"),
        ("GET", "/academic-affairs/selection/student/courses"),
        ("POST", "/academic-affairs/selection/student/enroll"),
        ("POST", "/academic-affairs/selection/student/drop"),
    }
    for method, path in expected:
        endpoint = _first_endpoint(path, method)
        assert endpoint.__module__ == adapter.__name__


def test_selection_adapter_only_delegates_to_final_service():
    source = inspect.getsource(adapter)
    assert "selection_final.student_enroll" in source
    assert "selection_final.student_courses" in source
    assert "selection_final.student_drop" in source
    assert "selection_final.publish_batch" in source
    assert "_validate_enroll" not in source
    assert "attach_selection_trace" not in source
    assert adapter.selection_final.student_enroll is final_service.student_enroll
