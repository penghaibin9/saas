"""PR261: real-MySQL first-write, ownership and transaction regressions."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from test_aa_grade_identity_head_concurrency import identity, _student, _session
from test_aa_effective_grade_policy_contract import (
    TID, _activate, _new_term, _policies, policy_service,
)
from test_internship_v93_batch2_remaining_first_create import _seed, _admin_ctx, ADMIN_USER

@pytest.mark.parametrize("broken_link", ["foreign", "deleted", "missing"])
def test_record_scope_rejects_invalid_student_owner(db_mode, broken_link):
    from app.core.exceptions import AppException
    from app.models import InternshipRecord, StudentProfile, Tenant
    from app.modules.internship.services.internship_scope import assert_internship_record_scope

    with _session() as db:
        ids = _seed(db)
        rec = db.get(InternshipRecord, ids["internship"])
        student = db.get(StudentProfile, rec.student_id)
        if broken_link == "foreign":
            db.add(Tenant(id=TID + 99, tenant_code="pr261-foreign-student", school_name="隔离测试学校"))
            db.flush()
            student.tenant_id = TID + 99
        elif broken_link == "deleted":
            student.is_deleted = True
        else:
            rec.student_id = 8999999999999999999
        db.commit()
    _admin_ctx()
    with _session() as db, pytest.raises(AppException) as caught:
        assert_internship_record_scope(db, ids["internship"], ADMIN_USER, "测试操作", lock=True)
    assert caught.value.http_status == 404

def test_reentrant_allocation_preserves_pending_counter(identity, db_mode):
    """The upsert/read must not overwrite an uncommitted ORM counter on re-entry."""
    from app.models import AaGradeIdentityHead
    with _session() as db:
        acad = _student(db, "GI_REENTRY")
        db.commit()
        acad_id = acad.id
        assert identity.next_study_attempt_no(db, acad_id, "GI_REENTRY") == 1
        assert identity.next_study_attempt_no(db, acad_id, "GI_REENTRY") == 2
        db.commit()
    with _session() as db:
        row = db.query(AaGradeIdentityHead).filter(
            AaGradeIdentityHead.tenant_id == TID,
            AaGradeIdentityHead.acad_student_id == acad_id,
            AaGradeIdentityHead.course_code == "GI_REENTRY",
        ).one()
        assert row.current_attempt_no == 2


def test_first_identity_creation_rolls_back_with_caller(identity, db_mode):
    """No hidden commit in the allocator: an outer failure leaves no head."""
    from app.models import AaGradeIdentityHead
    with _session() as db:
        acad = _student(db, "GI_ROLLBACK")
        db.commit()
        acad_id = acad.id
        assert identity.next_study_attempt_no(db, acad_id, "GI_ROLLBACK") == 1
        db.rollback()
    with _session() as db:
        assert db.query(AaGradeIdentityHead).filter(
            AaGradeIdentityHead.tenant_id == TID,
            AaGradeIdentityHead.acad_student_id == acad_id,
            AaGradeIdentityHead.course_code == "GI_ROLLBACK",
        ).count() == 0
        assert identity.next_study_attempt_no(db, acad_id, "GI_ROLLBACK") == 1
        db.commit()


def test_soft_deleted_identity_is_not_recreated_or_reset(identity, db_mode):
    from app.core.exceptions import AppException
    from app.models import AaGradeIdentityHead
    with _session() as db:
        acad = _student(db, "GI_DELETED")
        db.add(AaGradeIdentityHead(tenant_id=TID, acad_student_id=acad.id,
            course_code="GI_DELETED", current_attempt_no=8, is_deleted=True))
        db.commit()
        with pytest.raises(AppException) as caught:
            identity.next_study_attempt_no(db, acad.id, "GI_DELETED")
        assert caught.value.code == "DATA_CONFLICT"
        db.rollback()
        row = db.query(AaGradeIdentityHead).filter(
            AaGradeIdentityHead.tenant_id == TID,
            AaGradeIdentityHead.acad_student_id == acad.id,
            AaGradeIdentityHead.course_code == "GI_DELETED",
        ).one()
        assert row.is_deleted is True and row.current_attempt_no == 8

@pytest.mark.usefixtures("db_mode")
@pytest.mark.parametrize("repeat", range(3))
def test_concurrent_publications_share_version_chain_across_scopes(repeat):
    """One policy code can span terms; each successful publication gets a new version."""
    _activate()
    term_id = _new_term()
    barrier = Barrier(2)

    def publish(scope):
        _activate()
        barrier.wait(timeout=10)
        return policy_service.activate_grade_policy(None, {
            "attemptStrategy": "LATEST_ATTEMPT", "policyCode": "CROSS_SCOPE_RACE",
            "effectiveFromTermId": scope,
        })

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(publish, scope) for scope in [None, term_id]]
        results = [future.result(timeout=30) for future in futures]
    assert sorted(row["policyVersion"] for row in results) == [1, 2]
    active = [row for row in _policies() if row.status == "ACTIVE"]
    assert len(active) == 2
    assert {row.active_scope_key for row in active} == {"BASE", str(term_id)}
