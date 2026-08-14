"""D8-S3 成绩更正/复查结构合同：只切五条 owner，不抢成绩认定等相邻链路。"""
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


def test_d8_grade_change_and_recheck_routes_are_owned_by_s3_router():
    owners = _owners()
    expected = {
        ("/academic-affairs/grade-tasks/{}/records/{}/change-request", ("POST",)),
        ("/academic-affairs/grade-change/{}/college-review", ("POST",)),
        ("/academic-affairs/grade-change/{}/academic-review", ("POST",)),
        ("/academic-affairs/grade-rechecks", ("GET",)),
        ("/academic-affairs/grade-rechecks/{}/review", ("POST",)),
    }
    missing = expected - set(owners)
    assert not missing, f"D8-S3 routes missing from public bundle: {sorted(missing)}"
    wrong = {
        key: owners[key]
        for key in expected
        if owners[key] != "app.modules.academic_affairs.routers.grade_change_recheck_router"
    }
    assert not wrong, f"D8-S3 public owner drift: {wrong}"


def test_d8_s3_keeps_grade_recognition_on_existing_owner_for_s4():
    owners = _owners()
    legacy = "app.modules.academic_affairs.routers.academic_affairs"
    for key in (
        ("/academic-affairs/grade-recognitions", ("GET",)),
        ("/academic-affairs/grade-recognitions", ("POST",)),
        ("/academic-affairs/grade-recognitions/{}/review", ("POST",)),
        ("/academic-affairs/grade-recognitions/student/submit", ("POST",)),
        ("/academic-affairs/grade-recognitions/my", ("GET",)),
    ):
        assert owners[key] == legacy, f"D8-S3 must not steal recognition owner: {key} -> {owners[key]}"


def test_d8_s3_preserves_existing_grade_core_read_and_export_owners():
    owners = _owners()
    assert owners[("/academic-affairs/grade-tasks/{}/submit", ("POST",))] == (
        "app.modules.academic_affairs.routers.grade_core_router"
    )
    assert owners[("/academic-affairs/students/{}/transcript", ("GET",))] == (
        "app.modules.academic_affairs.routers.grade_read_router"
    )
    assert owners[("/academic-affairs/students/{}/transcript/export", ("POST",))] == (
        "app.modules.academic_affairs.routers.academic_export_compat_router"
    )
