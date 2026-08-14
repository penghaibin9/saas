"""D9-S5 教务归档 Router Move Only 与不可变边界合同。"""
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


def test_d9_s5_archive_management_routes_are_owned_by_archive_core_router():
    owners = _owners()
    expected = {
        ("/academic-affairs/archive/batches", ("POST",)),
        ("/academic-affairs/archive/batches", ("GET",)),
        ("/academic-affairs/archive/batches/{}", ("GET",)),
        ("/academic-affairs/archive/batches/{}/check", ("POST",)),
        ("/academic-affairs/archive/batches/{}/confirm", ("POST",)),
        ("/academic-affairs/archive/batches/{}/unfreeze", ("POST",)),
        ("/academic-affairs/archive/batches/{}/cancel", ("POST",)),
        ("/academic-affairs/archive/precheck", ("GET",)),
        ("/academic-affairs/archive/batches/{}/download-log", ("GET",)),
    }
    missing = expected - set(owners)
    assert not missing, f"D9-S5 archive routes missing from public bundle: {sorted(missing)}"
    expected_owner = "app.modules.academic_affairs.routers.archive_core_router"
    wrong = {key: owners[key] for key in expected if owners[key] != expected_owner}
    assert not wrong, f"D9-S5 archive public owner drift: {wrong}"


def test_d9_s5_preserves_exportjob_and_post_archive_correction_owners():
    owners = _owners()
    compat = "app.modules.academic_affairs.routers.academic_export_compat_router"
    assert owners[("/academic-affairs/archive/batches/{}/export", ("GET",))] == compat
    assert owners[("/academic-affairs/archive/batches/{}/items/{}/export", ("GET",))] == compat

    correction = "app.modules.academic_affairs.routers.archive_correction_router"
    correction_routes = {
        ("/academic-affairs/archive/batches/{}/manifest/verify", ("GET",)),
        ("/academic-affairs/archive/batches/{}/corrections", ("GET",)),
        ("/academic-affairs/archive/corrections/{}", ("GET",)),
        ("/academic-affairs/archive/batches/{}/corrections", ("POST",)),
        ("/academic-affairs/archive/corrections/{}/approve", ("POST",)),
    }
    wrong = {key: owners.get(key) for key in correction_routes if owners.get(key) != correction}
    assert not wrong, f"D9-S5 archive correction owner drift: {wrong}"


def test_d9_s5_archived_unfreeze_is_bound_to_fail_closed_immutable_guard():
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import academic_affairs_archive_immutable_guard as immutable_guard

    assert services.academic_affairs_archive_service.unfreeze is immutable_guard.reject_archive_unfreeze
