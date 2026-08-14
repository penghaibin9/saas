"""D8-S2 成绩读侧结构合同：只切读侧 owner，不抢正式导出与成绩写链。"""
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


def test_d8_grade_read_routes_are_owned_by_grade_read_router():
    owners = _owners()
    expected = {
        ("/academic-affairs/students/{}/transcript", ("GET",)),
        ("/academic-affairs/grade-views/fail-list", ("GET",)),
        ("/academic-affairs/grade-views/analysis", ("GET",)),
        ("/academic-affairs/grade-views/exception-list", ("GET",)),
        ("/academic-affairs/grade-views/audit", ("GET",)),
    }
    missing = expected - set(owners)
    assert not missing, f"D8-S2 routes missing from public bundle: {sorted(missing)}"
    wrong = {
        key: owners[key]
        for key in expected
        if owners[key] != "app.modules.academic_affairs.routers.grade_read_router"
    }
    assert not wrong, f"D8-S2 public owner drift: {wrong}"


def test_d8_grade_read_does_not_steal_exportjob_owners():
    owners = _owners()
    assert owners[("/academic-affairs/students/{}/transcript/export", ("POST",))] == (
        "app.modules.academic_affairs.routers.academic_export_compat_router"
    )
    assert owners[("/academic-affairs/grade-views/analysis/export", ("POST",))] == (
        "app.modules.academic_affairs.routers.academic_export_compat_router"
    )


def test_d8_grade_read_keeps_grade_change_recheck_and_recognition_on_existing_owner():
    owners = _owners()
    legacy = "app.modules.academic_affairs.routers.academic_affairs"
    assert owners[("/academic-affairs/grade-tasks/{}/records/{}/change-request", ("POST",))] == legacy
    assert owners[("/academic-affairs/grade-rechecks", ("GET",))] == legacy
    assert owners[("/academic-affairs/grade-rechecks/{}/review", ("POST",))] == legacy
    assert owners[("/academic-affairs/grade-recognitions", ("GET",))] == legacy
    assert owners[("/academic-affairs/grade-recognitions", ("POST",))] == legacy
