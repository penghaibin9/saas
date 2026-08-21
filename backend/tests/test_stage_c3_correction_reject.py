"""W1 formal reject path for immutable post-archive corrections."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

TID = 98116
TERM_CODE = "2097-2098-1"


def _user(user_id: int, login: str) -> dict:
    return {
        "userId": str(user_id),
        "loginName": login,
        "realName": login,
        "userType": "SCHOOL_ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
    }


def _activate(user: dict, tenant_id: int = TID):
    set_tenant({"tenantId": str(tenant_id), "tenantCode": f"stage-c3-reject-{tenant_id}"})
    set_current_user(user)


def _seed_grade_archive():
    from app.models import AaArchiveBatch, AcademicGrade, AcademicStudent, ArchiveManifest
    from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as manifest_service

    db = get_sessionmaker()()
    try:
        academic = AcademicStudent(
            tenant_id=TID,
            student_no="C3REJECT001",
            name="归档纠错驳回甲",
            obtained_credits=0,
        )
        db.add(academic)
        db.flush()
        grade = AcademicGrade(
            tenant_id=TID,
            acad_student_id=academic.id,
            course_name="操作系统",
            term=TERM_CODE,
            nature="REQUIRED",
            credit_value=4,
            score=72,
            pass_status="PASSED",
            exam_type="FINAL",
            record_status="ACTIVE",
            source="PUBLISH",
            course_code="OS2097",
            course_version=1,
            attempt_no=1,
            effective_policy_code="DEFAULT",
            effective_policy_version=1,
            effective_attempt_strategy="LATEST_ATTEMPT",
            pass_line_snapshot=60,
        )
        db.add(grade)
        db.flush()
        batch = AaArchiveBatch(
            tenant_id=TID,
            batch_name="Stage C3 Reject E2E 归档",
            term_id=None,
            term_code=TERM_CODE,
            status="ARCHIVED",
            archived_at=datetime.utcnow(),
        )
        db.add(batch)
        db.flush()
        counts = {"GRADE": 1}
        hashes = {"GRADE": "b" * 64}
        max_ids = {"GRADE": int(grade.id)}
        reason = "正式归档：Stage C3 reject 测试基线"
        payload = manifest_service._manifest_payload(
            batch=batch,
            version_no=1,
            domain_counts=counts,
            domain_hashes=hashes,
            max_ids=max_ids,
            reason=reason,
        )
        manifest = ArchiveManifest(
            tenant_id=TID,
            term_id=None,
            version_no=1,
            archive_batch_id=batch.id,
            domain_counts_json=manifest_service._json(counts),
            domain_hashes_json=manifest_service._json(hashes),
            max_ids_json=manifest_service._json(max_ids),
            manifest_hash=manifest_service._hash(payload),
            reason=reason,
            supersedes_id=None,
            archived_at=datetime.utcnow(),
            archived_by=41000,
            created_by=41000,
        )
        db.add(manifest)
        db.commit()
        return int(batch.id), int(grade.id), int(manifest.id), manifest.manifest_hash
    finally:
        db.close()


def _create_case(service, creator: dict, batch_id: int, grade_id: int):
    _activate(creator)
    return service.create_correction_case(
        creator,
        batch_id,
        business_type="GRADE",
        target_ref=str(grade_id),
        reason="复核材料不足，先申请更正成绩等待二审",
        correction={"score": 78},
        evidence_manifest={"kind": "PAPER_REVIEW", "sha256": "f" * 64},
        risk_level="HIGH",
    )


@pytest.mark.usefixtures("db_mode")
def test_reject_requires_different_reviewer_and_creates_no_fact_or_manifest():
    from app.models import AaArchiveBatch, AcademicGrade, ArchiveManifest, PostArchiveCorrectionCase
    from app.modules.academic_affairs.services import academic_affairs_archive_correction_review_service as review
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    creator = _user(41001, "stage_c3_reject_creator")
    reviewer = _user(41002, "stage_c3_reject_reviewer")
    _activate(creator)
    batch_id, grade_id, manifest_v1_id, manifest_v1_hash = _seed_grade_archive()
    created = _create_case(service, creator, batch_id, grade_id)
    case_id = int(created["caseId"])

    pending_detail = review.get_correction_case(creator, case_id)
    assert pending_detail["originalOfficialFact"]["factId"] == str(grade_id)
    assert pending_detail["originalOfficialFact"]["score"] == 72
    assert pending_detail["proposedOfficialFact"]["score"] == 78
    assert pending_detail["proposedOfficialFact"]["factId"] is None
    assert pending_detail["resultingOfficialFact"] is None

    _activate(creator)
    with pytest.raises(AppException) as same_actor:
        review.reject_correction_case(creator, case_id, reason="申请人不能驳回自己的纠错申请")
    assert same_actor.value.code == "NO_PERMISSION"

    _activate(reviewer)
    rejected = review.reject_correction_case(
        reviewer,
        case_id,
        reason="证据无法证明原成绩录入错误，驳回后补充材料重新申请",
    )
    assert rejected["status"] == "REJECTED"
    assert rejected["rejectedBy"] == "41002"
    assert rejected["officialFactId"] is None
    assert rejected["resultingManifestId"] is None

    detail = review.get_correction_case(reviewer, case_id)
    assert detail["status"] == "REJECTED"
    assert detail["rejectedBy"] == "41002"
    assert "补充材料" in detail["rejectReason"]
    assert detail["originalOfficialFact"]["factId"] == str(grade_id)
    assert detail["originalOfficialFact"]["score"] == 72
    assert detail["proposedOfficialFact"] is None
    assert detail["resultingOfficialFact"] is None

    verified = service.verify_manifest(reviewer, batch_id)
    assert verified["ok"] is True
    assert verified["appliedCorrections"] == 0
    assert [row["versionNo"] for row in verified["versions"]] == [1]

    with pytest.raises(AppException) as repeated:
        review.reject_correction_case(reviewer, case_id, reason="重复驳回应被状态机幂等拒绝")
    assert repeated.value.code == "APPROVAL_VERSION_CONFLICT"

    with pytest.raises(AppException) as approve_after_reject:
        service.approve_correction_case(reviewer, case_id)
    assert approve_after_reject.value.code == "APPROVAL_VERSION_CONFLICT"

    db = get_sessionmaker()()
    try:
        case = db.get(PostArchiveCorrectionCase, case_id)
        grade = db.get(AcademicGrade, grade_id)
        batch = db.get(AaArchiveBatch, batch_id)
        manifests = db.query(ArchiveManifest).filter(
            ArchiveManifest.tenant_id == TID,
            ArchiveManifest.archive_batch_id == batch_id,
        ).order_by(ArchiveManifest.version_no).all()
        grades = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == TID,
            AcademicGrade.acad_student_id == grade.acad_student_id,
        ).all()
        assert case.status == "REJECTED"
        assert case.rejected_by == 41002 and case.rejected_at is not None
        assert case.second_approved_by is None and case.applied_at is None
        assert case.official_fact_id is None and case.resulting_manifest_id is None
        assert grade.record_status == "ACTIVE" and grade.score == 72
        assert len(grades) == 1
        assert batch.status == "ARCHIVED"
        assert len(manifests) == 1
        assert manifests[0].id == manifest_v1_id
        assert manifests[0].manifest_hash == manifest_v1_hash
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_reject_is_tenant_scoped_and_cross_tenant_case_id_is_invisible():
    from app.models import ArchiveManifest, PostArchiveCorrectionCase
    from app.modules.academic_affairs.services import academic_affairs_archive_correction_review_service as review
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    creator = _user(42001, "stage_c3_tenant_creator")
    outsider = _user(42002, "stage_c3_other_tenant_reviewer")
    _activate(creator)
    batch_id, grade_id, _manifest_id, _manifest_hash = _seed_grade_archive()
    created = _create_case(service, creator, batch_id, grade_id)
    case_id = int(created["caseId"])

    _activate(outsider, TID + 1)
    with pytest.raises(AppException):
        review.get_correction_case(outsider, case_id)
    with pytest.raises(AppException):
        review.reject_correction_case(outsider, case_id, reason="跨租户不得访问或驳回该纠错申请")

    _activate(creator)
    db = get_sessionmaker()()
    try:
        case = db.query(PostArchiveCorrectionCase).filter(
            PostArchiveCorrectionCase.id == case_id,
            PostArchiveCorrectionCase.tenant_id == TID,
        ).one()
        manifests = db.query(ArchiveManifest).filter(
            ArchiveManifest.tenant_id == TID,
            ArchiveManifest.archive_batch_id == batch_id,
        ).all()
        assert case.status == "PENDING_SECOND_APPROVAL"
        assert case.rejected_by is None and case.reject_reason is None
        assert len(manifests) == 1
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_competing_approve_and_reject_are_serialized_to_one_terminal_decision():
    """SELECT FOR UPDATE makes approve-vs-reject a single-winner state transition."""
    from app.models import AcademicGrade, ArchiveManifest, PostArchiveCorrectionCase
    from app.modules.academic_affairs.services import academic_affairs_archive_correction_review_service as review
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    creator = _user(43001, "stage_c3_concurrent_creator")
    approver = _user(43002, "stage_c3_concurrent_approver")
    rejecter = _user(43003, "stage_c3_concurrent_rejecter")
    _activate(creator)
    batch_id, old_grade_id, _manifest_id, _manifest_hash = _seed_grade_archive()
    created = _create_case(service, creator, batch_id, old_grade_id)
    case_id = int(created["caseId"])
    barrier = Barrier(2)

    def approve_worker():
        _activate(approver)
        barrier.wait(timeout=10)
        try:
            return ("APPROVE", service.approve_correction_case(approver, case_id)["status"])
        except AppException as exc:
            return ("APPROVE_ERROR", exc.code)
        finally:
            set_current_user(None)
            set_tenant(None)

    def reject_worker():
        _activate(rejecter)
        barrier.wait(timeout=10)
        try:
            return (
                "REJECT",
                review.reject_correction_case(
                    rejecter,
                    case_id,
                    reason="并发二审竞争：本复核人决定驳回且不得覆盖另一终态",
                )["status"],
            )
        except AppException as exc:
            return ("REJECT_ERROR", exc.code)
        finally:
            set_current_user(None)
            set_tenant(None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        approve_future = pool.submit(approve_worker)
        reject_future = pool.submit(reject_worker)
        results = [approve_future.result(timeout=30), reject_future.result(timeout=30)]

    terminal = [result for result in results if result[1] in {"APPLIED", "REJECTED"}]
    conflicts = [result for result in results if result[1] == "APPROVAL_VERSION_CONFLICT"]
    assert len(terminal) == 1, results
    assert len(conflicts) == 1, results

    _activate(approver)
    db = get_sessionmaker()()
    try:
        case = db.get(PostArchiveCorrectionCase, case_id)
        old_grade = db.get(AcademicGrade, old_grade_id)
        grades = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == TID,
            AcademicGrade.acad_student_id == old_grade.acad_student_id,
        ).order_by(AcademicGrade.id).all()
        manifests = db.query(ArchiveManifest).filter(
            ArchiveManifest.tenant_id == TID,
            ArchiveManifest.archive_batch_id == batch_id,
        ).order_by(ArchiveManifest.version_no).all()

        assert case.status in {"APPLIED", "REJECTED"}
        if case.status == "APPLIED":
            assert case.second_approved_by == 43002
            assert case.rejected_by is None and case.reject_reason is None
            assert case.official_fact_id is not None and case.resulting_manifest_id is not None
            assert len(grades) == 2
            assert len(manifests) == 2
            assert manifests[1].supersedes_id == manifests[0].id
        else:
            assert case.rejected_by == 43003 and case.reject_reason
            assert case.second_approved_by is None and case.official_fact_id is None
            assert case.resulting_manifest_id is None
            assert len(grades) == 1 and grades[0].record_status == "ACTIVE"
            assert len(manifests) == 1
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)
