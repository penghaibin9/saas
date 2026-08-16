"""Graduation real-MySQL tests replay the production School-IAM Authority convergence.

Production stays fail-closed: this plugin only prepares a fresh pytest database after
``db_mode`` has cleared it.  It invokes the same production convergence used by the
School-IAM bootstrap: Permission Catalog reconcile -> published SYSTEM RoleTemplates ->
B8 shadow zero-drift verification.  No pytest-only wildcard or hand-built SCHOOL_ADMIN
permission set is introduced.
"""
from __future__ import annotations

import os

import pytest


def _is_graduation_test(request) -> bool:
    name = str(getattr(getattr(request, "node", None), "fspath", "") or "").replace("\\", "/")
    return name.rsplit("/", 1)[-1].startswith("test_graduation")


def _converge_school_iam_authority() -> None:
    from app.services.school_iam_authority_service import converge_school_iam_authority

    source_sha = str(os.environ.get("GITHUB_SHA") or "pytest-graduation-authority-baseline")
    result = converge_school_iam_authority(
        source="PYTEST_GRADUATION_AUTHORITY_BASELINE",
        source_commit_sha=source_sha,
        actor_user_id=None,
    )
    shadow = dict(result.get("shadow") or {})
    if not result.get("converged") or not shadow.get("zeroUnexplainedDrift"):
        raise RuntimeError(
            "pytest Graduation School-IAM Authority convergence did not reach zero drift"
        )


@pytest.fixture(autouse=True)
def _graduation_school_admin_authority_baseline(request):
    if (
        not _is_graduation_test(request)
        or "db_mode" not in request.fixturenames
        or "auth_headers" not in request.fixturenames
    ):
        yield
        return

    # db_mode owns fresh-schema/data cleanup.  Resolve auth_headers before the replay so
    # any legacy login/bootstrap side effects happen first; the final writer is always
    # the same production School-IAM convergence used by deployment/bootstrap tooling.
    request.getfixturevalue("db_mode")
    request.getfixturevalue("auth_headers")
    _converge_school_iam_authority()
    yield
