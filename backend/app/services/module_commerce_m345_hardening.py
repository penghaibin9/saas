"""M3-M5 cross-cutting hardening for delivery evidence and exit coordination.

This layer strengthens the already-installed lifecycle service without creating a
second authority. It keeps delivery acceptance bound to the *current* source set,
serializes tenant-wide and module-only exit requests across MySQL workers, verifies
final export evidence against real manifest items/storage, exposes only verified
export candidates, and records cross-domain consumer dependencies before retention.
It never grants physical purge or rewrites academic/departure truth.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from typing import Any

from sqlalchemy import func, select, text

from app.core.exceptions import AppException

_LOCK_TIMEOUT_SECONDS = 8
_LOCK_PREFIX = "module-commerce-offboard:"


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@contextmanager
def _coordination_lock(tenant_id: int):
    """Cross-process mutex shared by tenant-wide and module-only exit requests."""
    from app.db.session import db_enabled, get_sessionmaker

    if not db_enabled():
        yield
        return
    db = get_sessionmaker()()
    acquired = False
    name = f"{_LOCK_PREFIX}{int(tenant_id)}"
    try:
        if db.get_bind().dialect.name != "mysql":
            raise AppException("SERVER_ERROR", "退租协调锁仅支持生产 MySQL", http_status=500)
        value = db.execute(
            text("SELECT GET_LOCK(:name, :timeout)"),
            {"name": name, "timeout": _LOCK_TIMEOUT_SECONDS},
        ).scalar_one_or_none()
        acquired = int(value or 0) == 1
        if not acquired:
            raise AppException(
                "OFFBOARDING_COORDINATION_BUSY",
                "同一学校正在办理另一项退出操作，请刷新后重试",
                details={"tenantId": str(tenant_id), "retryable": True},
                http_status=503,
            )
        yield
    finally:
        if acquired:
            try:
                db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": name})
            except Exception:
                pass
        db.close()


def _assert_no_active_module_exit(tenant_id: int, lifecycle_module) -> None:
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleOffboardingJob

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(TenantModuleOffboardingJob).where(
            TenantModuleOffboardingJob.tenant_id == int(tenant_id),
            TenantModuleOffboardingJob.state.in_(tuple(lifecycle_module.ACTIVE_JOB_STATES)),
            TenantModuleOffboardingJob.is_deleted.is_(False),
        ).order_by(TenantModuleOffboardingJob.id.desc())).first()
        if row is not None:
            raise AppException(
                "DATA_CONFLICT",
                "该学校仍有未结束的单模块退出任务，禁止同时发起整校退出",
                details={"jobId": str(row.id), "moduleKey": row.module_key, "state": row.state},
                http_status=409,
            )
    finally:
        db.close()


def _consumer_dependencies(tenant_id: int, module_key: str, *, db_session=None) -> dict[str, Any]:
    """Read-only dependency inventory; never manufactures retained business truth."""
    from app.db.session import get_sessionmaker

    tid = int(tenant_id)
    module = str(module_key)
    owns = db_session is None
    db = db_session or get_sessionmaker()()
    try:
        if module == "internship":
            from app.models import InternshipArchive, InternshipFinalScore, InternshipRecord
            record_count = int(db.scalar(select(func.count(InternshipRecord.id)).where(
                InternshipRecord.tenant_id == tid, InternshipRecord.is_deleted.is_(False),
            )) or 0)
            score_count = int(db.scalar(select(func.count(InternshipFinalScore.id)).where(
                InternshipFinalScore.tenant_id == tid, InternshipFinalScore.is_deleted.is_(False),
            )) or 0)
            published_scores = int(db.scalar(select(func.count(InternshipFinalScore.id)).where(
                InternshipFinalScore.tenant_id == tid,
                InternshipFinalScore.status.in_(("PUBLISHED", "ARCHIVED")),
                InternshipFinalScore.is_deleted.is_(False),
            )) or 0)
            archive_count = int(db.scalar(select(func.count(InternshipArchive.id)).where(
                InternshipArchive.tenant_id == tid,
                InternshipArchive.status == "ARCHIVED",
                InternshipArchive.is_deleted.is_(False),
            )) or 0)
            counts = {
                "internshipRecords": record_count,
                "finalScores": score_count,
                "publishedFinalScores": published_scores,
                "validArchives": archive_count,
            }
            has_source = any(counts.values())
            source_bound = bool(published_scores or archive_count)
            if source_bound:
                disposition = "SOURCE_BOUND_EVIDENCE_RETAIN_REQUIRED"
                message = "离校与教务毕业资格仍直接消费实习正式成绩/归档；物理清理前必须由消费方形成并核验独立最小证据。"
            elif has_source:
                disposition = "SOURCE_PROCESS_UNRESOLVED"
                message = "存在实习过程事实但尚未形成完整正式成绩/归档；不得把退出后的缺源解释成从未安排。"
            else:
                disposition = "NO_SOURCE_CONSUMER_FACTS_FOUND"
                message = "当前未发现实习成绩/归档消费事实；仍需 M6 资源登记批准后才能进入物理清理。"
            basis = {
                "tenantId": str(tid), "moduleKey": module,
                "consumers": ["DEPARTURE", "ACADEMIC_GRADUATION_QUALIFICATION"],
                "sourceCounts": counts, "disposition": disposition,
                "consumerPurgeReady": not has_source,
                "requiresIndependentConsumerEvidence": has_source,
                "reviewStage": "M6_M7_BEFORE_PURGE",
            }
        elif module == "graduationDesign":
            from app.models import GraduationArchiveRecord, GraduationGrade, GraduationStudent
            student_count = int(db.scalar(select(func.count(GraduationStudent.id)).where(
                GraduationStudent.tenant_id == tid, GraduationStudent.is_deleted.is_(False),
            )) or 0)
            grade_count = int(db.scalar(select(func.count(GraduationGrade.id)).where(
                GraduationGrade.tenant_id == tid, GraduationGrade.is_deleted.is_(False),
            )) or 0)
            published_grades = int(db.scalar(select(func.count(GraduationGrade.id)).where(
                GraduationGrade.tenant_id == tid, GraduationGrade.status == "PUBLISHED",
                GraduationGrade.is_deleted.is_(False),
            )) or 0)
            filed_archives = int(db.scalar(select(func.count(GraduationArchiveRecord.id)).where(
                GraduationArchiveRecord.tenant_id == tid, GraduationArchiveRecord.status == "FILED",
                GraduationArchiveRecord.is_deleted.is_(False),
            )) or 0)
            counts = {
                "graduationStudents": student_count, "grades": grade_count,
                "publishedGrades": published_grades, "filedArchives": filed_archives,
            }
            has_source = any(counts.values())
            source_bound = bool(published_grades or filed_archives)
            if source_bound:
                disposition = "SOURCE_BOUND_EVIDENCE_RETAIN_REQUIRED"
                message = "离校与教务毕业资格仍直接消费毕设正式成绩/FILED归档；物理清理前必须保留并核验消费方最小证据。"
            elif has_source:
                disposition = "SOURCE_PROCESS_UNRESOLVED"
                message = "存在毕业设计过程事实但正式成绩/归档尚未闭环；缺源不能降级成未安排。"
            else:
                disposition = "NO_SOURCE_CONSUMER_FACTS_FOUND"
                message = "当前未发现毕设成绩/归档消费事实；仍需 M6 资源登记批准后才能进入物理清理。"
            basis = {
                "tenantId": str(tid), "moduleKey": module,
                "consumers": ["DEPARTURE", "ACADEMIC_GRADUATION_QUALIFICATION"],
                "sourceCounts": counts, "disposition": disposition,
                "consumerPurgeReady": not has_source,
                "requiresIndependentConsumerEvidence": has_source,
                "reviewStage": "M6_M7_BEFORE_PURGE",
            }
        elif module == "studentAffairs":
            basis = {
                "tenantId": str(tid), "moduleKey": module,
                "consumers": ["DEPARTURE", "SHARED_STUDENT_FOUNDATION", "APPROVAL_TODO_MESSAGE"],
                "sourceCounts": {}, "disposition": "MODULE_RESOURCE_REVIEW_REQUIRED",
                "consumerPurgeReady": False, "requiresIndependentConsumerEvidence": True,
                "reviewStage": "M6_M7_BEFORE_PURGE",
            }
            message = "学工数据与共享学生主档、离校及公共审批/待办存在跨域关系；M5 只冻结交付，禁止据菜单归属推断可删。"
        elif module == "academicAffairs":
            basis = {
                "tenantId": str(tid), "moduleKey": module,
                "consumers": ["GRADUATION_QUALIFICATION", "TRANSCRIPT_ARCHIVE", "DEPARTURE"],
                "sourceCounts": {}, "disposition": "FORMAL_ACADEMIC_FACTS_RETAIN_REVIEW_REQUIRED",
                "consumerPurgeReady": False, "requiresIndependentConsumerEvidence": True,
                "reviewStage": "M6_M7_BEFORE_PURGE",
            }
            message = "教务正式成绩、学分/GPA与毕业资格属于跨域正式事实；M5 不允许模块退订把这些事实变成可删源数据。"
        else:
            basis = {
                "tenantId": str(tid), "moduleKey": module, "consumers": [], "sourceCounts": {},
                "disposition": "UNKNOWN_MODULE_DEPENDENCY", "consumerPurgeReady": False,
                "requiresIndependentConsumerEvidence": True, "reviewStage": "M6_M7_BEFORE_PURGE",
            }
            message = "未知模块消费者依赖，默认阻断后续物理清理。"
        return {
            **basis,
            "message": message,
            "dependencyDigest": _digest(basis),
            "capturedAt": datetime.utcnow().isoformat(timespec="seconds"),
        }
    finally:
        if owns:
            db.close()


def _purge_blockers(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    if snapshot.get("consumerPurgeReady"):
        return []
    return [{
        "code": "CONSUMER_DEPENDENCY_NOT_DISPOSED",
        "message": snapshot.get("message"),
        "disposition": snapshot.get("disposition"),
        "dependencyDigest": snapshot.get("dependencyDigest"),
        "reviewStage": snapshot.get("reviewStage"),
    }]


def _stored_consumer_snapshot(job_id: int) -> dict | None:
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleOffboardingJob
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(TenantModuleOffboardingJob).where(
            TenantModuleOffboardingJob.id == int(job_id),
            TenantModuleOffboardingJob.is_deleted.is_(False),
        )).first()
        return dict((row.result_json or {}).get("consumerDependencySnapshot") or {}) or None if row else None
    finally:
        db.close()


def _harden_export_evidence(db, job, export, manifest, file_row, result, lifecycle_module) -> None:
    from app.models.file import ArchiveManifestItem
    from app.services.storage import get_backend

    scope = dict(export.data_scope_snapshot_json or {})
    if str(scope.get("tenantId") or "") != str(job.tenant_id):
        raise AppException("DATA_CONFLICT", "导出数据范围未绑定当前学校", http_status=409)
    try:
        scoped_module = lifecycle_module.canonical_module(str(scope.get("moduleKey") or ""))
    except AppException as exc:
        raise AppException("DATA_CONFLICT", "导出数据范围未绑定当前模块", http_status=409) from exc
    if scoped_module != job.module_key:
        raise AppException("DATA_CONFLICT", "导出数据范围模块与退出任务不一致", http_status=409)
    scoped_generation = scope.get("moduleGeneration")
    if scoped_generation is not None and int(scoped_generation or 0) != int(job.module_generation):
        raise AppException("DATA_CONFLICT", "导出数据范围模块代次不一致", http_status=409)

    if str(result.get("manifestId") or "") != str(manifest.id):
        raise AppException("DATA_CONFLICT", "导出回执引用的 Manifest 与提交对象不一致", http_status=409)
    if str(manifest.target_type or "").upper() != "MODULE_GENERATION":
        raise AppException("DATA_CONFLICT", "Manifest 不是模块代次交付清单", http_status=409)
    if str(manifest.target_id or "") != str(job.module_generation):
        raise AppException("DATA_CONFLICT", "Manifest 未绑定当前模块代次", http_status=409)

    attachment_count = result.get("attachmentCount")
    actual_items = int(db.scalar(select(func.count(ArchiveManifestItem.id)).where(
        ArchiveManifestItem.tenant_id == int(job.tenant_id),
        ArchiveManifestItem.manifest_id == int(manifest.id),
        ArchiveManifestItem.is_deleted.is_(False),
    )) or 0)
    if type(attachment_count) is not int or actual_items != attachment_count:
        raise AppException(
            "DATA_CONFLICT", "Manifest 实际附件数量与导出回执不一致",
            details={"expected": attachment_count, "actual": actual_items}, http_status=409,
        )

    backend = get_backend()
    row_backend = str(file_row.storage_backend or "").lower()
    active_backend = str(getattr(backend, "kind", "") or "").lower()
    if row_backend and active_backend and row_backend != active_backend:
        raise AppException(
            "DATA_CONFLICT", "导出文件记录的存储后端与当前受治理存储不一致",
            details={"fileBackend": row_backend, "activeBackend": active_backend}, http_status=409,
        )
    try:
        exists = bool(file_row.file_key and backend.exists(str(file_row.file_key)))
    except Exception as exc:
        raise AppException(
            "FILE_STORAGE_UNAVAILABLE", "最终交付文件存储核验暂时不可用，已拒绝进入保留期",
            details={"retryable": True}, http_status=503,
        ) from exc
    if not exists:
        raise AppException("DATA_CONFLICT", "最终交付文件在受治理存储中不存在", http_status=409)


def _verified_export_candidates(job_id: int, lifecycle_module) -> list[dict[str, Any]]:
    """Return only final-export rows that pass the exact same bind-time contract."""
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleOffboardingJob
    from app.models.data_exchange import ExportJob

    db = get_sessionmaker()()
    try:
        job = db.scalars(select(TenantModuleOffboardingJob).where(
            TenantModuleOffboardingJob.id == int(job_id), TenantModuleOffboardingJob.is_deleted.is_(False),
        )).first()
        if job is None or job.state not in {"FROZEN", "EXPORTING", "WAIT_EXPORT_ACCEPT"}:
            return []
        rows = list(db.scalars(select(ExportJob).where(
            ExportJob.tenant_id == int(job.tenant_id), ExportJob.status == "SUCCEEDED",
            ExportJob.file_object_id.is_not(None), ExportJob.revoked_at.is_(None),
            ExportJob.is_deleted.is_(False),
        ).order_by(ExportJob.id.desc()).limit(50)).all())
        output: list[dict[str, Any]] = []
        now = datetime.utcnow()
        for export in rows:
            if export.expires_at is not None and export.expires_at <= now:
                continue
            result = dict(export.result_json or {}); filters = dict(export.filter_snapshot_json or {})
            manifest_raw = str(result.get("manifestId") or "")
            if not manifest_raw.isdigit() or str(filters.get("scopeHash") or "") != str(job.scope_hash):
                continue
            if int(filters.get("moduleGeneration") or 0) != int(job.module_generation):
                continue
            try:
                verified_export, manifest, file_row, verified_result = lifecycle_module._validate_export_contract(
                    db, job, export_job_id=int(export.id), manifest_id=int(manifest_raw), scope_hash=str(job.scope_hash),
                )
            except AppException:
                continue
            output.append({
                "exportJobId": str(verified_export.id), "manifestId": str(manifest.id),
                "fileId": str(file_row.id), "fileName": file_row.file_name,
                "fileSizeBytes": int(file_row.size_bytes or 0), "fileSha256": str(file_row.sha256 or ""),
                "objectCount": int(verified_result.get("objectCount") or 0),
                "attachmentCount": int(verified_result.get("attachmentCount") or 0),
                "finishedAt": verified_export.finished_at.isoformat(timespec="seconds") if verified_export.finished_at else None,
            })
        return output
    finally:
        db.close()


def install(lifecycle_module, tenant_offboarding_module):
    if getattr(lifecycle_module, "_m345_hardening_installed", False):
        return lifecycle_module

    original_portfolio = lifecycle_module.tenant_module_portfolio
    original_preview = lifecycle_module.preview_module_offboarding
    original_module_request = lifecycle_module.request_module_offboarding
    original_validate_export = lifecycle_module._validate_export_contract
    original_get_job = lifecycle_module.get_module_offboarding_job
    original_tenant_request = tenant_offboarding_module.request_offboarding

    def tenant_module_portfolio(tenant_id: int) -> dict[str, Any]:
        result = original_portfolio(int(tenant_id))
        for row in result.get("modules") or []:
            acceptance = row.get("deliveryAcceptance"); current_digest = str(row.get("sourceDigest") or "")
            if acceptance and str(acceptance.get("sourceDigest") or "") != current_digest:
                row["staleDeliveryAcceptance"] = dict(acceptance); row["deliveryAcceptance"] = None; row["deliveryAcceptanceCurrent"] = False
            else:
                row["staleDeliveryAcceptance"] = None; row["deliveryAcceptanceCurrent"] = bool(acceptance)
        return result

    def preview_module_offboarding(tenant_id: int, module_key: str) -> dict[str, Any]:
        result = original_preview(int(tenant_id), module_key)
        dependencies = _consumer_dependencies(int(tenant_id), str(result["moduleKey"]))
        result["consumerDependencies"] = dependencies
        result["purgeBlockers"] = _purge_blockers(dependencies)
        result["physicalPurgeAuthorized"] = False
        return result

    def request_module_offboarding(user: dict, tenant_id: int, module_key: str, **kwargs):
        with _coordination_lock(int(tenant_id)):
            return original_module_request(user, int(tenant_id), module_key, **kwargs)

    def request_tenant_offboarding(user: dict, tenant_id: int, **kwargs):
        with _coordination_lock(int(tenant_id)):
            _assert_no_active_module_exit(int(tenant_id), lifecycle_module)
            return original_tenant_request(user, int(tenant_id), **kwargs)

    def validate_export_contract(db, job, **kwargs):
        export, manifest, file_row, result = original_validate_export(db, job, **kwargs)
        _harden_export_evidence(db, job, export, manifest, file_row, result, lifecycle_module)
        dependencies = _consumer_dependencies(int(job.tenant_id), str(job.module_key), db_session=db)
        job.result_json = {
            **dict(job.result_json or {}),
            "consumerDependencySnapshot": dependencies,
            "physicalPurgeAuthorized": False,
        }
        return export, manifest, file_row, result

    def get_module_offboarding_job(job_id: int) -> dict[str, Any]:
        result = original_get_job(int(job_id))
        current = _consumer_dependencies(int(result["tenantId"]), str(result["moduleKey"]))
        result["consumerDependencies"] = current
        result["purgeBlockers"] = _purge_blockers(current)
        result["consumerDependencySnapshot"] = _stored_consumer_snapshot(int(job_id))
        result["exportCandidates"] = _verified_export_candidates(int(job_id), lifecycle_module)
        result["physicalPurgeAuthorized"] = False
        return result

    lifecycle_module.tenant_module_portfolio = tenant_module_portfolio
    lifecycle_module.preview_module_offboarding = preview_module_offboarding
    lifecycle_module.request_module_offboarding = request_module_offboarding
    lifecycle_module._validate_export_contract = validate_export_contract
    lifecycle_module.get_module_offboarding_job = get_module_offboarding_job
    lifecycle_module._m345_hardening_installed = True
    tenant_offboarding_module.request_offboarding = request_tenant_offboarding
    tenant_offboarding_module._module_exit_coordination_installed = True
    return lifecycle_module
