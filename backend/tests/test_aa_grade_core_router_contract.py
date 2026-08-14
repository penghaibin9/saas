"""D8-S1 成绩主链结构合同：Move Only owner 切换，不抢既有独立成绩入口。"""
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


def test_d8_grade_task_create_stays_on_stable_identity_v2_owner():
    owners = _owners()
    assert owners[("/academic-affairs/grade-tasks", ("POST",))] == (
        "app.modules.academic_affairs.routers.grade_task_create_v2_router"
    )


def test_d8_grade_core_move_only_routes_are_owned_by_grade_core_router():
    owners = _owners()
    expected = {
        ("/academic-affairs/grade-tasks", ("GET",)),
        ("/academic-affairs/grade-tasks/{}/roster", ("GET",)),
        ("/academic-affairs/grade-tasks/{}/records", ("GET",)),
        ("/academic-affairs/grade-tasks/{}/scores", ("POST",)),
        ("/academic-affairs/grade-tasks/{}/import/template", ("GET",)),
        ("/academic-affairs/grade-tasks/{}/import/xlsx", ("POST",)),
        ("/academic-affairs/grade-tasks/{}/import/errors-xlsx", ("POST",)),
        ("/academic-affairs/grade-tasks/{}/import/confirm", ("POST",)),
        ("/academic-affairs/grade-tasks/{}/submit", ("POST",)),
        ("/academic-affairs/grade-tasks/{}/college-review", ("POST",)),
        ("/academic-affairs/grade-tasks/{}/publish", ("POST",)),
        ("/academic-affairs/grade-tasks/{}/return", ("POST",)),
        ("/academic-affairs/grade-tasks/{}/archive", ("POST",)),
    }
    missing = expected - set(owners)
    assert not missing, f"D8-S1 routes missing from public bundle: {sorted(missing)}"
    wrong = {
        key: owners[key]
        for key in expected
        if owners[key] != "app.modules.academic_affairs.routers.grade_core_router"
    }
    assert not wrong, f"D8-S1 public owner drift: {wrong}"


def test_d8_does_not_steal_dynamic_or_mobile_grade_extensions():
    owners = _owners()
    assert owners[("/academic-affairs/grade-tasks/{}/scheme", ("GET",))] == (
        "app.modules.academic_affairs.routers.dynamic_grade_router"
    )
    assert owners[("/mobile/teacher/academic/grade-tasks/{}/batch-save", ("POST",))] == (
        "app.modules.academic_affairs.routers.mobile_grade_entry_router"
    )


def test_d8_grade_exports_keep_exportjob_compat_owner():
    owners = _owners()
    assert owners[("/academic-affairs/students/{}/transcript/export", ("POST",))] == (
        "app.modules.academic_affairs.routers.academic_export_compat_router"
    )
    assert owners[("/academic-affairs/grade-views/analysis/export", ("POST",))] == (
        "app.modules.academic_affairs.routers.academic_export_compat_router"
    )
