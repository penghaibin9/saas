"""Stage C1 major-split must cut over through StudentAcademicFact atomically."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services.academic_affairs_student_fact_service import (
    resolve_student_academic_fact,
)
from tests.test_aa_major_split import BASE, _hdr, _mk_batch, _seed, _submit_all


@pytest.mark.usefixtures("db_mode")
def test_formal_major_split_confirm_appends_fact_and_preserves_preconfirm_identity(client, db_mode):
    from app.models import StudentProfile
    from app.models.academic_affairs_student_fact import StudentAcademicFact

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _mk_batch(client, admin, ids)
    _submit_all(client, ids, bid)
    client.post(f"{BASE}/major-split/batches/{bid}/close", headers=admin)
    client.post(f"{BASE}/major-split/batches/{bid}/allocate", headers=admin)
    before_confirm = datetime.utcnow()

    r = client.post(f"{BASE}/major-split/batches/{bid}/confirm", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["confirmed"] == 3

    db = get_sessionmaker()()
    try:
        sid = ids["stus"]["FL2401"]
        profile = db.get(StudentProfile, sid)
        old = resolve_student_academic_fact(db, sid, before_confirm)
        current = resolve_student_academic_fact(db, sid)
        facts = db.query(StudentAcademicFact).filter(
            StudentAcademicFact.tenant_id == profile.tenant_id,
            StudentAcademicFact.student_id == sid,
        ).order_by(StudentAcademicFact.version_no).all()
        assert len(facts) == 2
        assert old.major_id == ids["src"]
        assert current.major_id == ids["ma"]
        assert profile.major_id == current.major_id
        assert current.source_type == "MAJOR_SPLIT"
        assert current.source_ref_id == int(bid)
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_major_split_projection_drift_rolls_back_entire_batch(client, db_mode):
    from app.models import AaMajorSplitBatch, StudentProfile
    from app.models.academic_affairs_student_fact import StudentAcademicFact

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _mk_batch(client, admin, ids)
    _submit_all(client, ids, bid)
    client.post(f"{BASE}/major-split/batches/{bid}/close", headers=admin)
    client.post(f"{BASE}/major-split/batches/{bid}/allocate", headers=admin)

    # Inject legacy/direct-write drift into the last student. The canonical command for
    # that student must fail after earlier rows were processed, proving transaction rollback.
    drift_sid = max(ids["stus"].values())
    db = get_sessionmaker()()
    try:
        drift = db.get(StudentProfile, drift_sid)
        drift.major_id = ids["mb"]
        db.commit()
    finally:
        db.close()

    r = client.post(f"{BASE}/major-split/batches/{bid}/confirm", headers=admin)
    assert r.status_code == 409, r.text

    first_sid = min(ids["stus"].values())
    db = get_sessionmaker()()
    try:
        first = db.get(StudentProfile, first_sid)
        batch = db.get(AaMajorSplitBatch, int(bid))
        assert first.major_id == ids["src"], "earlier student changes must rollback with the batch"
        assert batch.status == "ALLOCATED"
        assert db.query(StudentAcademicFact).filter(
            StudentAcademicFact.tenant_id == first.tenant_id,
            StudentAcademicFact.student_id == first_sid,
        ).count() == 1
    finally:
        db.close()
