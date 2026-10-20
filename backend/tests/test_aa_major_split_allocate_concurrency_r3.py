"""P2-01 / AA-004 targeted MySQL regression for formal major-split allocation serialization."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_major_split_allocate_r3 as svc

TID = 1000000000000000811
SCHOOL_USER = {"userId": "db-93001", "loginName": "aa-r3-split-school", "currentRoleCode": "ACADEMIC_ADMIN"}


def _patch(monkeypatch, gpa_map=None):
    monkeypatch.setattr(svc._legacy, "_tid", lambda: TID)
    monkeypatch.setattr(svc._legacy, "_require_school", lambda *_a, **_k: None)
    mapping = dict(gpa_map or {})
    monkeypatch.setattr(
        svc._legacy,
        "_gpa_of",
        lambda _db, student_ids: {int(sid): float(mapping.get(int(sid), 0)) for sid in student_ids},
    )


def _seed_batch(name="R3 分流批次", specs=None):
    from app.db.session import get_sessionmaker
    from app.models import AaMajorSplitBatch, AaMajorSplitOption, AaMajorSplitVolunteer, Tenant

    specs = specs or [
        (94001, "S002", [95001, 95002]),
        (94002, "S001", [95001, 95002]),
        (94003, "S003", [95002]),
    ]
    db = get_sessionmaker()()
    try:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(
                id=TID,
                tenant_code="aa-r3-major-split",
                school_name="AA R3 专业分流学校",
                short_name="AA R3 分流",
                deploy_mode="SAAS",
                db_mode="SHARED",
                status="ACTIVE",
            ))
            db.flush()
        batch = AaMajorSplitBatch(
            tenant_id=TID,
            batch_name=name,
            grade="2099",
            max_choices=3,
            status="CLOSED",
        )
        db.add(batch); db.flush()
        db.add_all([
            AaMajorSplitOption(
                tenant_id=TID, batch_id=batch.id, major_id=95001,
                major_name="R3 专业 A", capacity=1, allocated_count=0,
            ),
            AaMajorSplitOption(
                tenant_id=TID, batch_id=batch.id, major_id=95002,
                major_name="R3 专业 B", capacity=2, allocated_count=0,
            ),
        ])
        for student_id, student_no, choices in specs:
            db.add(AaMajorSplitVolunteer(
                tenant_id=TID,
                batch_id=batch.id,
                student_id=student_id,
                student_no=student_no,
                student_name=f"R3 {student_no}",
                choices_json=__import__("json").dumps(choices),
                status="PENDING",
            ))
        db.commit()
        return int(batch.id)
    finally:
        db.close()


def _audit_count(batch_id):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail
    db = get_sessionmaker()()
    try:
        return int(db.scalar(select(func.count(AffairsAuditTrail.id)).where(
            AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_type == "AA_MAJOR_SPLIT",
            AffairsAuditTrail.biz_id == int(batch_id),
            AffairsAuditTrail.action == "SPLIT_ALLOCATE",
        )) or 0)
    finally:
        db.close()


def _results(batch_id):
    from app.db.session import get_sessionmaker
    from app.models import AaMajorSplitBatch, AaMajorSplitOption, AaMajorSplitVolunteer
    db = get_sessionmaker()()
    try:
        batch = db.get(AaMajorSplitBatch, int(batch_id))
        volunteers = db.scalars(select(AaMajorSplitVolunteer).where(
            AaMajorSplitVolunteer.batch_id == int(batch_id)
        ).order_by(AaMajorSplitVolunteer.student_no)).all()
        options = db.scalars(select(AaMajorSplitOption).where(
            AaMajorSplitOption.batch_id == int(batch_id)
        ).order_by(AaMajorSplitOption.major_id)).all()
        return {
            "status": batch.status,
            "volunteers": {
                row.student_no: (int(row.result_major_id or 0), row.result_choice_rank, row.status)
                for row in volunteers
            },
            "options": {int(row.major_id): int(row.allocated_count or 0) for row in options},
        }
    finally:
        db.close()


def test_two_formal_allocates_same_batch_commit_only_once(db_mode, monkeypatch):
    _patch(monkeypatch, {94001: 4.0, 94002: 4.0, 94003: 3.0})
    bid = _seed_batch()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(svc.allocate, SCHOOL_USER, bid, False) for _ in range(2)]
        success = 0; conflicts = 0
        for future in futures:
            try:
                future.result(timeout=15); success += 1
            except AppException as exc:
                assert exc.code == "DATA_CONFLICT"
                conflicts += 1
    assert (success, conflicts) == (1, 1)
    assert _results(bid)["status"] == "ALLOCATED"


def test_split_allocate_audit_count_is_exactly_one(db_mode, monkeypatch):
    _patch(monkeypatch, {94001: 4.0, 94002: 4.0, 94003: 3.0})
    bid = _seed_batch()
    svc.allocate(SCHOOL_USER, bid, False)
    with pytest.raises(AppException):
        svc.allocate(SCHOOL_USER, bid, False)
    assert _audit_count(bid) == 1


def test_two_different_batches_can_allocate_independently(db_mode, monkeypatch):
    _patch(monkeypatch, {94001: 4.0, 94002: 4.0, 94003: 3.0, 94101: 3.5})
    a = _seed_batch("R3 分流批次 A")
    b = _seed_batch("R3 分流批次 B", specs=[(94101, "T001", [95001])])
    with ThreadPoolExecutor(max_workers=2) as pool:
        ra = pool.submit(svc.allocate, SCHOOL_USER, a, False)
        rb = pool.submit(svc.allocate, SCHOOL_USER, b, False)
        assert ra.result(timeout=15)["dryRun"] is False
        assert rb.result(timeout=15)["dryRun"] is False
    assert _results(a)["status"] == "ALLOCATED"
    assert _results(b)["status"] == "ALLOCATED"


def test_dry_run_then_formal_allocate_uses_latest_data(db_mode, monkeypatch):
    _patch(monkeypatch, {94001: 4.0, 94002: 3.0, 94003: 2.0})
    bid = _seed_batch()
    preview = svc.allocate(SCHOOL_USER, bid, True)
    assert preview["dryRun"] is True
    assert _results(bid)["status"] == "CLOSED"

    from app.db.session import get_sessionmaker
    from app.models import AaMajorSplitVolunteer
    db = get_sessionmaker()()
    try:
        student = db.scalars(select(AaMajorSplitVolunteer).where(
            AaMajorSplitVolunteer.batch_id == bid,
            AaMajorSplitVolunteer.student_no == "S002",
        )).one()
        student.choices_json = "[95002]"
        db.commit()
    finally:
        db.close()

    svc.allocate(SCHOOL_USER, bid, False)
    assert _results(bid)["volunteers"]["S002"][0] == 95002


def test_gpa_studentno_preference_and_capacity_result_is_unchanged(db_mode, monkeypatch):
    _patch(monkeypatch, {94001: 4.0, 94002: 4.0, 94003: 3.0})
    bid = _seed_batch()
    svc.allocate(SCHOOL_USER, bid, False)
    result = _results(bid)
    # Same GPA: S001 sorts before S002 and takes the single A seat; S002 falls back to B.
    assert result["volunteers"]["S001"] == (95001, 1, "ALLOCATED")
    assert result["volunteers"]["S002"] == (95002, 2, "ALLOCATED")
    assert result["volunteers"]["S003"] == (95002, 1, "ALLOCATED")
    assert result["options"] == {95001: 1, 95002: 2}
