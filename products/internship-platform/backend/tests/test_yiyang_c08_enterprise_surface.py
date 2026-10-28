"""Standalone enterprise routes must be mounted in the real OpenAPI surface outside staff authority."""
from app.main import app


def _operations():
    result = set()
    for path, operations in (app.openapi().get("paths") or {}).items():
        for method in operations:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                result.add((path, method.upper()))
    return result


def test_enterprise_portal_and_collaboration_surfaces_are_reachable():
    methods = _operations()
    prefix = "/api/v1"
    assert (f"{prefix}/internship/enterprise-portal/auth/browser-login", "POST") in methods
    assert (f"{prefix}/internship/enterprise-portal/collaboration-context", "GET") in methods
    assert (f"{prefix}/internship/enterprise-portal/evaluation-tasks", "GET") in methods
    assert (
        f"{prefix}/internship/enterprise-portal/evaluation-tasks/{{internship_id}}/submit",
        "POST",
    ) in methods


def test_enterprise_route_is_not_duplicated_by_staff_surface():
    paths = [path for path, _method in _operations()]
    assert paths.count("/api/v1/internship/enterprise-portal/evaluation-tasks") == 1
    assert paths.count("/api/v1/internship/enterprise-portal/auth/browser-login") == 1
