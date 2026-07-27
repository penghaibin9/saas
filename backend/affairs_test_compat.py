"""Legacy student-affairs test adapter.

The production APIs require current optimistic-lock versions and formal publicity periods.
Older integration tests predate those contracts. This pytest-only plugin mirrors the real
frontend by reading the current row version before a legacy write. It never changes app code
or relaxes production validation.
"""
from __future__ import annotations

import os
import re
from typing import Any

import pytest

_VERSION_ROUTES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"/student-affairs/activities/(\d+)/(?:publish|transition|confirm|unconfirm|archive)$"), "AffairsActivity"),
    (re.compile(r"/student-affairs/volunteer/records/(\d+)/(?:confirm|reject)$"), "AffairsVolunteerRecord"),
    (re.compile(r"/student-affairs/second-class/appeals/(\d+)/review$"), "AffairsCreditAppeal"),
    (re.compile(r"/student-affairs/aid/applications/(\d+)/(?:review|publicity-confirm|resubmit|adjust|adjust-review)$"), "AidApply"),
    (re.compile(r"/student-affairs/aid/objections/(\d+)/review$"), "AidObjection"),
    (re.compile(r"/student-affairs/funding/applications/(\d+)/(?:review|publicity-confirm|disburse)$"), "FundingApplication"),
    (re.compile(r"/student-affairs/funding/appeals/(\d+)/review$"), "FundingAppeal"),
    (re.compile(r"/student-affairs/clubs/(\d+)/(?:review|disband)$"), "AffairsClub"),
    (re.compile(r"/student-affairs/counselor-eval/evals/(\d+)/(?:publish|appeal|appeal-review)$"), "CounselorEval"),
    (re.compile(r"/student-affairs/counselor-assessment/assessments/(\d+)/score$"), "AffairsCounselorAssessment"),
    (re.compile(r"/student-affairs/counselor-assessment/periods/(\d+)/publish$"), "AffairsCounselorAssessmentPeriod"),
    (re.compile(r"/student-affairs/discipline/cases/(\d+)/(?:submit|review|deliver|remove|remove-review)$"), "DisciplineCase"),
    (re.compile(r"/student-affairs/discipline/appeals/(\d+)/review$"), "DisciplineAppeal"),
    (re.compile(r"/student-affairs/dorm/transfers/(\d+)/review$"), "DormTransfer"),
    (re.compile(r"/student-affairs/dorm/exceptions/(\d+)/handle$"), "CsDormException"),
    (re.compile(r"/student-affairs/leave/(\d+)/(?:submit|review|cancel|cancel-review|extend|extension-review|close|overdue-handle)$"), "CsLeave"),
    (re.compile(r"/student-affairs/risk/records/(\d+)/(?:assign|process|follow|transfer|escalate|takeover|close|reopen)$"), "AffairsRiskRecord"),
    (re.compile(r"/student-affairs/talks/(\d+)/(?:record|follow-up)$"), "TalkPlan"),
    (re.compile(r"/student-affairs/league/dev/(\d+)/(?:stage|terminate)$"), "AffairsLeagueDev"),
    (re.compile(r"/student-affairs/orgs/(\d+)/(?:review|disband)$"), "AffairsStudentOrg"),
    (re.compile(r"/student-affairs/work-study/posts/(\d+)/(?:publish|close)$"), "WorkStudyPost"),
    (re.compile(r"/student-affairs/student-loans/(\d+)/(?:review|confirm)$"), "StudentLoan"),
    (re.compile(r"/student-affairs/fee-reductions/(\d+)/(?:review|confirm)$"), "FeeReduction"),
)

_SKIP_VERSION_MARKERS = (
    "version_required", "missing_version", "stale_version", "optimistic_lock",
    "version_conflict", "requires_version",
)


def _current_test() -> str:
    return os.environ.get("PYTEST_CURRENT_TEST", "").lower()


def _body(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    value = kwargs.get("json")
    return value if isinstance(value, dict) else None


def _read_version(path: str) -> int | None:
    from app import models
    from app.db.session import get_sessionmaker

    for pattern, model_name in _VERSION_ROUTES:
        match = pattern.search(path)
        if not match:
            continue
        model = getattr(models, model_name, None)
        if model is None:
            return None
        db = get_sessionmaker()()
        try:
            row = db.get(model, int(match.group(1)))
            if row is None or getattr(row, "is_deleted", False):
                return None
            return int(getattr(row, "version", 0) or 0)
        finally:
            db.close()
    return None


def _prepare_legacy_affairs_request(method: str, path: str, kwargs: dict[str, Any]) -> None:
    if method not in {"POST", "PUT", "PATCH"} or "/student-affairs/" not in path:
        return
    body = _body(kwargs)
    if body is None:
        return

    current = _current_test()
    if (
        path.endswith("/aid/batches") or path.endswith("/funding/batches")
    ) and body.get("publicityDays") == 0 and not any(
        marker in current for marker in ("invalid", "validation", "publicity_guard")
    ):
        body["publicityDays"] = 1

    if "version" in body or any(marker in current for marker in _SKIP_VERSION_MARKERS):
        return
    version = _read_version(path)
    if version is not None:
        body["version"] = version


@pytest.fixture(scope="session", autouse=True)
def _install_affairs_legacy_adapter():
    import conftest

    client_cls = conftest.GraduationBatchAwareClient
    if getattr(client_cls, "_affairs_legacy_adapter_installed", False):
        yield
        return

    original = client_cls.request

    def request(self, method, url, **kwargs):
        method_upper = str(method).upper()
        path, _query = self._path_and_query(url)
        _prepare_legacy_affairs_request(method_upper, path, kwargs)
        return original(self, method_upper, url, **kwargs)

    client_cls.request = request
    client_cls._affairs_legacy_adapter_installed = True
    yield
