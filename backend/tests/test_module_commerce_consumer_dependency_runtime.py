from __future__ import annotations

from datetime import datetime

import pytest

BASE = 1000000000000025000


def _seed_state(tid: int, module: str):
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig, Tenant, TenantModuleState
    db = get_sessionmaker()()
    try:
        db.add(Tenant(id=tid, tenant_code=f"m5-consumer-{tid}", school_name=f"M5Consumer-{tid}",
                      deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE"))
        db.add(PlatformConfig(
            tenant_id=tid, config_type="TENANT_META", config_key="-",
            config_json={"status": "active", "packageCode": "module-v2", "environment": "test"},
            enabled=True, status="ACTIVE",
        ))
        db.add(TenantModuleState(
            tenant_id=tid, module_key=module, generation=1, lifecycle_version=1,
            data_state="AVAILABLE",
        ))
        db.commit()
    finally:
        db.close()


def test_m5_internship_preview_marks_departure_and_academic_source_evidence_retain_required(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipArchive, InternshipFinalScore
    from app.services import module_commerce_lifecycle_service as lifecycle

    tid = BASE + 1
    _seed_state(tid, "internship")
    db = get_sessionmaker()()
    try:
        db.add(InternshipFinalScore(
            tenant_id=tid, internship_id=9001, student_id=8001, batch_id=7001,
            total_score=82, pass_line=60, is_pass=True, incomplete=False,
            status="PUBLISHED", published_at=datetime.utcnow(),
        ))
        db.add(InternshipArchive(
            tenant_id=tid, internship_id=9001, student_id=8001, batch_id=7001,
            completeness=100, status="ARCHIVED", archived_at=datetime.utcnow(),
        ))
        db.commit()
    finally:
        db.close()

    preview = lifecycle.preview_module_offboarding(tid, "internship")
    dep = preview["consumerDependencies"]
    assert preview["canRequest"] is True
    assert preview["physicalPurgeAuthorized"] is False
    assert dep["disposition"] == "SOURCE_BOUND_EVIDENCE_RETAIN_REQUIRED"
    assert dep["consumerPurgeReady"] is False
    assert dep["sourceCounts"]["publishedFinalScores"] == 1
    assert dep["sourceCounts"]["validArchives"] == 1
    assert set(dep["consumers"]) == {"DEPARTURE", "ACADEMIC_GRADUATION_QUALIFICATION"}
    assert preview["purgeBlockers"][0]["code"] == "CONSUMER_DEPENDENCY_NOT_DISPOSED"
    assert len(dep["dependencyDigest"]) == 64


def test_m5_graduation_preview_marks_published_grade_and_filed_archive_as_consumer_bound(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationArchiveRecord, GraduationGrade
    from app.services import module_commerce_lifecycle_service as lifecycle

    tid = BASE + 2
    _seed_state(tid, "graduationDesign")
    db = get_sessionmaker()()
    try:
        db.add(GraduationGrade(
            tenant_id=tid, gd_student_id=9101, total_score=88, grade_level="良好",
            status="PUBLISHED", published_at=datetime.utcnow(), source_snapshot_hash="a" * 64,
        ))
        db.add(GraduationArchiveRecord(
            tenant_id=tid, gd_student_id=9101, status="FILED", filed_at=datetime.utcnow(),
            manifest_hash="b" * 64,
        ))
        db.commit()
    finally:
        db.close()

    preview = lifecycle.preview_module_offboarding(tid, "graduationDesign")
    dep = preview["consumerDependencies"]
    assert preview["canRequest"] is True
    assert dep["disposition"] == "SOURCE_BOUND_EVIDENCE_RETAIN_REQUIRED"
    assert dep["sourceCounts"]["publishedGrades"] == 1
    assert dep["sourceCounts"]["filedArchives"] == 1
    assert dep["requiresIndependentConsumerEvidence"] is True
    assert dep["consumerPurgeReady"] is False


def test_m5_incomplete_internship_process_is_not_downgraded_to_never_required(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipFinalScore
    from app.services import module_commerce_lifecycle_service as lifecycle

    tid = BASE + 3
    _seed_state(tid, "internship")
    db = get_sessionmaker()()
    try:
        db.add(InternshipFinalScore(
            tenant_id=tid, internship_id=9201, student_id=8201,
            incomplete=True, incomplete_reason="企业评价待补", status="PENDING_REVIEW",
        ))
        db.commit()
    finally:
        db.close()
    dep = lifecycle.preview_module_offboarding(tid, "internship")["consumerDependencies"]
    assert dep["disposition"] == "SOURCE_PROCESS_UNRESOLVED"
    assert dep["consumerPurgeReady"] is False
    assert dep["sourceCounts"]["finalScores"] == 1


@pytest.mark.parametrize(
    ("module", "expected", "consumers"),
    [
        ("studentAffairs", "MODULE_RESOURCE_REVIEW_REQUIRED", {"DEPARTURE", "SHARED_STUDENT_FOUNDATION", "APPROVAL_TODO_MESSAGE"}),
        ("academicAffairs", "FORMAL_ACADEMIC_FACTS_RETAIN_REVIEW_REQUIRED", {"GRADUATION_QUALIFICATION", "TRANSCRIPT_ARCHIVE", "DEPARTURE"}),
    ],
)
def test_m5_student_affairs_and_academic_stay_fail_closed_for_future_purge(db_mode, module, expected, consumers):
    from app.services import module_commerce_lifecycle_service as lifecycle
    tid = BASE + (4 if module == "studentAffairs" else 5)
    _seed_state(tid, module)
    preview = lifecycle.preview_module_offboarding(tid, module)
    dep = preview["consumerDependencies"]
    assert preview["canRequest"] is True
    assert preview["physicalPurgeAuthorized"] is False
    assert dep["disposition"] == expected
    assert dep["consumerPurgeReady"] is False
    assert dep["reviewStage"] == "M6_M7_BEFORE_PURGE"
    assert set(dep["consumers"]) == consumers
    assert preview["purgeBlockers"][0]["code"] == "CONSUMER_DEPENDENCY_NOT_DISPOSED"
