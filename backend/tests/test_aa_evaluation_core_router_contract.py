"""D9-S3 教学评价 Router Move Only 结构合同。"""
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


def test_d9_s3_evaluation_routes_are_owned_by_evaluation_core_router():
    owners = _owners()
    expected = {
        ("/academic-affairs/evaluation/batches", ("POST",)),
        ("/academic-affairs/evaluation/batches", ("GET",)),
        ("/academic-affairs/evaluation/batches/{}", ("GET",)),
        ("/academic-affairs/evaluation/batches/{}/tasks", ("POST",)),
        ("/academic-affairs/evaluation/batches/{}/tasks", ("GET",)),
        ("/academic-affairs/evaluation/batches/{}/publish", ("POST",)),
        ("/academic-affairs/evaluation/batches/{}/open", ("POST",)),
        ("/academic-affairs/evaluation/batches/{}/close-score", ("POST",)),
        ("/academic-affairs/evaluation/batches/{}/publish-results", ("POST",)),
        ("/academic-affairs/evaluation/batches/{}/archive", ("POST",)),
        ("/academic-affairs/evaluation/batches/{}/role-tasks", ("POST",)),
        ("/academic-affairs/evaluation/my-role-tasks", ("GET",)),
        ("/academic-affairs/evaluation/submit", ("POST",)),
        ("/academic-affairs/evaluation/batches/{}/results", ("GET",)),
        ("/academic-affairs/evaluation/batches/{}/my-results", ("GET",)),
        ("/academic-affairs/evaluation/appeals", ("POST",)),
        ("/academic-affairs/evaluation/appeals", ("GET",)),
        ("/academic-affairs/evaluation/appeals/{}/review", ("POST",)),
        ("/academic-affairs/evaluation/batches/{}/stats", ("GET",)),
    }
    missing = expected - set(owners)
    assert not missing, f"D9-S3 routes missing from public bundle: {sorted(missing)}"
    expected_owner = "app.modules.academic_affairs.routers.evaluation_core_router"
    wrong = {key: owners[key] for key in expected if owners[key] != expected_owner}
    assert not wrong, f"D9-S3 public owner drift: {wrong}"


def test_d9_s3_preserves_formal_extension_and_export_owners():
    owners = _owners()
    assert owners[("/academic-affairs/evaluation/my-student-tasks", ("GET",))] == (
        "app.modules.academic_affairs.routers.student_evaluation_router"
    )
    assert owners[("/academic-affairs/evaluation/batches/{}/export", ("POST",))] == (
        "app.modules.academic_affairs.routers.academic_export_compat_router"
    )
