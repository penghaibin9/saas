"""Read-only M4/M5 consumer-object evidence for module offboarding.

The commerce lifecycle owns no approval, message, file, student-affairs or academic
facts.  This module therefore only inventories rows that already carry an explicit
module ownership field, plus formal domain facts whose table itself is authoritative.
It never guesses ownership from titles, URLs or menu placement and never mutates the
consumer tables.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import func, select


# Historical producers are not fully normalized.  Matching is intentionally limited
# to reviewed aliases that are written into explicit source_module/module_code fields.
# lower() makes legacy upper-case writes equivalent without broad substring matching.
MODULE_SOURCE_ALIASES: dict[str, tuple[str, ...]] = {
    "internship": ("internship",),
    "graduationDesign": ("graduation", "graduationdesign", "graduation_design", "gd"),
    "studentAffairs": ("studentaffairs", "student_affairs", "student-affairs", "affairs", "sa"),
    "academicAffairs": ("academicaffairs", "academic_affairs", "academic-affairs", "academic", "aa"),
}


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _count(db, model, *filters) -> int:
    return int(db.scalar(select(func.count(model.id)).where(*filters)) or 0)


def _module_filter(column, module_key: str):
    aliases = MODULE_SOURCE_ALIASES.get(str(module_key), (str(module_key).lower(),))
    return func.lower(column).in_(aliases)


def _shared_object_counts(db, tenant_id: int, module_key: str) -> tuple[dict[str, int], dict[str, int]]:
    """Count only shared rows with an explicit module source/ownership field."""
    from app.models.approval import UnifiedTodo, WorkflowInstance, WorkflowTask
    from app.models.file import FileBinding
    from app.models.message import (
        MessageCampaign,
        MessageChannelDelivery,
        MessageDeliveryJob,
        MessageEventOutbox,
        UnifiedMessage,
    )

    tid = int(tenant_id)
    workflow_filter = _module_filter(WorkflowInstance.source_module, module_key)
    campaign_filter = _module_filter(MessageCampaign.source_module, module_key)

    counts = {
        "workflowInstances": _count(
            db, WorkflowInstance,
            WorkflowInstance.tenant_id == tid,
            workflow_filter,
            WorkflowInstance.is_deleted.is_(False),
        ),
        "workflowTasks": int(db.scalar(
            select(func.count(WorkflowTask.id))
            .select_from(WorkflowTask)
            .join(
                WorkflowInstance,
                (WorkflowInstance.id == WorkflowTask.instance_id)
                & (WorkflowInstance.tenant_id == WorkflowTask.tenant_id),
            )
            .where(
                WorkflowTask.tenant_id == tid,
                workflow_filter,
                WorkflowTask.is_deleted.is_(False),
                WorkflowInstance.is_deleted.is_(False),
            )
        ) or 0),
        "todos": _count(
            db, UnifiedTodo,
            UnifiedTodo.tenant_id == tid,
            _module_filter(UnifiedTodo.source_module, module_key),
            UnifiedTodo.is_deleted.is_(False),
        ),
        "messages": _count(
            db, UnifiedMessage,
            UnifiedMessage.tenant_id == tid,
            _module_filter(UnifiedMessage.source_module, module_key),
            UnifiedMessage.is_deleted.is_(False),
        ),
        "messageCampaigns": _count(
            db, MessageCampaign,
            MessageCampaign.tenant_id == tid,
            campaign_filter,
            MessageCampaign.is_deleted.is_(False),
        ),
        "messageOutbox": _count(
            db, MessageEventOutbox,
            MessageEventOutbox.tenant_id == tid,
            _module_filter(MessageEventOutbox.source_module, module_key),
            MessageEventOutbox.is_deleted.is_(False),
        ),
        "messageDeliveryJobs": int(db.scalar(
            select(func.count(MessageDeliveryJob.id))
            .select_from(MessageDeliveryJob)
            .join(
                MessageCampaign,
                (MessageCampaign.id == MessageDeliveryJob.campaign_id)
                & (MessageCampaign.tenant_id == MessageDeliveryJob.tenant_id),
            )
            .where(
                MessageDeliveryJob.tenant_id == tid,
                campaign_filter,
                MessageDeliveryJob.is_deleted.is_(False),
                MessageCampaign.is_deleted.is_(False),
            )
        ) or 0),
        "messageChannelDeliveries": int(db.scalar(
            select(func.count(MessageChannelDelivery.id))
            .select_from(MessageChannelDelivery)
            .join(
                MessageCampaign,
                (MessageCampaign.id == MessageChannelDelivery.campaign_id)
                & (MessageCampaign.tenant_id == MessageChannelDelivery.tenant_id),
            )
            .where(
                MessageChannelDelivery.tenant_id == tid,
                campaign_filter,
                MessageChannelDelivery.is_deleted.is_(False),
                MessageCampaign.is_deleted.is_(False),
            )
        ) or 0),
        "fileBindings": _count(
            db, FileBinding,
            FileBinding.tenant_id == tid,
            _module_filter(FileBinding.module_code, module_key),
            FileBinding.is_current.is_(True),
            FileBinding.status == "ACTIVE",
            FileBinding.is_deleted.is_(False),
        ),
        "distinctBoundFiles": int(db.scalar(
            select(func.count(func.distinct(FileBinding.file_id))).where(
                FileBinding.tenant_id == tid,
                _module_filter(FileBinding.module_code, module_key),
                FileBinding.is_current.is_(True),
                FileBinding.status == "ACTIVE",
                FileBinding.is_deleted.is_(False),
            )
        ) or 0),
    }

    unsettled = {
        "runningWorkflowInstances": _count(
            db, WorkflowInstance,
            WorkflowInstance.tenant_id == tid,
            workflow_filter,
            WorkflowInstance.status == "RUNNING",
            WorkflowInstance.is_deleted.is_(False),
        ),
        "pendingWorkflowTasks": int(db.scalar(
            select(func.count(WorkflowTask.id))
            .select_from(WorkflowTask)
            .join(
                WorkflowInstance,
                (WorkflowInstance.id == WorkflowTask.instance_id)
                & (WorkflowInstance.tenant_id == WorkflowTask.tenant_id),
            )
            .where(
                WorkflowTask.tenant_id == tid,
                workflow_filter,
                WorkflowTask.status == "PENDING",
                WorkflowTask.is_deleted.is_(False),
                WorkflowInstance.is_deleted.is_(False),
            )
        ) or 0),
        "pendingTodos": _count(
            db, UnifiedTodo,
            UnifiedTodo.tenant_id == tid,
            _module_filter(UnifiedTodo.source_module, module_key),
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.is_deleted.is_(False),
        ),
        "unfinishedMessageCampaigns": _count(
            db, MessageCampaign,
            MessageCampaign.tenant_id == tid,
            campaign_filter,
            ~MessageCampaign.status.in_(("PUBLISHED", "WITHDRAWN", "EXPIRED", "REJECTED")),
            MessageCampaign.is_deleted.is_(False),
        ),
        "unsettledMessageOutbox": _count(
            db, MessageEventOutbox,
            MessageEventOutbox.tenant_id == tid,
            _module_filter(MessageEventOutbox.source_module, module_key),
            MessageEventOutbox.status.in_(("PENDING", "PROCESSING", "RETRY_WAIT", "DEAD")),
            MessageEventOutbox.is_deleted.is_(False),
        ),
        "unsettledMessageDeliveryJobs": int(db.scalar(
            select(func.count(MessageDeliveryJob.id))
            .select_from(MessageDeliveryJob)
            .join(
                MessageCampaign,
                (MessageCampaign.id == MessageDeliveryJob.campaign_id)
                & (MessageCampaign.tenant_id == MessageDeliveryJob.tenant_id),
            )
            .where(
                MessageDeliveryJob.tenant_id == tid,
                campaign_filter,
                MessageDeliveryJob.status.in_(("PENDING", "PROCESSING", "RETRY_WAIT", "DEAD")),
                MessageDeliveryJob.is_deleted.is_(False),
                MessageCampaign.is_deleted.is_(False),
            )
        ) or 0),
        "unsettledMessageChannelDeliveries": int(db.scalar(
            select(func.count(MessageChannelDelivery.id))
            .select_from(MessageChannelDelivery)
            .join(
                MessageCampaign,
                (MessageCampaign.id == MessageChannelDelivery.campaign_id)
                & (MessageCampaign.tenant_id == MessageChannelDelivery.tenant_id),
            )
            .where(
                MessageChannelDelivery.tenant_id == tid,
                campaign_filter,
                MessageChannelDelivery.status.in_(("PENDING", "PROCESSING", "RETRY_WAIT", "DEAD")),
                MessageChannelDelivery.is_deleted.is_(False),
                MessageCampaign.is_deleted.is_(False),
            )
        ) or 0),
    }
    return counts, unsettled


def _domain_fact_counts(db, tenant_id: int, module_key: str) -> dict[str, int]:
    """Count formal facts only where the domain table itself is the authority."""
    tid = int(tenant_id)
    if module_key == "studentAffairs":
        from app.models.affairs_archive import ArchiveBatch, ArchivePackage

        return {
            "archiveBatches": _count(
                db, ArchiveBatch,
                ArchiveBatch.tenant_id == tid,
                ArchiveBatch.is_deleted.is_(False),
            ),
            "archivedBatches": _count(
                db, ArchiveBatch,
                ArchiveBatch.tenant_id == tid,
                ArchiveBatch.status == "ARCHIVED",
                ArchiveBatch.is_deleted.is_(False),
            ),
            "archivePackages": _count(
                db, ArchivePackage,
                ArchivePackage.tenant_id == tid,
                ArchivePackage.is_deleted.is_(False),
            ),
            "archivedPackages": _count(
                db, ArchivePackage,
                ArchivePackage.tenant_id == tid,
                ArchivePackage.status == "ARCHIVED",
                ArchivePackage.is_deleted.is_(False),
            ),
            "generatedPackageFiles": _count(
                db, ArchivePackage,
                ArchivePackage.tenant_id == tid,
                ArchivePackage.package_file_id.is_not(None),
                ArchivePackage.is_deleted.is_(False),
            ),
        }
    if module_key == "academicAffairs":
        from app.models.academic import AcademicGrade, AcademicStudent
        from app.models.academic_affairs_effective_grade import (
            AaEffectiveGradePolicySnapshot,
            AaGradeCorrection,
        )

        return {
            "academicStudents": _count(
                db, AcademicStudent,
                AcademicStudent.tenant_id == tid,
                AcademicStudent.is_deleted.is_(False),
            ),
            "formalGrades": _count(
                db, AcademicGrade,
                AcademicGrade.tenant_id == tid,
                AcademicGrade.is_deleted.is_(False),
            ),
            "activeGrades": _count(
                db, AcademicGrade,
                AcademicGrade.tenant_id == tid,
                AcademicGrade.record_status == "ACTIVE",
                AcademicGrade.is_deleted.is_(False),
            ),
            "passedActiveGrades": _count(
                db, AcademicGrade,
                AcademicGrade.tenant_id == tid,
                AcademicGrade.record_status == "ACTIVE",
                AcademicGrade.pass_status == "PASSED",
                AcademicGrade.is_deleted.is_(False),
            ),
            "effectiveGradePolicySnapshots": _count(
                db, AaEffectiveGradePolicySnapshot,
                AaEffectiveGradePolicySnapshot.tenant_id == tid,
                AaEffectiveGradePolicySnapshot.is_deleted.is_(False),
            ),
            "activeGradeCorrections": _count(
                db, AaGradeCorrection,
                AaGradeCorrection.tenant_id == tid,
                AaGradeCorrection.status == "ACTIVE",
                AaGradeCorrection.is_deleted.is_(False),
            ),
        }
    return {}


def collect_consumer_object_evidence(db, tenant_id: int, module_key: str) -> dict[str, Any]:
    """Return a stable, digestible snapshot of explicit consumer objects.

    No timestamp is included in this payload so its digest can be compared at export
    bind and school acceptance without generating false drift.
    """
    module = str(module_key)
    counts, unsettled = _shared_object_counts(db, int(tenant_id), module)
    domain_counts = _domain_fact_counts(db, int(tenant_id), module)
    basis: dict[str, Any] = {
        "authority": "EXPLICIT_SOURCE_MODULE_OR_DOMAIN_TABLE",
        "moduleAliases": list(MODULE_SOURCE_ALIASES.get(module, (module.lower(),))),
        "sharedObjectCounts": counts,
        "unsettledSharedObjectCounts": unsettled,
        "domainFactCounts": domain_counts,
        "hasOwnedSharedObjects": any(int(value or 0) > 0 for value in counts.values()),
        "hasUnsettledSharedObjects": any(int(value or 0) > 0 for value in unsettled.values()),
        "hasDomainFacts": any(int(value or 0) > 0 for value in domain_counts.values()),
        "ownershipGuessingUsed": False,
    }
    return {**basis, "objectEvidenceDigest": _digest(basis)}
