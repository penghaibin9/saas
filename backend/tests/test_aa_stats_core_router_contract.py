"""D9-S6 教务统计 Router Move Only 与正式 owner 合同。"""
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


def test_d9_s6_public_stats_routes_are_owned_by_stats_core_router():
    owners = _owners()
    expected = {
        ("/academic-affairs/stats/overview", ("GET",)),
        ("/academic-affairs/stats/filters", ("GET",)),
        ("/academic-affairs/stats/registration", ("GET",)),
        ("/academic-affairs/stats/status-change", ("GET",)),
        ("/academic-affairs/stats/warning", ("GET",)),
        ("/academic-affairs/stats/status-change/summary", ("GET",)),
        ("/academic-affairs/stats/registration/summary", ("GET",)),
        ("/academic-affairs/stats/course", ("GET",)),
        ("/academic-affairs/stats/course/detail", ("GET",)),
        ("/academic-affairs/stats/teaching-task", ("GET",)),
        ("/academic-affairs/stats/teaching-task/pending", ("GET",)),
        ("/academic-affairs/stats/schedule", ("GET",)),
        ("/academic-affairs/stats/schedule/conflicts", ("GET",)),
        ("/academic-affairs/stats/grade", ("GET",)),
        ("/academic-affairs/stats/grade/detail", ("GET",)),
        ("/academic-affairs/stats/warning/summary", ("GET",)),
        ("/academic-affairs/stats/graduation", ("GET",)),
        ("/academic-affairs/stats/graduation/abnormal", ("GET",)),
        ("/academic-affairs/stats/workload", ("GET",)),
        ("/academic-affairs/stats/workload/detail", ("GET",)),
        ("/academic-affairs/stats/course-selection", ("GET",)),
        ("/academic-affairs/stats/course-selection/detail", ("GET",)),
        ("/academic-affairs/stats/exam", ("GET",)),
        ("/academic-affairs/stats/exam/detail", ("GET",)),
        ("/academic-affairs/stats/resource", ("GET",)),
        ("/academic-affairs/stats/resource/detail", ("GET",)),
    }
    missing = expected - set(owners)
    assert not missing, f"D9-S6 stats routes missing from public bundle: {sorted(missing)}"
    expected_owner = "app.modules.academic_affairs.routers.stats_core_router"
    wrong = {key: owners[key] for key in expected if owners[key] != expected_owner}
    assert not wrong, f"D9-S6 stats public owner drift: {wrong}"


def test_d9_s6_preserves_exportjob_and_immutable_snapshot_owners():
    owners = _owners()
    assert owners[("/academic-affairs/stats/export", ("POST",))] == (
        "app.modules.academic_affairs.routers.academic_export_compat_router"
    )

    snapshot = "app.modules.academic_affairs.routers.stats_snapshot_router"
    snapshot_routes = {
        ("/academic-affairs/stats/snapshots", ("POST",)),
        ("/academic-affairs/stats/snapshots", ("GET",)),
        ("/academic-affairs/stats/snapshots/{}", ("GET",)),
        ("/academic-affairs/stats/snapshots/{}/verify", ("POST",)),
    }
    wrong = {key: owners.get(key) for key in snapshot_routes if owners.get(key) != snapshot}
    assert not wrong, f"D9-S6 stats snapshot owner drift: {wrong}"
