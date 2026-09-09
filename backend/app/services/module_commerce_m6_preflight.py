"""M6 read-only module purge preflight.

This module is deliberately incapable of executing destruction. It converts the
M0/M5 evidence already present in the repository into a fail-closed review
surface: candidate tables, selector quality, shared-file/legal-hold risk,
consumer dependencies, retention/export evidence, and schema-registry drift.

Physical deletion remains disabled until a later explicitly reviewed M6
implementation supplies complete resource ownership and executable selectors.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import importlib
import json
from typing import Any

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker

REGISTRY_VERSION = "2026-09-08.module-m6-preflight.1"
FULL_RESOURCE_CLOSURE_COMPLETE = False
DELETION_AUTHORIZED = False

_MODULE_PREFIX_HINTS: dict[str, tuple[str, ...]] = {
    "internship": ("t_internship", "t_risk_", "t_weekly_"),
    "graduationDesign": ("t_graduation", "t_gd_"),
    "studentAffairs": (
        "t_affairs", "t_dorm", "t_aid_", "t_funding_", "t_psy_", "t_discipline_",
    ),
    "academicAffairs": ("t_aa_", "t_acad_", "t_academic"),
}

_SHARED_FOUNDATION_PRESERVE = (
    "t_tenant",
    "t_user",
    "t_role",
    "t_permission",
    "t_student_profile",
    "t_college",
    "t_major",
    "t_class",
)


def _require_db() -> None:
    if not db_enabled():
        raise AppException("SERVER_ERROR", "M6只读销毁预演需要数据库", http_status=500)


def _digest(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _canonical_module(value: str) -> str:
    lifecycle = importlib.import_module("app.services.module_commerce_lifecycle_service")
    return lifecycle.canonical_module(value)


def module_table_inventory(module_key: str) -> dict[str, Any]:
    """Metadata-only discovery hints; never an executable deletion registry."""
    from app.db.base import metadata

    module = _canonical_module(module_key)
    prefixes = _MODULE_PREFIX_HINTS[module]
    rows: list[dict[str, Any]] = []
    for table in metadata.sorted_tables:
        if not any(table.name.startswith(prefix) for prefix in prefixes):
            continue
        columns = set(table.c.keys())
        has_tenant = "tenant_id" in columns
        has_generation = "module_generation" in columns
        if not has_tenant:
            selector_status = "NO_TENANT_SELECTOR_BLOCKED"
        elif not has_generation:
            selector_status = "TENANT_ONLY_SELECTOR_REVIEW_REQUIRED"
        else:
            selector_status = "TENANT_AND_GENERATION_SELECTOR_PRESENT"
        rows.append(
            {
                "table": table.name,
                "discoveryReason": "MODULE_PREFIX_HINT_ONLY",
                "tenantIdColumn": "tenant_id" if has_tenant else None,
                "moduleGenerationColumn": "module_generation" if has_generation else None,
                "selectorStatus": selector_status,
                "purgeAuthorized": False,
            }
        )
    unsafe = [
        row["table"]
        for row in rows
        if row["selectorStatus"] != "TENANT_AND_GENERATION_SELECTOR_PRESENT"
    ]
    basis = {
        "registryVersion": REGISTRY_VERSION,
        "moduleKey": module,
        "candidateTables": rows,
        "metadataOnly": True,
        "sqlOnlyAndDynamicResourcesIncluded": False,
        "fullResourceClosureComplete": FULL_RESOURCE_CLOSURE_COMPLETE,
        "selectorCoverageComplete": bool(rows) and not unsafe,
        "unsafeSelectorTables": unsafe,
        "deletionAuthorized": DELETION_AUTHORIZED,
    }
    return {**basis, "inventoryDigest": _digest(basis)}


def _module_file_risk(db, tenant_id: int, module_key: str) -> dict[str, Any]:
    from app.models.file import FileBinding, FileObject
    from app.models.file_quota import FileStorageQuotaReservation

    aliases = {
        "internship": {"internship", "INTERNSHIP"},
        "graduationDesign": {"graduation", "graduationDesign", "GRADUATION"},
        "studentAffairs": {"studentAffairs", "STUDENT_AFFAIRS", "AFFAIRS"},
        "academicAffairs": {"academicAffairs", "ACADEMIC_AFFAIRS", "ACADEMIC"},
    }[module_key]

    module_ids = (
        select(FileBinding.file_id)
        .where(
            FileBinding.tenant_id == int(tenant_id),
            FileBinding.module_code.in_(tuple(aliases)),
            FileBinding.status == "ACTIVE",
            FileBinding.is_deleted.is_(False),
        )
        .distinct()
    )
    module_file_count = int(
        db.scalar(
            select(func.count(FileObject.id)).where(
                FileObject.tenant_id == int(tenant_id),
                FileObject.id.in_(module_ids),
                FileObject.is_deleted.is_(False),
            )
        )
        or 0
    )
    legal_hold_count = int(
        db.scalar(
            select(func.count(FileObject.id)).where(
                FileObject.tenant_id == int(tenant_id),
                FileObject.id.in_(module_ids),
                FileObject.is_deleted.is_(False),
                FileObject.legal_hold.is_(True),
            )
        )
        or 0
    )
    cross_module_reference_count = int(
        db.scalar(
            select(func.count(func.distinct(FileBinding.file_id))).where(
                FileBinding.tenant_id == int(tenant_id),
                FileBinding.file_id.in_(module_ids),
                FileBinding.status == "ACTIVE",
                FileBinding.is_deleted.is_(False),
                ~FileBinding.module_code.in_(tuple(aliases)),
            )
        )
        or 0
    )
    held_reservation_count = int(
        db.scalar(
            select(func.count(FileStorageQuotaReservation.id)).where(
                FileStorageQuotaReservation.tenant_id == int(tenant_id),
                FileStorageQuotaReservation.module_code.in_(tuple(aliases)),
                FileStorageQuotaReservation.status == "HELD",
                FileStorageQuotaReservation.expires_at > datetime.utcnow(),
                FileStorageQuotaReservation.is_deleted.is_(False),
            )
        )
        or 0
    )
    return {
        "logicalModuleFileCount": module_file_count,
        "legalHoldFileCount": legal_hold_count,
        "crossModuleReferencedFileCount": cross_module_reference_count,
        "activeReservationCount": held_reservation_count,
        "physicalFileDeletionAuthorized": False,
    }


def preview_module_purge(
    job_id: int, *, tenant_id: int | None = None,
    expected_generation: int | None = None, expected_version: int | None = None,
) -> dict[str, Any]:
    """Read-only preflight, optionally bound to the operator's selected school/job.

    The HTTP reader supplies all three context fields. Check ownership in the first
    query and optimistic context before collecting any consumer or file information.
    Existing internal callers retain the same read-only behavior without these fields.
    """
    for name, value, minimum in (
        ("jobId", job_id, 1), ("tenantId", tenant_id, 1),
        ("expectedGeneration", expected_generation, 1), ("expectedVersion", expected_version, 0),
    ):
        if value is not None and (type(value) is not int or not minimum <= value <= 2**63 - 1):
            raise AppException("VALIDATION_ERROR", f"{name} 必须是有效整数", http_status=422)
    if job_id is None:
        raise AppException("VALIDATION_ERROR", "jobId 必填", http_status=422)
    _require_db()
    from app.models import TenantModuleOffboardingJob, TenantModuleState
    from app.services import tenant_purge_registry

    hardening = importlib.import_module("app.services.module_commerce_m345_hardening")

    db = get_sessionmaker()()
    try:
        filters = [
            TenantModuleOffboardingJob.id == job_id,
            TenantModuleOffboardingJob.is_deleted.is_(False),
        ]
        if tenant_id is not None:
            filters.append(TenantModuleOffboardingJob.tenant_id == tenant_id)
        job = db.scalars(select(TenantModuleOffboardingJob).where(*filters)).first()
        if job is None:
            raise AppException("DATA_NOT_FOUND", "模块退出任务不存在", http_status=404)

        if (expected_generation is not None and int(job.module_generation) != expected_generation
                or expected_version is not None and int(job.version or 0) != expected_version):
            raise AppException(
                "DATA_CONFLICT", "退出任务代次或版本已变化，请刷新当前学校的任务后重新检查", http_status=409,
            )
        module = _canonical_module(job.module_key)
        state = db.scalars(
            select(TenantModuleState).where(
                TenantModuleState.tenant_id == int(job.tenant_id),
                TenantModuleState.module_key == module,
                TenantModuleState.is_deleted.is_(False),
            )
        ).first()
        dependencies = hardening._consumer_dependencies(
            int(job.tenant_id), module, db_session=db
        )
        consumer_blockers = hardening._purge_blockers(dependencies)
        file_risk = _module_file_risk(db, int(job.tenant_id), module)
        table_inventory = module_table_inventory(module)
        tenant_registry = tenant_purge_registry.inventory()
        now = datetime.utcnow()

        blockers: list[dict[str, Any]] = [
            {
                "code": "M0_FULL_RESOURCE_CLOSURE_REQUIRED",
                "message": "M0完整consumer/resource闭包尚未形成可执行模块销毁清单；当前只允许只读预演。",
            },
            {
                "code": "MODULE_PURGE_EXECUTION_DISABLED",
                "message": "M6物理销毁实现尚未授权，当前服务没有任何删除能力。",
            },
            {
                "code": "BACKUP_DISPOSITION_POLICY_REQUIRED",
                "message": "模块在线数据清理不能声称备份介质同步擦除；必须先绑定明确的备份保留/退休政策证据。",
            },
        ]
        blockers.extend(consumer_blockers)

        if job.state != "RETENTION":
            blockers.append(
                {
                    "code": "RETENTION_NOT_ACTIVE",
                    "message": f"退出任务当前状态 {job.state}，尚未处于合规保留期。",
                }
            )
        if job.accepted_at is None or not str(job.acceptance_ref or "").strip():
            blockers.append(
                {"code": "EXPORT_ACCEPTANCE_MISSING", "message": "校方最终数据接收证据缺失。"}
            )
        if not job.export_job_id or not job.manifest_id or not job.export_file_id:
            blockers.append(
                {
                    "code": "VERIFIED_EXPORT_EVIDENCE_MISSING",
                    "message": "服务端最终导出/Manifest/FileObject证据链不完整。",
                }
            )
        if job.retention_until is None:
            blockers.append(
                {"code": "RETENTION_DEADLINE_MISSING", "message": "保留期截止时间缺失。"}
            )
        elif job.retention_until > now:
            blockers.append(
                {
                    "code": "RETENTION_ACTIVE",
                    "message": "法定/合同保留期尚未结束。",
                    "retentionUntil": job.retention_until.isoformat(timespec="seconds"),
                }
            )
        if state is None or int(state.generation or 0) != int(job.module_generation):
            blockers.append(
                {
                    "code": "MODULE_GENERATION_CONFLICT",
                    "message": "模块实例不存在或generation已变化，旧退出任务不能用于销毁预演。",
                }
            )
        elif str(state.data_state or "").upper() != "RETAINED":
            blockers.append(
                {
                    "code": "MODULE_NOT_RETAINED",
                    "message": f"模块数据状态 {state.data_state} 不是 RETAINED。",
                }
            )
        if file_risk["legalHoldFileCount"]:
            blockers.append(
                {
                    "code": "LEGAL_HOLD_ACTIVE",
                    "message": "目标模块引用的文件存在legal hold，禁止物理清理。",
                    "count": file_risk["legalHoldFileCount"],
                }
            )
        if file_risk["crossModuleReferencedFileCount"]:
            blockers.append(
                {
                    "code": "SHARED_FILE_REFERENCE_ACTIVE",
                    "message": "存在被其他模块继续引用的文件对象，不能按模块归属删除物理字节。",
                    "count": file_risk["crossModuleReferencedFileCount"],
                }
            )
        if file_risk["activeReservationCount"]:
            blockers.append(
                {
                    "code": "ACTIVE_STORAGE_RESERVATION",
                    "message": "仍有模块文件容量预留未释放。",
                    "count": file_risk["activeReservationCount"],
                }
            )
        if not table_inventory["selectorCoverageComplete"]:
            blockers.append(
                {
                    "code": "MODULE_SELECTOR_COVERAGE_INCOMPLETE",
                    "message": "候选模块表尚未全部具备经过审核的tenant+generation销毁selector。",
                    "tables": table_inventory["unsafeSelectorTables"],
                }
            )
        if not tenant_registry["complete"]:
            blockers.append(
                {
                    "code": "TENANT_PURGE_REGISTRY_INCOMPLETE",
                    "message": "整租Purge Registry存在未分类tenant表；模块销毁不得绕过该更严格信号。",
                    "tables": tenant_registry["unknownTables"],
                }
            )

        stable_basis = {
            "jobId": str(job.id),
            "jobVersion": int(job.version or 0),
            "tenantId": str(job.tenant_id),
            "moduleKey": module,
            "moduleGeneration": int(job.module_generation),
            "scopeHash": str(job.scope_hash),
            "jobState": str(job.state),
            "retentionUntil": job.retention_until.isoformat(timespec="seconds") if job.retention_until else None,
            "consumerDependencyDigest": dependencies.get("dependencyDigest"),
            "moduleInventoryDigest": table_inventory["inventoryDigest"],
            "tenantPurgeRegistryVersion": tenant_registry["registryVersion"],
            "blockerCodes": sorted({str(row.get("code")) for row in blockers}),
        }
        return {
            **stable_basis,
            "preflightVersion": REGISTRY_VERSION,
            "capturedAt": now.isoformat(timespec="seconds"),
            "dryRunOnly": True,
            "destructiveExecutionAvailable": False,
            "physicalPurgeAuthorized": False,
            "deletionAuthorized": False,
            "fullResourceClosureComplete": FULL_RESOURCE_CLOSURE_COMPLETE,
            "sharedFoundation": [
                {"table": table, "disposition": "PRESERVE", "purgeAuthorized": False}
                for table in _SHARED_FOUNDATION_PRESERVE
            ],
            "moduleTableInventory": table_inventory,
            "consumerDependencies": dependencies,
            "fileRisk": file_risk,
            "tenantPurgeRegistry": {
                "registryVersion": tenant_registry["registryVersion"],
                "reviewedAlembicHead": tenant_registry["reviewedAlembicHead"],
                "complete": tenant_registry["complete"],
                "unknownTables": tenant_registry["unknownTables"],
            },
            "blockers": blockers,
            "canExecutePhysicalPurge": False,
            "destructiveStatements": [],
            "preflightDigest": _digest(stable_basis),
        }
    finally:
        db.close()
