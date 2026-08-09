"""Stage C1 temporal academic fact contracts (real DB fixture)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services.academic_affairs_student_fact_service import (
    append_student_academic_fact,
    create_baseline_student_academic_fact,
    current_projection_reconciliation,
    resolve_student_academic_fact,
)

TID = 98109


def _activate():
    set_tenant({"tenantId": str(TID), "tenantCode": "stage-c1"})


def _student(no: str, *, major_id=101, class_id=1001):
    from app.models import StudentProfile

    return StudentProfile(
        tenant_id=TID,
        student_no=no,
        real_name=f"C1-{no}",
        college_id=11,
        major_id=major_id,
        class_id=class_id,
        grade="2024",
        current_stage="ON_CAMPUS",
        student_status="REGISTERED",
        status="ACTIVE",
    )


@pytest.mark.usefixtures("db_mode")
def test_as_of_resolver_keeps_old_major_after_current_projection_changes():
    _activate()
    db = get_sessionmaker()()
    try:
        s = _student("C1FACT001")
        db.add(s)
        db.flush()
        baseline_at = datetime(2026, 1, 1, 0, 0, 0)
        create_baseline_student_academic_fact(
            db, s, valid_from=baseline_at, source_type="TEST_BASELINE", source_quality="EXACT"
        )
        base_version = int(s.version or 0)

        next_fact, projected = append_student_academic_fact(
            db,
            s.id,
            effective_at=datetime(2026, 6, 1, 0, 0, 0),
            major_id=202,
            class_id=2002,
            source_type="TRANSFER_MAJOR",
            source_ref_id=70001,
            expected_student_version=base_version,
        )
        db.commit()

        old = resolve_student_academic_fact(db, s.id, datetime(2026, 3, 1, 0, 0, 0))
        current = resolve_student_academic_fact(db, s.id, datetime(2026, 7, 1, 0, 0, 0))
        assert old.major_id == 101 and old.class_id == 1001
        assert current.id == next_fact.id
        assert current.major_id == 202 and current.class_id == 2002
        assert projected.major_id == 202
        assert int(projected.version or 0) == base_version + 1
        assert current_projection_reconciliation(db, s.id)["matched"] is True
    finally:
        db.close()
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_future_fact_append_fails_closed_without_changing_projection():
    _activate()
    db = get_sessionmaker()()
    try:
        s = _student("C1FACT002")
        db.add(s)
        db.flush()
        create_baseline_student_academic_fact(
            db, s, valid_from=datetime.utcnow() - timedelta(days=30), source_quality="EXACT"
        )
        before_version = int(s.version or 0)
        with pytest.raises(AppException) as exc:
            append_student_academic_fact(
                db,
                s.id,
                effective_at=datetime.utcnow() + timedelta(days=1),
                major_id=303,
                source_type="TRANSFER_MAJOR",
                source_ref_id=70002,
                expected_student_version=before_version,
            )
        assert exc.value.code == "ACADEMIC_FACT_FUTURE_NOT_DUE"
        db.rollback()
        db.refresh(s)
        assert s.major_id == 101
        assert int(s.version or 0) == before_version
    finally:
        db.close()
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_projection_drift_is_not_laundered_by_next_canonical_change():
    _activate()
    db = get_sessionmaker()()
    try:
        s = _student("C1FACT003")
        db.add(s)
        db.flush()
        create_baseline_student_academic_fact(
            db, s, valid_from=datetime.utcnow() - timedelta(days=30), source_quality="EXACT"
        )
        db.commit()

        # Simulate a legacy/direct profile write. The next canonical command must expose
        # the drift instead of silently making the ledger agree with corrupted current data.
        s.major_id = 909
        db.commit()
        with pytest.raises(AppException) as exc:
            append_student_academic_fact(
                db,
                s.id,
                major_id=808,
                source_type="TRANSFER_MAJOR",
                source_ref_id=70003,
                expected_student_version=int(s.version or 0),
            )
        assert exc.value.code == "ACADEMIC_FACT_PROJECTION_DRIFT"
        assert current_projection_reconciliation(db, s.id)["matched"] is False
    finally:
        db.close()
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_multiple_active_facts_are_hard_integrity_failure():
    from app.models.academic_affairs_student_fact import StudentAcademicFact

    _activate()
    db = get_sessionmaker()()
    try:
        s = _student("C1FACT004")
        db.add(s)
        db.flush()
        first = create_baseline_student_academic_fact(
            db, s, valid_from=datetime.utcnow() - timedelta(days=30), source_quality="EXACT"
        )
        db.add(
            StudentAcademicFact(
                tenant_id=TID,
                student_id=s.id,
                version_no=int(first.version_no) + 1,
                valid_from=datetime.utcnow() - timedelta(days=1),
                valid_to=None,
                student_status=s.student_status,
                college_id=s.college_id,
                major_id=s.major_id,
                class_id=s.class_id,
                grade=s.grade,
                source_type="INJECTED_CONFLICT",
                source_quality="UNKNOWN",
            )
        )
        db.commit()

        with pytest.raises(AppException) as exc:
            resolve_student_academic_fact(db, s.id)
        assert exc.value.code == "ACADEMIC_FACT_OVERLAP"
    finally:
        db.close()
        set_tenant(None)
