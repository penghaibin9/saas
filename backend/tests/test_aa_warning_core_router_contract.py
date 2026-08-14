"""D9-S2 学业预警 Router Move Only 结构合同。"""
from __future__ import annotations

import re


def _key(route):
    path = re.sub(r"\{[^/{}]+\}", "{}", getattr(route, "path", ""))
    methods = tuple(sorted(getattr(route, "methods", set()) or set()))
    return path, methods


def _owners():
    from app.modules.academic_affairs.routers import academic_affairs_bundle

    return {
        _key(route): route.endpoint.__module__
        for route in academic_affairs_bundle.build_router().routes
        if getattr(route, "endpoint", None)
    }


def test_d9_s2_warning_routes_are_owned_by_warning_core_router():
    owners = _owners()
    expected = {
        ("/academic-affairs/warnings/scan", ("POST",)),
        ("/academic-affairs/warnings/scan/credit", ("POST",)),
        ("/academic-affairs/warnings/scan/gpa", ("POST",)),
        ("/academic-affairs/warnings/scan/retake", ("POST",)),
        ("/academic-affairs/warnings/scan/graduation", ("POST",)),
        ("/academic-affairs/warnings/scan/attendance", ("POST",)),
        ("/academic-affairs/warnings/scan/all", ("POST",)),
        ("/academic-affairs/warnings/rules", ("GET",)),
        ("/academic-affairs/warnings/rules/{}", ("PUT",)),
        ("/academic-affairs/warnings/summary", ("GET",)),
        ("/academic-affairs/warnings/notifications", ("GET",)),
        ("/academic-affairs/warnings/notifications/summary", ("GET",)),
        ("/academic-affairs/warnings", ("GET",)),
        ("/academic-affairs/warnings/{}", ("GET",)),
        ("/academic-affairs/warnings/{}/assign", ("POST",)),
        ("/academic-affairs/warnings/{}/interventions", ("POST",)),
        ("/academic-affairs/warnings/{}/escalate", ("POST",)),
        ("/academic-affairs/warnings/{}/close", ("POST",)),
        ("/academic-affairs/warnings/{}/void", ("POST",)),
        ("/academic-affairs/warnings/{}/remind", ("POST",)),
    }
    missing = expected - set(owners)
    assert not missing, f"D9-S2 routes missing from public bundle: {sorted(missing)}"
    expected_owner = "app.modules.academic_affairs.routers.warning_core_router"
    wrong = {key: owners[key] for key in expected if owners[key] != expected_owner}
    assert not wrong, f"D9-S2 public owner drift: {wrong}"
