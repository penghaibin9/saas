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
    from app.models import GraduationArchiveRecord, GraduationGrade, GraduationStudent
    from app.services import module_commerce_lifecycle_service as lifecycle

    tid = BASE + 2
    _seed_state(tid, "graduationDesign")
    db = get_sessionmaker()()
    try:
        # This test exercises the M5 consumer-dependency reader, not the package-9
        # archival writer. Seed one real graduation student and already-persisted
        # upstream facts at table level so immutable archive-version creation stays
        # under its own dedicated regression suite rather than being bypassed or
        # accidentally re-entered here.
        db.add(GraduationStudent(
            id=9101,
            tenant_id=tid,
            student_id=8101,
            student_no="M5GD9101",
            name="M5 Consumer Student",
        ))
        db.flush()
        db.execute(GraduationGrade.__table__.insert().values(
            tenant_id=tid, gd_student_id=9101, total_score=88, grade_level="良好",
            status="PUBLISHED", published_at=datetime.utcnow(), source_snapshot_hash="a" * 64,
        ))
        db.execute(GraduationArchiveRecord.__table__.insert().values(
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


def test_m6_readonly_preflight_never_authorizes_physical_purge(db_mode):
    from datetime import timedelta
    import importlib

    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models import TenantModuleOffboardingJob, TenantModuleState

    tid = BASE + 6
    _seed_state(tid, "internship")
    db = get_sessionmaker()()
    try:
        state = db.scalars(select(TenantModuleState).where(
            TenantModuleState.tenant_id == tid,
            TenantModuleState.module_key == "internship",
        )).one()
        state.data_state = "RETAINED"
        state.lifecycle_version = 2
        job = TenantModuleOffboardingJob(
            tenant_id=tid,
            module_key="internship",
            module_generation=1,
            state="RETENTION",
            expected_lifecycle_version=1,
            reason="M6只读销毁预演测试，不执行任何删除",
            requested_at=datetime.utcnow() - timedelta(days=31),
            retention_days=30,
            retention_policy_version="TEST-RETENTION-1",
            retention_until=datetime.utcnow() - timedelta(days=1),
            scope_hash="c" * 64,
            acceptance_ref="SCHOOL-M6-001",
            accepted_at=datetime.utcnow() - timedelta(days=30),
            result_json={"physicalPurgeAuthorized": False},
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = int(job.id)
    finally:
        db.close()

    preflight_service = importlib.import_module("app.services.module_commerce_m6_preflight")
    preview = preflight_service.preview_module_purge(job_id)

    assert preview["dryRunOnly"] is True
    assert preview["destructiveExecutionAvailable"] is False
    assert preview["physicalPurgeAuthorized"] is False
    assert preview["deletionAuthorized"] is False
    assert preview["canExecutePhysicalPurge"] is False
    assert preview["destructiveStatements"] == []
    assert preview["fullResourceClosureComplete"] is False
    assert len(preview["preflightDigest"]) == 64
    blocker_codes = {row["code"] for row in preview["blockers"]}
    assert "M0_FULL_RESOURCE_CLOSURE_REQUIRED" in blocker_codes
    assert "MODULE_PURGE_EXECUTION_DISABLED" in blocker_codes
    assert "BACKUP_DISPOSITION_POLICY_REQUIRED" in blocker_codes
    assert "VERIFIED_EXPORT_EVIDENCE_MISSING" in blocker_codes
    assert all(row["purgeAuthorized"] is False for row in preview["sharedFoundation"])


def test_m6_table_inventory_is_discovery_only_and_fail_closed(db_mode):
    import importlib

    preflight_service = importlib.import_module("app.services.module_commerce_m6_preflight")
    for module in ("internship", "graduationDesign", "studentAffairs", "academicAffairs"):
        inventory = preflight_service.module_table_inventory(module)
        assert inventory["registryVersion"] == preflight_service.REGISTRY_VERSION
        assert inventory["metadataOnly"] is True
        assert inventory["sqlOnlyAndDynamicResourcesIncluded"] is False
        assert inventory["fullResourceClosureComplete"] is False
        assert inventory["deletionAuthorized"] is False
        assert len(inventory["inventoryDigest"]) == 64
        assert all(row["purgeAuthorized"] is False for row in inventory["candidateTables"])


def test_m6_preflight_source_contains_no_destructive_primitive():
    from pathlib import Path

    source = Path("app/services/module_commerce_m6_preflight.py").read_text(encoding="utf-8")
    forbidden = (
        "sqlalchemy import delete",
        "session.delete(",
        "db.delete(",
        "backend.delete(",
        "execute_tenant_purge",
        "_purge_file_objects",
    )
    for marker in forbidden:
        assert marker not in source
