"""Standalone enterprise routes must be mounted outside the staff dependency bundle."""
from app.api.router import api_router


def _methods():
    result = set()
    for route in api_router.routes:
        for method in getattr(route, "methods", set()) or set():
            result.add((route.path, method))
    return result


def test_enterprise_portal_and_collaboration_surfaces_are_reachable():
    methods = _methods()
    assert ("/internship/enterprise-portal/auth/browser-login", "POST") in methods
    assert ("/internship/enterprise-portal/collaboration-context", "GET") in methods
    assert ("/internship/enterprise-portal/evaluation-tasks", "GET") in methods
    assert (
        "/internship/enterprise-portal/evaluation-tasks/{internship_id}/submit",
        "POST",
    ) in methods


def test_enterprise_route_is_not_duplicated_by_staff_surface():
    paths = [route.path for route in api_router.routes]
    assert paths.count("/internship/enterprise-portal/evaluation-tasks") == 1
    assert paths.count("/internship/enterprise-portal/auth/browser-login") == 1
