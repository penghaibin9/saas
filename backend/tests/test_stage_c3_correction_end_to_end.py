"""Stage C3 post-archive correction end-to-end production contracts.

These tests exercise the public Stage C3 service boundary, not only the lower-level
fact helper: creator -> different second approver -> official grade fact -> Manifest V2
-> verification/list/detail. They also prove same-person approval leaves V1 and the old
official grade untouched.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

TID = 98115
TERM_CODE = "2098-2099-2"


def _user(user_id: int, login: str) -> dict:
    return {
        "userId": str(user_id),
        "loginName": login,
        "realName": login,
        "userType": "SCHOOL_ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
    }


def _activate(user: dict):
    set_tenant({"tenantId": str(TID), "tenantCode": "stage-c3-e2e"})
    set_current_user(user)


def _seed_grade_archive():
    from app.models import AaArchiveBatch, AcademicGrade, AcademicStudent, ArchiveManifest
    from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as manifest_service

    db = get_sessionmaker()()
    try:
        academic = AcademicStudent(
            tenant_id=TID,
            student_no="C3E2E001",
            name="归档纠错集成甲",
            obtained_credits=0,
        )
        db.add(academic)
        db.flush()
        grade = AcademicGrade(
            tenant_id=TID,
            acad_student_id=academic.id,
            course_name="离散数学",
            term=TERM_CODE,
            nature="REQUIRED",
            credit_value=3,
            score=58,
            pass_status="FAILED",
            exam_type="FINAL",
            record_status="ACTIVE",
            source="PUBLISH",
            course_code="CS2098",
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
            batch_name="Stage C3 E2E 归档",
            term_id=None,
            term_code=TERM_CODE,
            status="ARCHIVED",
            archived_at=datetime.utcnow(),
        )
        db.add(batch)
        db.flush()
        counts = {"GRADE": 1}
        hashes = {"GRADE": "a" * 64}
        max_ids = {"GRADE": int(grade.id)}
        reason = "正式归档：Stage C3 集成测试基线"
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
            archived_by=9001,
            created_by=9001,
        )
        db.add(manifest)
        db.commit()
        return int(batch.id), int(grade.id), int(manifest.id)
    finally:
        db.close()


def _create_case(service, creator: dict, batch_id: int, grade_id: int):
    _activate(creator)
    return service.create_correction_case(
        creator,
        batch_id,
        business_type="GRADE",
        target_ref=str(grade_id),
        reason="原卷复核确认录入错误，按卷面成绩更正",
        correction={"score": 65},
        evidence_manifest={"kind": "PAPER_REVIEW", "sha256": "e" * 64},
        risk_level="HIGH",
    )


@pytest.mark.usefixtures("db_mode")
def test_post_archive_grade_correction_public_flow_appends_fact_and_manifest_v2():
    from app.models import AaArchiveBatch, AcademicGrade, ArchiveManifest, PostArchiveCorrectionCase
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    creator = _user(31001, "stage_c3_creator")
    reviewer = _user(31002, "stage_c3_reviewer")
    _activate(creator)
    batch_id, old_grade_id, manifest_v1_id = _seed_grade_archive()

    created = _create_case(service, creator, batch_id, old_grade_id)
    assert created["status"] == "PENDING_SECOND_APPROVAL"
    case_id = int(created["caseId"])

    _activate(reviewer)
    applied = service.approve_correction_case(reviewer, case_id)
    assert applied["status"] == "APPLIED"
    assert applied["officialFactType"] == "ACADEMIC_GRADE"
    assert applied["manifestVersion"] == 2
    assert int(applied["supersedesId"]) == manifest_v1_id
    new_grade_id = int(applied["officialFactId"])
    assert new_grade_id != old_grade_id

    verified = service.verify_manifest(reviewer, batch_id)
    assert verified["ok"] is True
    assert verified["appliedCorrections"] == 1
    assert [row["versionNo"] for row in verified["versions"]] == [1, 2]

    queue = service.list_correction_cases(
        reviewer, batch_id, status="APPLIED", page=1, page_size=20
    )
    assert queue["total"] == 1
    assert queue["items"][0]["officialFactId"] == str(new_grade_id)
    detail = service.get_correction_case(reviewer, case_id)
    assert detail["correction"] == {"score": 65}
    assert detail["evidenceManifest"]["kind"] == "PAPER_REVIEW"

    db = get_sessionmaker()()
    try:
        old = db.get(AcademicGrade, old_grade_id)
        new = db.get(AcademicGrade, new_grade_id)
        case = db.get(PostArchiveCorrectionCase, case_id)
        batch = db.get(AaArchiveBatch, batch_id)
        manifests = db.query(ArchiveManifest).filter(
            ArchiveManifest.tenant_id == TID,
            ArchiveManifest.archive_batch_id == batch_id,
        ).order_by(ArchiveManifest.version_no).all()
        assert old.record_status == "SUPERSEDED" and old.score == 58
        assert new.record_status == "ACTIVE" and new.score == 65 and new.pass_status == "PASSED"
        assert new.source_biz_type == "POST_ARCHIVE" and new.source_biz_id == case_id
        assert case.created_by == 31001 and case.second_approved_by == 31002
        assert case.official_fact_type == "ACADEMIC_GRADE" and case.official_fact_id == new_grade_id
        assert batch.status == "ARCHIVED"
        assert len(manifests) == 2 and manifests[1].supersedes_id == manifests[0].id
        assert manifests[0].id == manifest_v1_id
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_post_archive_same_person_second_approval_is_fail_closed_and_creates_nothing():
    from app.models import AcademicGrade, ArchiveManifest, PostArchiveCorrectionCase
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    creator = _user(32001, "stage_c3_same_actor")
    _activate(creator)
    batch_id, old_grade_id, _manifest_v1_id = _seed_grade_archive()
    created = _create_case(service, creator, batch_id, old_grade_id)
    case_id = int(created["caseId"])

    _activate(creator)
    with pytest.raises(AppException) as exc:
        service.approve_correction_case(creator, case_id)
    assert exc.value.code == "NO_PERMISSION"

    db = get_sessionmaker()()
    try:
        case = db.get(PostArchiveCorrectionCase, case_id)
        grades = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == TID,
            AcademicGrade.acad_student_id == db.get(AcademicGrade, old_grade_id).acad_student_id,
        ).all()
        manifests = db.query(ArchiveManifest).filter(
            ArchiveManifest.tenant_id == TID,
            ArchiveManifest.archive_batch_id == batch_id,
        ).all()
        assert case.status == "PENDING_SECOND_APPROVAL"
        assert case.second_approved_by is None and case.official_fact_id is None
        assert len(grades) == 1 and grades[0].id == old_grade_id and grades[0].record_status == "ACTIVE"
        assert len(manifests) == 1 and manifests[0].version_no == 1
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)
