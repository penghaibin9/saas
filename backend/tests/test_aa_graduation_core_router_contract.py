"""D9-S1a 毕业资格审核 Router Move Only 结构合同。"""
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


def test_d9_s1a_graduation_qualification_routes_are_owned_by_graduation_core_router():
    owners = _owners()
    expected = {
        ("/academic-affairs/graduation-audit-batches", ("GET",)),
        ("/academic-affairs/graduation-audit-batches", ("POST",)),
        ("/academic-affairs/graduation-audit-batches/{}/generate", ("POST",)),
        ("/academic-affairs/graduation-audit-batches/{}/precheck", ("POST",)),
        ("/academic-affairs/graduation-audit-batches/{}/fee-clearance", ("POST",)),
        ("/academic-affairs/graduation-audit-batches/{}/fee-clearance/mark", ("POST",)),
        ("/academic-affairs/graduation-audit-batches/{}/archive", ("POST",)),
        ("/academic-affairs/graduation-audit-batches/{}/results", ("GET",)),
        ("/academic-affairs/graduation-audit-batches/{}/rosters", ("GET",)),
        ("/academic-affairs/graduation-results/{}", ("GET",)),
        ("/academic-affairs/graduation-results/{}/college-review", ("POST",)),
        ("/academic-affairs/graduation-results/{}/final", ("POST",)),
    }
    missing = expected - set(owners)
    assert not missing, f"D9-S1a routes missing from public bundle: {sorted(missing)}"
    expected_owner = "app.modules.academic_affairs.routers.graduation_core_router"
    wrong = {key: owners[key] for key in expected if owners[key] != expected_owner}
    assert not wrong, f"D9-S1a public owner drift: {wrong}"


def test_d9_s1a_graduation_core_never_owns_certificate_routes():
    owners = _owners()
    graduation_core_owner = "app.modules.academic_affairs.routers.graduation_core_router"
    certificate_routes = {
        ("/academic-affairs/graduation-batches/{}/certificates/generate", ("POST",)),
        ("/academic-affairs/graduation-certificates", ("GET",)),
        ("/academic-affairs/graduation-certificates/{}/issue", ("POST",)),
        ("/academic-affairs/graduation-certificates/{}/void", ("POST",)),
    }
    missing = certificate_routes - set(owners)
    assert not missing, f"certificate routes missing from public bundle: {sorted(missing)}"
    stolen = {key: owners[key] for key in certificate_routes if owners[key] == graduation_core_owner}
    assert not stolen, f"graduation core must not own certificate routes: {stolen}"
