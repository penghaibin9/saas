"""D9-S1b 毕业证书 Router Move Only 结构合同。"""
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


def test_d9_s1b_certificate_routes_are_owned_by_graduation_certificate_router():
    owners = _owners()
    expected = {
        ("/academic-affairs/graduation-batches/{}/certificates/generate", ("POST",)),
        ("/academic-affairs/graduation-certificates", ("GET",)),
        ("/academic-affairs/graduation-certificates/{}/issue", ("POST",)),
        ("/academic-affairs/graduation-certificates/{}/void", ("POST",)),
    }
    missing = expected - set(owners)
    assert not missing, f"D9-S1b routes missing from public bundle: {sorted(missing)}"
    expected_owner = "app.modules.academic_affairs.routers.graduation_certificate_router"
    wrong = {key: owners[key] for key in expected if owners[key] != expected_owner}
    assert not wrong, f"D9-S1b public owner drift: {wrong}"
