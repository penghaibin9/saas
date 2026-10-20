"""M4/M5 object-level consumer closure for module offboarding delivery.

Installed after ``module_commerce_m345_hardening``.  It enriches that layer's domain
summary with explicit shared-object evidence and seals the resulting dependency digest
when the final export is bound.  School acceptance rechecks the same evidence inside
the lifecycle transaction; any object drift forces a new export/bind cycle.

This module is deliberately non-destructive.  It never changes consumer data and never
authorizes physical purge.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.exceptions import AppException
from app.services.module_commerce_consumer_evidence import collect_consumer_object_evidence


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _stable_dependency_basis(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in snapshot.items()
        if key not in {"dependencyDigest", "capturedAt", "message"}
    }


def enrich_dependency_snapshot(base: dict[str, Any], object_evidence: dict[str, Any]) -> dict[str, Any]:
    """Add exact object evidence without weakening the existing fail-closed disposition."""
    current = dict(base or {})
    module = str(current.get("moduleKey") or "")
    domain = dict(object_evidence.get("domainFactCounts") or {})
    has_shared = bool(object_evidence.get("hasOwnedSharedObjects"))
    has_unsettled = bool(object_evidence.get("hasUnsettledSharedObjects"))
    has_domain = bool(object_evidence.get("hasDomainFacts"))
    message = str(current.get("message") or "")

    if module == "studentAffairs":
        current["sourceCounts"] = domain
        formal_archive = any(int(domain.get(key) or 0) > 0 for key in (
            "archivedBatches", "archivedPackages", "generatedPackageFiles",
        ))
        if formal_archive:
            current["disposition"] = "SOURCE_BOUND_EVIDENCE_RETAIN_REQUIRED"
            message = "学工正式归档包已经形成，且共享审批/待办/消息/文件仍可能引用本模块对象；交付必须保留归档与对象级消费证据。"
        elif has_domain or has_shared:
            current["disposition"] = "SOURCE_PROCESS_UNRESOLVED"
            message = "学工仍存在归档过程或显式归属的共享对象；退出交付不得把未闭环事实解释为从未发生。"
        current["consumerPurgeReady"] = False
        current["requiresIndependentConsumerEvidence"] = True
    elif module == "academicAffairs":
        current["sourceCounts"] = domain
        if has_domain:
            current["disposition"] = "FORMAL_ACADEMIC_FACTS_RETAIN_REQUIRED"
            message = "已存在正式学籍/成绩/规则快照或更正链；这些事实继续服务成绩单、学分/GPA、毕业资格与离校，必须作为长期消费证据保留。"
        current["consumerPurgeReady"] = False
        current["requiresIndependentConsumerEvidence"] = True
    elif has_shared:
        # Existing internship/graduation source disposition remains authoritative.
        # Only the previous 'nothing found' state is strengthened when exact shared
        # objects prove that cross-domain consumers do exist.
        if current.get("disposition") == "NO_SOURCE_CONSUMER_FACTS_FOUND":
            current["disposition"] = "SHARED_CONSUMER_EVIDENCE_RETAIN_REQUIRED"
            message = "未发现该模块正式成绩/归档，但公共审批、待办、消息或文件存在显式模块归属；交付前必须保留并核验这些共享对象。"
        current["consumerPurgeReady"] = False
        current["requiresIndependentConsumerEvidence"] = True

    if has_unsettled:
        current["consumerPurgeReady"] = False
        current["requiresIndependentConsumerEvidence"] = True
        message = (message + " 当前仍有未完成的共享审批/待办/异步消息投递，不能进入不可逆处置。 ").strip()

    current["objectEvidence"] = dict(object_evidence)
    current["message"] = message
    current["dependencyDigest"] = _digest(_stable_dependency_basis(current))
    return current


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


def _changed_evidence(stored: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    left = dict((stored.get("objectEvidence") or {}))
    right = dict((current.get("objectEvidence") or {}))
    changed: dict[str, Any] = {}
    for section in ("sharedObjectCounts", "unsettledSharedObjectCounts", "domainFactCounts"):
        before = dict(left.get(section) or {})
        after = dict(right.get(section) or {})
        keys = sorted(set(before) | set(after))
        delta = {
            key: {"bound": int(before.get(key) or 0), "current": int(after.get(key) or 0)}
            for key in keys
            if int(before.get(key) or 0) != int(after.get(key) or 0)
        }
        if delta:
            changed[section] = delta
    return changed


def assert_bound_snapshot_current(stored: dict[str, Any] | None, current: dict[str, Any]) -> None:
    """Reject acceptance when the export was bound against another consumer graph."""
    snapshot = dict(stored or {})
    evidence = dict(snapshot.get("objectEvidence") or {})
    if not snapshot or not evidence.get("objectEvidenceDigest"):
        raise AppException(
            "DATA_CONFLICT",
            "交付绑定缺少对象级消费者快照，请重新生成并绑定最终交付包",
            details={"reasonCode": "CONSUMER_SNAPSHOT_REBIND_REQUIRED"},
            http_status=409,
        )
    if str(snapshot.get("dependencyDigest") or "") != str(current.get("dependencyDigest") or ""):
        raise AppException(
            "DATA_CONFLICT",
            "交付绑定后消费者对象发生变化，请重新生成并绑定最终交付包",
            details={
                "reasonCode": "CONSUMER_DEPENDENCY_CHANGED",
                "boundDigest": snapshot.get("dependencyDigest"),
                "currentDigest": current.get("dependencyDigest"),
                "changedEvidence": _changed_evidence(snapshot, current),
            },
            http_status=409,
        )


def _collect_with_new_session(tenant_id: int, module_key: str) -> dict[str, Any]:
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        return collect_consumer_object_evidence(db, int(tenant_id), str(module_key))
    finally:
        db.close()


def _is_fresh_rebind(job, kwargs: dict[str, Any]) -> bool:
    """A drifted package can recover only through a different verified export/manifest."""
    try:
        requested_export = int(kwargs.get("export_job_id") or 0)
        requested_manifest = int(kwargs.get("manifest_id") or 0)
    except (TypeError, ValueError, OverflowError):
        return False
    return bool(
        requested_export
        and requested_manifest
        and (
            requested_export != int(job.export_job_id or 0)
            or requested_manifest != int(job.manifest_id or 0)
        )
    )


def install(lifecycle_module):
    if getattr(lifecycle_module, "_m45_consumer_closure_installed", False):
        return lifecycle_module

    original_preview = lifecycle_module.preview_module_offboarding
    original_validate_export = lifecycle_module._validate_export_contract
    original_get_job = lifecycle_module.get_module_offboarding_job

    def preview_module_offboarding(tenant_id: int, module_key: str) -> dict[str, Any]:
        result = original_preview(int(tenant_id), module_key)
        evidence = _collect_with_new_session(int(tenant_id), str(result["moduleKey"]))
        dependency = enrich_dependency_snapshot(dict(result.get("consumerDependencies") or {}), evidence)
        result["consumerDependencies"] = dependency
        result["purgeBlockers"] = _purge_blockers(dependency)
        result["physicalPurgeAuthorized"] = False
        return result

    def validate_export_contract(db, job, **kwargs):
        # Save the bind-time snapshot before the older hardening layer refreshes its
        # own domain summary.  On WAIT_EXPORT_ACCEPT this is the evidence sealed when
        # the school-facing package was bound.
        state_before = str(job.state or "")
        stored_before = dict((job.result_json or {}).get("consumerDependencySnapshot") or {}) or None
        fresh_rebind = state_before == "WAIT_EXPORT_ACCEPT" and _is_fresh_rebind(job, kwargs)
        export, manifest, file_row, result = original_validate_export(db, job, **kwargs)

        base_current = dict((job.result_json or {}).get("consumerDependencySnapshot") or {})
        evidence = collect_consumer_object_evidence(db, int(job.tenant_id), str(job.module_key))
        current = enrich_dependency_snapshot(base_current, evidence)

        if state_before == "WAIT_EXPORT_ACCEPT" and not fresh_rebind:
            # Acceptance (and re-submitting the same old package) must match exactly.
            assert_bound_snapshot_current(stored_before, current)
            sealed = dict(stored_before or {})
        else:
            # First bind, or explicit rebind to a different verified export/manifest,
            # seals the current object graph so drift has a safe recovery path.
            sealed = current

        job.result_json = {
            **dict(job.result_json or {}),
            "consumerDependencySnapshot": sealed,
            "consumerDependencyLastVerifiedDigest": current.get("dependencyDigest"),
            "consumerSnapshotRebound": bool(fresh_rebind),
            "physicalPurgeAuthorized": False,
        }
        return export, manifest, file_row, result

    def get_module_offboarding_job(job_id: int) -> dict[str, Any]:
        result = original_get_job(int(job_id))
        evidence = _collect_with_new_session(int(result["tenantId"]), str(result["moduleKey"]))
        current = enrich_dependency_snapshot(dict(result.get("consumerDependencies") or {}), evidence)
        stored = dict(result.get("consumerDependencySnapshot") or {}) or None
        snapshot_current = bool(
            stored
            and (stored.get("objectEvidence") or {}).get("objectEvidenceDigest")
            and str(stored.get("dependencyDigest") or "") == str(current.get("dependencyDigest") or "")
        )
        result["consumerDependencies"] = current
        result["purgeBlockers"] = _purge_blockers(current)
        result["consumerDependencySnapshot"] = stored
        result["consumerSnapshotCurrent"] = snapshot_current

        delivery_basis = {
            "tenantId": result.get("tenantId"),
            "moduleKey": result.get("moduleKey"),
            "moduleGeneration": result.get("moduleGeneration"),
            "scopeHash": result.get("scopeHash"),
            "exportJobId": result.get("exportJobId"),
            "manifestId": result.get("manifestId"),
            "exportFileId": result.get("exportFileId"),
            "consumerDependencyDigest": (stored or {}).get("dependencyDigest"),
        }
        has_bound_export = bool(result.get("exportJobId") and result.get("manifestId") and result.get("exportFileId"))
        result["deliveryEvidenceDigest"] = _digest(delivery_basis) if has_bound_export and stored else None
        result["deliveryAcceptanceReady"] = bool(
            result.get("state") == "WAIT_EXPORT_ACCEPT" and has_bound_export and snapshot_current
        )
        result["deliveryAcceptanceBlockers"] = [] if result["deliveryAcceptanceReady"] else ([{
            "code": "CONSUMER_SNAPSHOT_NOT_CURRENT",
            "message": "最终交付包尚未绑定当前对象级消费者快照，或绑定后消费者对象已发生变化。",
        }] if result.get("state") == "WAIT_EXPORT_ACCEPT" else [])
        result["physicalPurgeAuthorized"] = False
        return result

    lifecycle_module.preview_module_offboarding = preview_module_offboarding
    lifecycle_module._validate_export_contract = validate_export_contract
    lifecycle_module.get_module_offboarding_job = get_module_offboarding_job
    lifecycle_module._m45_consumer_closure_installed = True
    return lifecycle_module
