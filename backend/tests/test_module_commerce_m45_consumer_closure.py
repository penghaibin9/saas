from __future__ import annotations

import pytest

from app.core.exceptions import AppException

BASE = 1000000000000028000


def _seed_state(tid: int, module: str):
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig, Tenant, TenantModuleState

    db = get_sessionmaker()()
    try:
        db.add(Tenant(
            id=tid, tenant_code=f"m45-evidence-{tid}", school_name=f"M45Evidence-{tid}",
            deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE",
        ))
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


def test_m45_shared_consumer_objects_are_counted_by_explicit_module_ownership(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.approval import UnifiedTodo, WorkflowInstance, WorkflowTask
    from app.models.file import FileBinding, FileObject
    from app.models.message import (
        MessageCampaign, MessageChannelDelivery, MessageDeliveryJob,
        MessageEventOutbox, UnifiedMessage,
    )
    from app.services import module_commerce_lifecycle_service as lifecycle

    tid = BASE + 1
    _seed_state(tid, "internship")
    db = get_sessionmaker()()
    try:
        workflow = WorkflowInstance(
            tenant_id=tid, workflow_code="M45-INTERN-WF", source_module="INTERNSHIP",
            source_biz_type="INTERNSHIP_RECORD", source_biz_id=8001,
            applicant_id=7001, title="实习退出前共享审批", status="RUNNING",
        )
        db.add(workflow)
        db.flush()
        db.add(WorkflowTask(
            tenant_id=tid, instance_id=int(workflow.id), assignee_id=7002,
            node_code="REVIEW", status="PENDING",
        ))
        db.add(UnifiedTodo(
            tenant_id=tid, source_module="internship", source_biz_type="INTERNSHIP_RECORD",
            source_biz_id=8001, todo_type="REVIEW", assignee_id=7002,
            title="实习待办", status="PENDING",
        ))
        db.add(UnifiedMessage(
            tenant_id=tid, receiver_id=7001, receiver_user_id=7001,
            receiver_context_key="GLOBAL", source_module="internship", source_biz_id=8001,
            title="实习消息", content="退出交付消费者证据", status="UNREAD",
        ))
        campaign = MessageCampaign(
            tenant_id=tid, title="实习异步通知", content_plain="消费者证据",
            source_module="internship", source_biz_type="INTERNSHIP_RECORD", source_biz_id=8001,
            sender_user_id=7002, status="SCHEDULED",
        )
        db.add(campaign)
        db.flush()
        db.add(MessageDeliveryJob(
            tenant_id=tid, campaign_id=int(campaign.id), cursor_start=0,
            status="PENDING",
        ))
        db.add(MessageChannelDelivery(
            tenant_id=tid, campaign_id=int(campaign.id), channel="SMS",
            receiver_user_id=7001, status="PENDING",
        ))
        db.add(MessageEventOutbox(
            tenant_id=tid, event_code="INTERNSHIP.M45_EVIDENCE",
            source_module="internship", source_biz_type="INTERNSHIP_RECORD",
            source_biz_id=8001, dedup_key=f"m45:{tid}:8001", status="PENDING",
        ))
        file_row = FileObject(
            tenant_id=tid, file_key=f"m45/{tid}/evidence.pdf", file_name="实习证明.pdf",
            ext="pdf", mime_type="application/pdf", size_bytes=128, sha256="a" * 64,
            biz_type="INTERNSHIP_RECORD", biz_id="8001", visibility="PRIVATE",
            security_level="NORMAL", status="AVAILABLE", storage_backend="local",
            storage_zone="ACTIVE", upload_source="SYSTEM", scan_required=False,
            scan_status="NOT_REQUIRED",
        )
        db.add(file_row)
        db.flush()
        db.add(FileBinding(
            tenant_id=tid, file_id=int(file_row.id), biz_type="INTERNSHIP_RECORD",
            biz_id="8001", relation_type="ATTACHMENT", subject_type="BUSINESS_OBJECT",
            is_current=True, status="ACTIVE", module_code="internship",
        ))
        db.commit()
    finally:
        db.close()

    preview = lifecycle.preview_module_offboarding(tid, "internship")
    dep = preview["consumerDependencies"]
    evidence = dep["objectEvidence"]
    counts = evidence["sharedObjectCounts"]
    unsettled = evidence["unsettledSharedObjectCounts"]

    assert preview["canRequest"] is True
    assert preview["physicalPurgeAuthorized"] is False
    assert dep["disposition"] == "SHARED_CONSUMER_EVIDENCE_RETAIN_REQUIRED"
    assert dep["consumerPurgeReady"] is False
    assert dep["requiresIndependentConsumerEvidence"] is True
    assert evidence["ownershipGuessingUsed"] is False
    assert counts["workflowInstances"] == 1
    assert counts["workflowTasks"] == 1
    assert counts["todos"] == 1
    assert counts["messages"] == 1
    assert counts["messageCampaigns"] == 1
    assert counts["messageOutbox"] == 1
    assert counts["messageDeliveryJobs"] == 1
    assert counts["messageChannelDeliveries"] == 1
    assert counts["fileBindings"] == 1
    assert counts["distinctBoundFiles"] == 1
    assert unsettled["runningWorkflowInstances"] == 1
    assert unsettled["pendingWorkflowTasks"] == 1
    assert unsettled["pendingTodos"] == 1
    assert unsettled["unsettledMessageOutbox"] == 1
    assert evidence["hasUnsettledSharedObjects"] is True
    assert len(evidence["objectEvidenceDigest"]) == 64
    assert len(dep["dependencyDigest"]) == 64


def test_m45_student_affairs_uses_real_archive_facts_instead_of_empty_placeholder(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.affairs_archive import ArchiveBatch, ArchivePackage
    from app.services import module_commerce_lifecycle_service as lifecycle

    tid = BASE + 2
    _seed_state(tid, "studentAffairs")
    db = get_sessionmaker()()
    try:
        batch = ArchiveBatch(
            tenant_id=tid, batch_name="2026届学工正式归档", year_code="2026",
            status="ARCHIVED",
        )
        db.add(batch)
        db.flush()
        db.add(ArchivePackage(
            tenant_id=tid, batch_id=int(batch.id), student_id=9001,
            status="ARCHIVED", package_file_id=99001,
        ))
        db.commit()
    finally:
        db.close()

    preview = lifecycle.preview_module_offboarding(tid, "studentAffairs")
    dep = preview["consumerDependencies"]
    assert dep["sourceCounts"]["archiveBatches"] == 1
    assert dep["sourceCounts"]["archivedBatches"] == 1
    assert dep["sourceCounts"]["archivePackages"] == 1
    assert dep["sourceCounts"]["archivedPackages"] == 1
    assert dep["sourceCounts"]["generatedPackageFiles"] == 1
    assert dep["disposition"] == "SOURCE_BOUND_EVIDENCE_RETAIN_REQUIRED"
    assert dep["consumerPurgeReady"] is False
    assert preview["physicalPurgeAuthorized"] is False


def test_m45_academic_uses_real_formal_grade_facts_and_keeps_them_retain_required(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.academic import AcademicGrade, AcademicStudent
    from app.services import module_commerce_lifecycle_service as lifecycle

    tid = BASE + 3
    _seed_state(tid, "academicAffairs")
    db = get_sessionmaker()()
    try:
        student = AcademicStudent(
            tenant_id=tid, student_no="M45-AA-001", student_id=9101,
            name="教务消费者证据学生", academic_status="NORMAL", record_status="ACTIVE",
        )
        db.add(student)
        db.flush()
        db.add(AcademicGrade(
            tenant_id=tid, acad_student_id=int(student.id), course_name="职业素养",
            term="2026-1", credit_value=2, score=88, pass_status="PASSED",
            record_status="ACTIVE", source="PUBLISH",
        ))
        db.commit()
    finally:
        db.close()

    preview = lifecycle.preview_module_offboarding(tid, "academicAffairs")
    dep = preview["consumerDependencies"]
    assert dep["sourceCounts"]["academicStudents"] == 1
    assert dep["sourceCounts"]["formalGrades"] == 1
    assert dep["sourceCounts"]["activeGrades"] == 1
    assert dep["sourceCounts"]["passedActiveGrades"] == 1
    assert dep["disposition"] == "FORMAL_ACADEMIC_FACTS_RETAIN_REQUIRED"
    assert dep["consumerPurgeReady"] is False
    assert dep["requiresIndependentConsumerEvidence"] is True
    assert preview["physicalPurgeAuthorized"] is False


def _base_dependency() -> dict:
    return {
        "tenantId": "1", "moduleKey": "internship",
        "consumers": ["DEPARTURE", "ACADEMIC_GRADUATION_QUALIFICATION"],
        "sourceCounts": {}, "disposition": "NO_SOURCE_CONSUMER_FACTS_FOUND",
        "consumerPurgeReady": True, "requiresIndependentConsumerEvidence": False,
        "reviewStage": "M6_M7_BEFORE_PURGE", "message": "none",
        "dependencyDigest": "0" * 64, "capturedAt": "2026-09-09T00:00:00",
    }


def _evidence(todo_count: int) -> dict:
    stable = {
        "authority": "EXPLICIT_SOURCE_MODULE_OR_DOMAIN_TABLE",
        "moduleAliases": ["internship"],
        "sharedObjectCounts": {"todos": todo_count},
        "unsettledSharedObjectCounts": {"pendingTodos": todo_count},
        "domainFactCounts": {},
        "hasOwnedSharedObjects": todo_count > 0,
        "hasUnsettledSharedObjects": todo_count > 0,
        "hasDomainFacts": False,
        "ownershipGuessingUsed": False,
    }
    import hashlib, json
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**stable, "objectEvidenceDigest": hashlib.sha256(raw.encode("utf-8")).hexdigest()}


def test_m45_bound_consumer_snapshot_rejects_object_drift_before_school_acceptance():
    from app.services.module_commerce_m45_consumer_closure import (
        assert_bound_snapshot_current,
        enrich_dependency_snapshot,
    )

    bound = enrich_dependency_snapshot(_base_dependency(), _evidence(1))
    same = enrich_dependency_snapshot(_base_dependency(), _evidence(1))
    assert_bound_snapshot_current(bound, same)

    changed = enrich_dependency_snapshot(_base_dependency(), _evidence(2))
    with pytest.raises(AppException) as caught:
        assert_bound_snapshot_current(bound, changed)
    assert caught.value.http_status == 409
    assert caught.value.details["reasonCode"] == "CONSUMER_DEPENDENCY_CHANGED"
    assert caught.value.details["changedEvidence"]["sharedObjectCounts"]["todos"] == {
        "bound": 1, "current": 2,
    }


def test_m45_lifecycle_installer_is_active_and_never_exposes_purge_execution():
    from app.services import module_commerce_lifecycle_service as lifecycle

    assert lifecycle._m45_consumer_closure_installed is True
    source = __import__("pathlib").Path("app/services/module_commerce_m45_consumer_closure.py").read_text(encoding="utf-8")
    assert "physicalPurgeAuthorized\"] = False" in source
    for forbidden in ("execute_tenant_purge", "_purge_file_objects", "session.delete(", "db.delete("):
        assert forbidden not in source
