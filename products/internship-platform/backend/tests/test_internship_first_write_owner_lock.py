"""Same-record first writes must serialize before probing an empty child range."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select

from test_internship_v93_batch2_remaining_first_create import (
    ADMIN_USER, TID, _admin_ctx, _ctx, _seed, _session, safety_course,
)


def _parallel(operation):
    barrier = Barrier(2)

    def run(index):
        barrier.wait(timeout=10)
        return operation(index)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, index) for index in range(2)]
        # Any deadlock/timeout/authorization failure is a test failure, not an
        # accepted loser; these idempotent entrypoints should both return a row.
        return [future.result(timeout=30) for future in futures]


@pytest.mark.parametrize("mode", ["students", "teachers", "mixed"])
@pytest.mark.parametrize("repeat", range(3))
def test_safety_first_write_is_one_record_across_entrypoints(safety_course, mode, repeat):
    from app.models import InternshipSafetyCompletion
    from app.modules.internship.services import internship_safety_service as svc

    ids = safety_course

    def operation(index):
        if mode == "teachers" or (mode == "mixed" and index == 0):
            _admin_ctx()
            return svc.ensure_completion({"internshipId": str(ids["internship"]), "courseId": ids["course"]}, user=ADMIN_USER)
        _ctx(ids["studentNo"])
        return svc.start_my_course(ids["course"], {"studentNo": ids["studentNo"], "userType": "STUDENT", "userId": "1"})

    result = _parallel(operation)
    assert result[0]["id"] == result[1]["id"]
    with _session() as db:
        rows = list(db.scalars(select(InternshipSafetyCompletion).where(
            InternshipSafetyCompletion.tenant_id == TID,
            InternshipSafetyCompletion.internship_id == ids["internship"],
            InternshipSafetyCompletion.course_id == int(ids["course"]),
            InternshipSafetyCompletion.is_deleted.is_(False),
        )))
        assert len(rows) == 1
        assert rows[0].status == ("NOT_STARTED" if mode == "teachers" else "IN_PROGRESS")


@pytest.mark.parametrize("same_content", [True, False])
@pytest.mark.parametrize("repeat", range(3))
def test_consent_first_write_keeps_one_current_record(db_mode, same_content, repeat):
    from app.models import InternshipConsent
    from app.modules.internship.services import internship_consent_service as svc

    with _session() as db:
        ids = _seed(db)
        db.commit()

    def operation(index):
        _admin_ctx()
        return svc.create_pending({"internshipId": str(ids["internship"]), "consentType": "STUDENT",
            "contentSnapshot": "测试安全须知" + ("" if same_content else str(index)), "contentVersion": "test-1"}, user=ADMIN_USER)

    results = _parallel(operation)
    if same_content:
        assert results[0]["id"] == results[1]["id"]
    with _session() as db:
        rows = list(db.scalars(select(InternshipConsent).where(
            InternshipConsent.tenant_id == TID, InternshipConsent.internship_id == ids["internship"],
            InternshipConsent.consent_type == "STUDENT", InternshipConsent.is_deleted.is_(False),
        )))
        assert sum(row.status in {"PENDING", "VALID"} for row in rows) == 1
        assert len(rows) == (1 if same_content else 2)


def test_owner_lock_cannot_access_another_tenant_record(db_mode):
    from app.core.context import get_tenant, set_tenant
    from app.core.exceptions import AppException
    from app.modules.internship.services.internship_scope import lock_internship_record

    with _session() as db:
        ids = _seed(db)
        db.commit()
    before = get_tenant()
    try:
        set_tenant({"tenantId": str(TID + 1)})
        with _session() as db, pytest.raises(AppException):
            lock_internship_record(db, ids["internship"])
    finally:
        set_tenant(before)
