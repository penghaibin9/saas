"""D8-S4 成绩认定/课程替代结构合同：五入口切 owner，既有成绩域 owner 不漂移。"""
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


def test_d8_grade_recognition_routes_are_owned_by_s4_router():
    owners = _owners()
    expected = {
        ("/academic-affairs/grade-recognitions", ("GET",)),
        ("/academic-affairs/grade-recognitions", ("POST",)),
        ("/academic-affairs/grade-recognitions/{}/review", ("POST",)),
        ("/academic-affairs/grade-recognitions/student/submit", ("POST",)),
        ("/academic-affairs/grade-recognitions/my", ("GET",)),
    }
    missing = expected - set(owners)
    assert not missing, f"D8-S4 routes missing from public bundle: {sorted(missing)}"
    wrong = {
        key: owners[key]
        for key in expected
        if owners[key] != "app.modules.academic_affairs.routers.grade_recognition_router"
    }
    assert not wrong, f"D8-S4 public owner drift: {wrong}"


def test_d8_s4_preserves_existing_grade_core_read_change_and_export_owners():
    owners = _owners()
    assert owners[("/academic-affairs/grade-tasks/{}/submit", ("POST",))] == (
        "app.modules.academic_affairs.routers.grade_core_router"
    )
    assert owners[("/academic-affairs/students/{}/transcript", ("GET",))] == (
        "app.modules.academic_affairs.routers.grade_read_router"
    )
    assert owners[("/academic-affairs/grade-rechecks/{}/review", ("POST",))] == (
        "app.modules.academic_affairs.routers.grade_change_recheck_router"
    )
    assert owners[("/academic-affairs/students/{}/transcript/export", ("POST",))] == (
        "app.modules.academic_affairs.routers.academic_export_compat_router"
    )
