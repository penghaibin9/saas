"""P0 contract: Course Catalog confirmation must re-check current action authority."""
from __future__ import annotations

import pytest


def _course_job(jobs):
    return {
        "adapterType": jobs.IMPORT_ADAPTER_EXCEL,
        "importType": "ACADEMIC_COURSE_CATALOG",
    }


def test_course_catalog_confirm_fails_closed_when_course_manage_was_revoked(monkeypatch):
    from app.core.exceptions import AppException
    from app.services import data_exchange_confirm_service as canonical
    from app.services import data_exchange_job_service as jobs

    user = {
        "userId": "7",
        # The caller may still have another Academic import grant at the router.
        # That must not preserve a revoked Course Catalog write grant.
        "permissions": ["academicAffairs.grade.import"],
    }
    monkeypatch.setattr(jobs, "get_import_job", lambda job_id, *, user: _course_job(jobs))

    permission_checks = []

    def revoked(actual_user, code):
        permission_checks.append((actual_user, code))
        raise AppException("NO_PERMISSION", "课程库管理权限已撤销", http_status=403)

    writer_calls = []
    monkeypatch.setattr(canonical, "enforce_permission", revoked)
    monkeypatch.setattr(
        canonical,
        "confirm_academic_import_job",
        lambda *args, **kwargs: writer_calls.append((args, kwargs)),
    )

    with pytest.raises(AppException) as exc_info:
        canonical.confirm_import_job(
            "55",
            expected_version=3,
            user=user,
            idempotency_key="course-confirm-revoked",
        )

    assert exc_info.value.code == "NO_PERMISSION"
    assert permission_checks == [(user, "academicAffairs.course.manage")]
    assert writer_calls == []


def test_course_catalog_confirm_rechecks_permission_before_dispatch(monkeypatch):
    from app.services import data_exchange_confirm_service as canonical
    from app.services import data_exchange_job_service as jobs

    user = {"userId": "7"}
    monkeypatch.setattr(jobs, "get_import_job", lambda job_id, *, user: _course_job(jobs))

    order = []

    def allowed(actual_user, code):
        assert actual_user is user
        assert code == "academicAffairs.course.manage"
        order.append("permission")

    def writer(*args, **kwargs):
        order.append("writer")
        return {"confirmedRows": 1}

    monkeypatch.setattr(canonical, "enforce_permission", allowed)
    monkeypatch.setattr(canonical, "confirm_academic_import_job", writer)

    result = canonical.confirm_import_job(
        "55",
        expected_version=3,
        user=user,
        idempotency_key="course-confirm-allowed",
    )

    assert result == {"confirmedRows": 1}
    assert order == ["permission", "writer"]


def test_non_course_academic_confirm_does_not_inherit_course_permission_gate(monkeypatch):
    from app.services import data_exchange_confirm_service as canonical
    from app.services import data_exchange_job_service as jobs

    user = {"userId": "7"}
    monkeypatch.setattr(
        jobs,
        "get_import_job",
        lambda job_id, *, user: {
            "adapterType": jobs.IMPORT_ADAPTER_EXCEL,
            "importType": "ACADEMIC_GRADE",
        },
    )

    monkeypatch.setattr(
        canonical,
        "enforce_permission",
        lambda *_args, **_kwargs: pytest.fail("Course permission gate leaked into another import type"),
    )
    monkeypatch.setattr(
        canonical,
        "confirm_academic_import_job",
        lambda *args, **kwargs: {"confirmedRows": 2},
    )

    assert canonical.confirm_import_job(
        "56",
        expected_version=1,
        user=user,
        idempotency_key="grade-confirm",
    ) == {"confirmedRows": 2}
