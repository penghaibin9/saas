"""Stage C3 immutable archive manifest and post-archive correction flow.

ARCHIVED is permanent. Confirmation re-evaluates all archive domains in the same
transaction and appends Manifest V1. A post-archive correction never reopens the term;
it appends a ``PostArchiveCorrectionCase`` workflow row and, after a *different*
operator gives second approval, invokes the designated GRADE/GRADUATION command to
append the new official fact and Manifest V(N+1) in one database transaction.

First production scope is intentionally limited to GRADE and GRADUATION.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_archive_service as archive_service

_CORRECTION_TYPES = {"GRADE", "GRADUATION"}


def _json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(payload) -> str:
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _actor_id() -> int | None:
    from app.core.context import get_current_user_ctx

    raw = (get_current_user_ctx() or {}).get("userId")
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _max_numeric_ids(payload) -> int | None:
    values: list[int] = []

    def walk(value, key=""):
        if isinstance(value, dict):
            for child_key, child in value.items():
                walk(child, str(child_key))
        elif isinstance(value, list):
            for child in value:
                walk(child, key)
        elif key.lower().endswith("id") or key.lower().endswith("ids"):
            try:
                values.append(int(value))
            except (TypeError, ValueError):
                return

    walk(payload)
    return max(values) if values else None


def _live_manifest_parts(db, batch) -> tuple[dict, dict, dict]:
    """Re-evaluate formal archive rules and return deterministic manifest components."""
    evaluated = archive_service._evaluate_domains(db, batch.term_id, batch.term_code)
    domain_counts: dict[str, int] = {}
    domain_hashes: dict[str, str] = {}
    max_ids: dict[str, int | None] = {}
    blocked: list[str] = []
    for code, _label in archive_service._DOMAINS:
        result = archive_service._public_result(code, evaluated[code])
        if result["result"] != "PASS":
            blocked.append(f"{code}:{result['ruleCode']}")
        stable = {
            "domain": code,
            "recordCount": int(result["recordCount"] or 0),
            "result": result["result"],
            "ruleCode": result["ruleCode"],
            "blockingCount": int(result["blockingCount"] or 0),
            "summary": result["summary"],
            "evidence": result["evidence"],
        }
        domain_counts[code] = stable["recordCount"]
        domain_hashes[code] = _hash(stable)
        max_ids[code] = _max_numeric_ids(stable)
    if blocked:
        raise AppException(
            "DATA_CONFLICT",
            "归档确认前实时复核发现阻断项，禁止使用历史 READY 状态直接封存",
            details={"blockingRules": blocked},
            http_status=409,
        )
    return domain_counts, domain_hashes, max_ids


def _manifest_payload(*, batch, version_no: int, domain_counts: dict, domain_hashes: dict,
                      max_ids: dict, supersedes_id=None, reason: str) -> dict:
    return {
        "schema": "AA_ARCHIVE_MANIFEST_C3_V1",
        "archiveBatchId": str(batch.id),
        "termId": str(batch.term_id) if batch.term_id is not None else None,
        "termCode": batch.term_code,
        "versionNo": int(version_no),
        "domainCounts": domain_counts,
        "domainHashes": domain_hashes,
        "maxIds": max_ids,
        "supersedesId": str(supersedes_id) if supersedes_id else None,
        "reason": reason,
    }


def _latest_manifest(db, batch_id):
    from app.models import ArchiveManifest

    return db.scalars(select(ArchiveManifest).where(
        ArchiveManifest.tenant_id == _tid(),
        ArchiveManifest.archive_batch_id == int(batch_id),
    ).order_by(ArchiveManifest.version_no.desc()).limit(1)).first()


def confirm_archive(user, batch_id, force=False):
    """Create immutable Manifest V1 in the same transaction as ARCHIVED."""
    from app.models import AaArchiveBatch, AaTerm, ArchiveManifest

    core = archive_service._core
    with core.session() as db:
        core._require_school(core._ctx(user, db))
        batch = db.query(AaArchiveBatch).filter(
            AaArchiveBatch.id == int(batch_id),
            AaArchiveBatch.tenant_id == _tid(),
            AaArchiveBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("归档批次不存在")
        if batch.status == "ARCHIVED":
            manifest = _latest_manifest(db, batch.id)
            if not manifest:
                raise AppException(
                    "DATA_CONFLICT",
                    "该历史批次已标记 ARCHIVED 但缺少 ArchiveManifest，禁止按不完整归档事实继续操作",
                    http_status=409,
                )
            payload = core._batch_dto(batch)
            payload.update({"manifestId": str(manifest.id), "manifestVersion": manifest.version_no,
                            "manifestHash": manifest.manifest_hash})
            return payload
        if batch.status == "MISSING_ITEMS":
            raise core._invalid(
                f"仍有 {batch.missing_count} 个业务域未满足归档规则。整体强制归档已停用，请逐项处理后重新检查"
            )
        if batch.status != "READY":
            raise core._invalid("仅语义完整性检查通过（READY）的批次可确认归档")

        # Do not trust a stale READY projection: recompute immediately before sealing.
        counts, hashes, max_ids = _live_manifest_parts(db, batch)
        existing = _latest_manifest(db, batch.id)
        if existing:
            raise AppException("DATA_CONFLICT", "未归档批次已存在正式 Manifest，数据状态异常", http_status=409)
        archived_at = datetime.utcnow()
        reason = "正式归档：实时语义门禁通过"
        manifest_payload = _manifest_payload(
            batch=batch,
            version_no=1,
            domain_counts=counts,
            domain_hashes=hashes,
            max_ids=max_ids,
            reason=reason,
        )
        manifest = ArchiveManifest(
            tenant_id=_tid(),
            term_id=batch.term_id,
            version_no=1,
            archive_batch_id=batch.id,
            domain_counts_json=_json(counts),
            domain_hashes_json=_json(hashes),
            max_ids_json=_json(max_ids),
            manifest_hash=_hash(manifest_payload),
            reason=reason,
            supersedes_id=None,
            archived_at=archived_at,
            archived_by=_actor_id(),
            created_at=archived_at,
            created_by=_actor_id(),
        )
        db.add(manifest)
        db.flush()
        batch.status = "ARCHIVED"
        batch.archived_at = archived_at
        if batch.term_id:
            term = db.query(AaTerm).filter(
                AaTerm.id == batch.term_id,
                AaTerm.tenant_id == _tid(),
                AaTerm.is_deleted.is_(False),
            ).with_for_update().first()
            if term:
                term.status = "ARCHIVED"
        core._audit(
            db,
            batch.id,
            "ARCHIVE_CONFIRM_IMMUTABLE",
            f"manifestId={manifest.id};version=1;hash={manifest.manifest_hash}",
        )
        db.commit()
        payload = core._batch_dto(batch)
        payload.update({"manifestId": str(manifest.id), "manifestVersion": 1,
                        "manifestHash": manifest.manifest_hash})
        return payload


def verify_manifest(user, batch_id) -> dict:
    """Verify immutable manifest chain and current ARCHIVED projection."""
    from app.models import AaArchiveBatch, ArchiveManifest

    core = archive_service._core
    with core.session() as db:
        core._ctx(user, db)
        batch = db.query(AaArchiveBatch).filter(
            AaArchiveBatch.id == int(batch_id),
            AaArchiveBatch.tenant_id == _tid(),
            AaArchiveBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("归档批次不存在")
        manifests = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(),
            ArchiveManifest.archive_batch_id == batch.id,
        ).order_by(ArchiveManifest.version_no)).all()
        if not manifests:
            return {"ok": False, "reason": "MANIFEST_MISSING", "versions": []}
        problems: list[str] = []
        previous = None
        versions = []
        for manifest in manifests:
            payload = _manifest_payload(
                batch=batch,
                version_no=manifest.version_no,
                domain_counts=json.loads(manifest.domain_counts_json),
                domain_hashes=json.loads(manifest.domain_hashes_json),
                max_ids=json.loads(manifest.max_ids_json),
                supersedes_id=manifest.supersedes_id,
                reason=manifest.reason,
            )
            expected = _hash(payload)
            if expected != manifest.manifest_hash:
                problems.append(f"V{manifest.version_no}:HASH_MISMATCH")
            if previous is None:
                if manifest.version_no != 1 or manifest.supersedes_id is not None:
                    problems.append(f"V{manifest.version_no}:BAD_CHAIN_ROOT")
            else:
                if manifest.version_no != previous.version_no + 1 or manifest.supersedes_id != previous.id:
                    problems.append(f"V{manifest.version_no}:BAD_SUPERSEDES")
            versions.append({"manifestId": str(manifest.id), "versionNo": manifest.version_no,
                             "hash": manifest.manifest_hash,
                             "supersedesId": str(manifest.supersedes_id) if manifest.supersedes_id else None})
            previous = manifest
        if batch.status != "ARCHIVED":
            problems.append("BATCH_NOT_ARCHIVED")
        return {"ok": not problems, "reason": None if not problems else ";".join(problems), "versions": versions}


def create_correction_case(user, batch_id, *, business_type, target_ref, reason,
                           correction, evidence_manifest, risk_level="HIGH") -> dict:
    """Open a controlled correction request; no historical official fact is mutated yet."""
    from app.models import AaArchiveBatch, PostArchiveCorrectionCase

    core = archive_service._core
    business_type = str(business_type or "").upper()
    reason = str(reason or "").strip()
    target_ref = str(target_ref or "").strip()
    if business_type not in _CORRECTION_TYPES:
        raise AppException("VALIDATION_ERROR", "Stage C3 首期归档后纠错仅支持 GRADE/GRADUATION")
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "归档后纠错原因至少 5 字")
    if not target_ref:
        raise AppException("VALIDATION_ERROR", "纠错目标引用不能为空")
    if not isinstance(correction, dict) or not correction:
        raise AppException("VALIDATION_ERROR", "纠错内容不能为空")
    if not isinstance(evidence_manifest, dict) or not evidence_manifest:
        raise AppException("VALIDATION_ERROR", "纠错证据清单不能为空")

    with core.session() as db:
        core._require_school(core._ctx(user, db))
        requester = _actor_id()
        if requester is None:
            raise AppException(
                "NO_PERMISSION",
                "当前操作人缺少稳定数字 userId，禁止发起高风险归档后纠错",
                http_status=403,
            )
        batch = db.query(AaArchiveBatch).filter(
            AaArchiveBatch.id == int(batch_id),
            AaArchiveBatch.tenant_id == _tid(),
            AaArchiveBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("归档批次不存在")
        if batch.status != "ARCHIVED":
            raise AppException("DATA_CONFLICT", "仅正式 ARCHIVED 批次可发起归档后纠错", http_status=409)
        latest = _latest_manifest(db, batch.id)
        if not latest:
            raise AppException("DATA_CONFLICT", "缺少原 ArchiveManifest，禁止建立不可验证的纠错链", http_status=409)
        max_no = db.scalar(select(func.max(PostArchiveCorrectionCase.correction_no)).where(
            PostArchiveCorrectionCase.tenant_id == _tid(),
            PostArchiveCorrectionCase.archive_batch_id == batch.id,
            PostArchiveCorrectionCase.is_deleted.is_(False),
        )) or 0
        case = PostArchiveCorrectionCase(
            tenant_id=_tid(),
            archive_batch_id=batch.id,
            correction_no=int(max_no) + 1,
            business_type=business_type,
            target_ref=target_ref,
            reason=reason,
            correction_json=_json(correction),
            evidence_manifest=_json(evidence_manifest),
            risk_level=str(risk_level or "HIGH").upper(),
            status="PENDING_SECOND_APPROVAL",
            created_by=requester,
            updated_by=requester,
        )
        db.add(case)
        db.flush()
        core._audit(db, batch.id, "POST_ARCHIVE_CORRECTION_CREATE",
                    f"caseId={case.id};type={business_type};target={target_ref};requester={requester}")
        db.commit()
        return {"caseId": str(case.id), "correctionNo": case.correction_no,
                "status": case.status, "businessType": case.business_type}


def approve_correction_case(user, case_id) -> dict:
    """Different second approver appends official fact + Manifest V2+ atomically."""
    from app.models import AaArchiveBatch, ArchiveManifest, PostArchiveCorrectionCase
    from .academic_affairs_post_archive_fact_service import apply_official_correction_fact

    core = archive_service._core
    with core.session() as db:
        core._require_school(core._ctx(user, db))
        actor = _actor_id()
        if actor is None:
            raise AppException("NO_PERMISSION", "当前操作人缺少稳定数字 userId，禁止执行高风险归档纠错", http_status=403)
        case = db.query(PostArchiveCorrectionCase).filter(
            PostArchiveCorrectionCase.id == int(case_id),
            PostArchiveCorrectionCase.tenant_id == _tid(),
            PostArchiveCorrectionCase.is_deleted.is_(False),
        ).with_for_update().first()
        if not case:
            raise not_found("归档后纠错单不存在")
        if case.status != "PENDING_SECOND_APPROVAL":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该纠错单当前状态不可二次审批")
        if case.created_by is None:
            raise AppException(
                "DATA_CONFLICT",
                "该高风险纠错单缺少发起人审计身份，无法证明双人复核，禁止应用",
                http_status=409,
            )
        if int(case.created_by) == int(actor):
            raise AppException("NO_PERMISSION", "归档后纠错必须由不同操作人二次审批", http_status=403)

        batch = db.query(AaArchiveBatch).filter(
            AaArchiveBatch.id == case.archive_batch_id,
            AaArchiveBatch.tenant_id == _tid(),
            AaArchiveBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch or batch.status != "ARCHIVED":
            raise AppException("DATA_CONFLICT", "纠错应用时归档批次不再处于 ARCHIVED，已拒绝", http_status=409)
        previous = _latest_manifest(db, batch.id)
        if not previous:
            raise AppException("DATA_CONFLICT", "原 ArchiveManifest 缺失，已拒绝纠错", http_status=409)

        # Critical Stage C3 invariant: the designated domain command creates the new
        # official fact *before* Manifest V2 is assembled, in this same transaction.
        official = apply_official_correction_fact(db, batch, case, actor)

        counts = json.loads(previous.domain_counts_json)
        hashes = json.loads(previous.domain_hashes_json)
        max_ids = json.loads(previous.max_ids_json)
        correction_fact = {
            "caseId": str(case.id),
            "correctionNo": case.correction_no,
            "businessType": case.business_type,
            "targetRef": case.target_ref,
            "reason": case.reason,
            "correction": json.loads(case.correction_json),
            "evidenceManifest": json.loads(case.evidence_manifest),
            "requestedBy": int(case.created_by),
            "secondApprovedBy": actor,
            "officialFactType": official["factType"],
            "officialFactId": str(official["factId"]),
            "beforeHash": official["beforeHash"],
            "afterHash": official["afterHash"],
            "officialSnapshot": official["snapshot"],
            "lineage": official["lineage"],
        }
        hashes[case.business_type] = _hash({
            "previousDomainHash": hashes.get(case.business_type),
            "officialCorrectionFact": correction_fact,
        })
        old_max = max_ids.get(case.business_type)
        try:
            old_max_int = int(old_max) if old_max is not None else 0
        except (TypeError, ValueError):
            old_max_int = 0
        max_ids[case.business_type] = max(old_max_int, int(official["factId"]))

        version_no = int(previous.version_no) + 1
        reason = f"归档后纠错 #{case.correction_no}: {case.reason}"
        payload = _manifest_payload(
            batch=batch,
            version_no=version_no,
            domain_counts=counts,
            domain_hashes=hashes,
            max_ids=max_ids,
            supersedes_id=previous.id,
            reason=reason,
        )
        now = datetime.utcnow()
        manifest = ArchiveManifest(
            tenant_id=_tid(),
            term_id=batch.term_id,
            version_no=version_no,
            archive_batch_id=batch.id,
            domain_counts_json=_json(counts),
            domain_hashes_json=_json(hashes),
            max_ids_json=_json(max_ids),
            manifest_hash=_hash(payload),
            reason=reason,
            supersedes_id=previous.id,
            archived_at=now,
            archived_by=actor,
            created_at=now,
            created_by=actor,
        )
        db.add(manifest)
        db.flush()
        case.second_approved_by = actor
        case.applied_at = now
        case.official_fact_type = official["factType"]
        case.official_fact_id = int(official["factId"])
        case.resulting_manifest_id = manifest.id
        case.status = "APPLIED"
        case.updated_by = actor
        core._audit(
            db,
            batch.id,
            "POST_ARCHIVE_CORRECTION_APPLY",
            (
                f"caseId={case.id};type={case.business_type};officialFact={official['factType']}:"
                f"{official['factId']};manifestV={version_no};manifestId={manifest.id};"
                f"requester={case.created_by};secondApprover={actor}"
            ),
        )
        db.commit()
        return {
            "caseId": str(case.id),
            "status": case.status,
            "officialFactType": case.official_fact_type,
            "officialFactId": str(case.official_fact_id),
            "manifestId": str(manifest.id),
            "manifestVersion": manifest.version_no,
            "manifestHash": manifest.manifest_hash,
            "supersedesId": str(previous.id),
        }


def install() -> None:
    archive_service.confirm_archive = confirm_archive
    archive_service.verify_manifest = verify_manifest
    archive_service.create_correction_case = create_correction_case
    archive_service.approve_correction_case = approve_correction_case
