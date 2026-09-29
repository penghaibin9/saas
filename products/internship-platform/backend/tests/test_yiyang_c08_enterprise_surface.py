"""Standalone enterprise routes must be mounted in the real app outside staff authority."""
from app.main import app


def _methods():
    result = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        for method in getattr(route, "methods", set()) or set():
            result.add((path, method))
    return result


def test_enterprise_portal_and_collaboration_surfaces_are_reachable():
    methods = _methods()
    prefix = "/api/v1"
    assert (f"{prefix}/internship/enterprise-portal/auth/browser-login", "POST") in methods
    assert (f"{prefix}/internship/enterprise-portal/collaboration-context", "GET") in methods
    assert (f"{prefix}/internship/enterprise-portal/evaluation-tasks", "GET") in methods
    assert (
        f"{prefix}/internship/enterprise-portal/evaluation-tasks/{{internship_id}}/submit",
        "POST",
    ) in methods


def test_enterprise_route_is_not_duplicated_by_staff_surface():
    paths = [getattr(route, "path", "") for route in app.routes]
    assert paths.count("/api/v1/internship/enterprise-portal/evaluation-tasks") == 1
    assert paths.count("/api/v1/internship/enterprise-portal/auth/browser-login") == 1
