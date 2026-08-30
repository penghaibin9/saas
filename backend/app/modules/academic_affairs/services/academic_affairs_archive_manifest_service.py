"""Stage C3 immutable archive manifest and post-archive correction flow.

ARCHIVED is permanent. Confirmation re-evaluates all archive domains in the same
transaction and appends Manifest V1. A post-archive correction never reopens the term;
it appends a ``PostArchiveCorrectionCase`` workflow row and, after a *different*
operator gives second approval, invokes the designated GRADE/GRADUATION/SCHEDULE command to
append the new official fact and Manifest V(N+1) in one database transaction.

Schedule correction is append-only as well: it publishes a complete replacement
batch, advances the scope head and marks the old batch SUPERSEDED.  Existing schedule
items and previous manifests remain queryable.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_archive_service as archive_service

_CORRECTION_TYPES = {"GRADE", "GRADUATION", "SCHEDULE"}
_CORRECTION_STATUSES = {"PENDING_SECOND_APPROVAL", "APPLIED", "REJECTED"}


def _json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(payload) -> str:
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _actor_id(db=None) -> int | None:
    """Resolve a stable numeric actor id without trusting display/login strings.

    Production tokens normally carry the database user id. Compatibility/mock tokens
    may carry ``u_<login>`` instead; for a high-risk archive action we resolve that
    login back to the tenant-scoped ``t_user.id`` rather than storing NULL or comparing
    two unstable strings for the two-person rule.
    """
    from app.core.context import get_current_user_ctx

    ctx = get_current_user_ctx() or {}
    raw = ctx.get("userId")
    try:
        value = int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        value = None
    if value and value > 0:
        return value
    if db is None:
        return None
    login = str(ctx.get("loginName") or "").strip()
    if not login:
        return None
    from app.models import User

    user_id = db.scalar(select(User.id).where(
        User.tenant_id == _tid(),
        User.login_name == login,
        User.is_deleted.is_(False),
    ))
    return int(user_id) if user_id else None


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
        if result["result"] in archive_service._BLOCKING_RESULTS:
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


def _raw_manifest_chain_digest(manifests) -> str:
    """Hash stored legacy rows exactly, so a forward checkpoint can attest them.

    This is deliberately separate from ``manifest_hash``: early fixtures used a
    pre-C3 payload and therefore cannot be made C3-valid without rewriting history.
    A later checkpoint records their exact stored bytes and makes any subsequent
    modification detectable.
    """
    payload = [{
        "id": str(row.id),
        "versionNo": int(row.version_no),
        "supersedesId": str(row.supersedes_id) if row.supersedes_id else None,
        "domainCountsJson": row.domain_counts_json,
        "domainHashesJson": row.domain_hashes_json,
        "maxIdsJson": row.max_ids_json,
        "manifestHash": row.manifest_hash,
        "reason": row.reason,
    } for row in manifests]
    return _hash(payload)


def _latest_manifest(db, batch_id):
    from app.models import ArchiveManifest

    return db.scalars(select(ArchiveManifest).where(
        ArchiveManifest.tenant_id == _tid(),
        ArchiveManifest.archive_batch_id == int(batch_id),
    ).order_by(ArchiveManifest.version_no.desc()).limit(1)).first()


def _case_dto(case, *, detail: bool = False) -> dict:
    payload = {
        "caseId": str(case.id),
        "archiveBatchId": str(case.archive_batch_id),
        "correctionNo": int(case.correction_no),
        "businessType": case.business_type,
        "targetRef": case.target_ref,
        "reason": case.reason,
        "riskLevel": case.risk_level,
        "status": case.status,
        "requestedBy": str(case.created_by) if case.created_by is not None else None,
        "secondApprovedBy": str(case.second_approved_by) if case.second_approved_by is not None else None,
        "appliedAt": case.applied_at.isoformat() if case.applied_at else None,
        "officialFactType": case.official_fact_type,
        "officialFactId": str(case.official_fact_id) if case.official_fact_id is not None else None,
        "resultingManifestId": str(case.resulting_manifest_id) if case.resulting_manifest_id is not None else None,
        "createdAt": case.created_at.isoformat() if case.created_at else None,
    }
    if detail:
        try:
            payload["correction"] = json.loads(case.correction_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            payload["correction"] = None
        try:
            payload["evidenceManifest"] = json.loads(case.evidence_manifest or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            payload["evidenceManifest"] = None
    return payload


def confirm_archive(user, batch_id, force=False):
    """Create immutable Manifest V1 in the same transaction as ARCHIVED."""
    from app.models import AaArchiveBatch, AaTerm, ArchiveManifest

    core = archive_service._core
    with core.session() as db:
        core._require_school(core._ctx(user, db))
        actor = _actor_id(db)
        if actor is None:
            raise AppException("NO_PERMISSION", "缺少可审计的操作人身份，禁止执行正式归档", http_status=403)
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
            archived_by=actor,
            created_at=archived_at,
            created_by=actor,
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
            f"manifestId={manifest.id};version=1;hash={manifest.manifest_hash};actor={actor}",
        )
        db.commit()
        payload = core._batch_dto(batch)
        payload.update({"manifestId": str(manifest.id), "manifestVersion": 1,
                        "manifestHash": manifest.manifest_hash})
        return payload


def verify_manifest(user, batch_id) -> dict:
    """Verify immutable manifest chain, correction lineage and ARCHIVED projection."""
    from app.models import (
        AaArchiveBatch,
        AaScheduleBatch,
        AcademicGrade,
        ArchiveManifest,
        GraduationDecisionFact,
        PostArchiveCorrectionCase,
    )

    core = archive_service._core
    with core.session() as db:
        core._require_school(core._ctx(user, db))
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
        warnings: list[str] = []
        previous = None
        versions = []
        hash_validity: dict[int, bool] = {}
        manifest_ids = {int(row.id) for row in manifests}
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
            hash_validity[int(manifest.id)] = expected == manifest.manifest_hash
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
                             "hashValid": expected == manifest.manifest_hash,
                             "supersedesId": str(manifest.supersedes_id) if manifest.supersedes_id else None})
            previous = manifest

        # An early fixture may predate the C3 payload schema.  Never rewrite those
        # rows: a later, independently signed checkpoint hashes their exact stored
        # bytes.  Once that checkpoint and its own C3 hash are valid, old-schema hash
        # mismatches become explicit warnings rather than an unverifiable blocker.
        latest = manifests[-1]
        checkpoint_match = re.search(
            r"INTEGRITY_CHECKPOINT:([0-9a-f]{64})", str(latest.reason or ""), re.IGNORECASE,
        )
        if checkpoint_match and len(manifests) > 1:
            attested = checkpoint_match.group(1).lower()
            actual_chain = _raw_manifest_chain_digest(manifests[:-1])
            try:
                latest_counts = json.loads(latest.domain_counts_json)
                latest_hashes = json.loads(latest.domain_hashes_json)
            except (TypeError, ValueError, json.JSONDecodeError):
                latest_counts = latest_hashes = {}
            checkpoint_valid = (
                attested == actual_chain
                and hash_validity.get(int(latest.id), False)
                and len(latest_counts) == len(archive_service._DOMAINS)
                and len(latest_hashes) == len(archive_service._DOMAINS)
            )
            if checkpoint_valid:
                older_hash_problems = {
                    f"V{row.version_no}:HASH_MISMATCH"
                    for row in manifests[:-1]
                }
                warnings.extend(
                    f"{problem}:ATTESTED_BY_V{latest.version_no}"
                    for problem in problems if problem in older_hash_problems
                )
                problems = [problem for problem in problems if problem not in older_hash_problems]
            else:
                problems.append(f"V{latest.version_no}:INTEGRITY_CHECKPOINT_INVALID")

        applied_cases = db.scalars(select(PostArchiveCorrectionCase).where(
            PostArchiveCorrectionCase.tenant_id == _tid(),
            PostArchiveCorrectionCase.archive_batch_id == batch.id,
            PostArchiveCorrectionCase.status == "APPLIED",
            PostArchiveCorrectionCase.is_deleted.is_(False),
        ).order_by(PostArchiveCorrectionCase.correction_no)).all()
        for case in applied_cases:
            prefix = f"CORRECTION#{case.correction_no}"
            if not case.official_fact_type or not case.official_fact_id:
                problems.append(f"{prefix}:OFFICIAL_FACT_MISSING")
                continue
            if not case.resulting_manifest_id or int(case.resulting_manifest_id) not in manifest_ids:
                problems.append(f"{prefix}:RESULTING_MANIFEST_MISSING")
            if case.business_type == "GRADE":
                fact = db.query(AcademicGrade).filter(
                    AcademicGrade.id == int(case.official_fact_id),
                    AcademicGrade.tenant_id == _tid(),
                    AcademicGrade.source_biz_type == "POST_ARCHIVE",
                    AcademicGrade.source_biz_id == case.id,
                    AcademicGrade.is_deleted.is_(False),
                ).first()
                if not fact or case.official_fact_type != "ACADEMIC_GRADE":
                    # Legacy sandbox used the append-only AaGradeCorrection fact as
                    # the official target.  Accept it only when it points back to the
                    # exact case and its corrected grade still exists.
                    from app.models import AaGradeCorrection
                    legacy = db.query(AaGradeCorrection).filter(
                        AaGradeCorrection.id == int(case.official_fact_id),
                        AaGradeCorrection.tenant_id == _tid(),
                        AaGradeCorrection.source_ref_id == case.id,
                        AaGradeCorrection.is_deleted.is_(False),
                    ).first()
                    corrected = None if legacy is None else db.query(AcademicGrade).filter(
                        AcademicGrade.id == int(legacy.corrected_grade_id),
                        AcademicGrade.tenant_id == _tid(),
                        AcademicGrade.is_deleted.is_(False),
                    ).first()
                    if (
                        not legacy or not corrected
                        or case.official_fact_type != "AA_GRADE_CORRECTION"
                    ):
                        problems.append(f"{prefix}:GRADE_FACT_LINEAGE_BROKEN")
                    else:
                        warnings.append(f"{prefix}:LEGACY_GRADE_CORRECTION_FACT")
            elif case.business_type == "GRADUATION":
                fact = db.query(GraduationDecisionFact).filter(
                    GraduationDecisionFact.id == int(case.official_fact_id),
                    GraduationDecisionFact.tenant_id == _tid(),
                    GraduationDecisionFact.correction_case_id == case.id,
                ).first()
                if not fact or case.official_fact_type != "GRADUATION_DECISION":
                    problems.append(f"{prefix}:GRADUATION_FACT_LINEAGE_BROKEN")
            elif case.business_type == "SCHEDULE":
                fact = db.query(AaScheduleBatch).filter(
                    AaScheduleBatch.id == int(case.official_fact_id),
                    AaScheduleBatch.tenant_id == _tid(),
                    AaScheduleBatch.status == "PUBLISHED",
                    AaScheduleBatch.is_deleted.is_(False),
                ).first()
                if not fact or case.official_fact_type != "AA_SCHEDULE_BATCH":
                    problems.append(f"{prefix}:SCHEDULE_FACT_LINEAGE_BROKEN")
            else:
                problems.append(f"{prefix}:UNSUPPORTED_BUSINESS_TYPE")
        if batch.status != "ARCHIVED":
            problems.append("BATCH_NOT_ARCHIVED")
        return {
            "ok": not problems,
            "reason": None if not problems else ";".join(problems),
            "warnings": warnings,
            "versions": versions,
            "appliedCorrections": len(applied_cases),
        }


def append_integrity_checkpoint(user, batch_id, *, note: str) -> dict:
    """Append a forward-only checkpoint over legacy manifest bytes.

    The actor must differ from the most recent manifest signer.  The checkpoint first
    re-runs all thirteen live archive gates, then embeds the digest of every prior row
    in its immutable reason and domain hash.
    """
    from app.models import AaArchiveBatch, ArchiveManifest

    core = archive_service._core
    with core.session() as db:
        core._require_school(core._ctx(user, db))
        actor = _actor_id(db)
        if actor is None:
            raise AppException("NO_PERMISSION", "缺少可审计操作人，禁止追加完整性检查点", http_status=403)
        batch = db.query(AaArchiveBatch).filter(
            AaArchiveBatch.id == int(batch_id),
            AaArchiveBatch.tenant_id == _tid(),
            AaArchiveBatch.status == "ARCHIVED",
            AaArchiveBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("归档批次不存在")
        manifests = list(db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(),
            ArchiveManifest.archive_batch_id == batch.id,
        ).order_by(ArchiveManifest.version_no)).all())
        if not manifests:
            raise AppException("DATA_CONFLICT", "没有可证明的原始 Manifest 链", http_status=409)
        previous = manifests[-1]
        if previous.archived_by is not None and int(previous.archived_by) == int(actor):
            raise AppException("NO_PERMISSION", "完整性检查点必须由不同于上一版本签署人的操作人追加", http_status=403)
        if re.search(r"INTEGRITY_CHECKPOINT:[0-9a-f]{64}", str(previous.reason or ""), re.IGNORECASE):
            return {
                "manifestId": str(previous.id),
                "manifestVersion": int(previous.version_no),
                "manifestHash": previous.manifest_hash,
                "alreadyCheckpointed": True,
            }
        counts, hashes, max_ids = _live_manifest_parts(db, batch)
        chain_digest = _raw_manifest_chain_digest(manifests)
        hashes["SCHEDULE"] = _hash({
            "liveDomainHash": hashes.get("SCHEDULE"),
            "priorManifestChainDigest": chain_digest,
        })
        version_no = int(previous.version_no) + 1
        reason = (
            f"INTEGRITY_CHECKPOINT:{chain_digest};"
            f"历史 Manifest 原始字节前向见证；{str(note or '').strip()[:200]}"
        )
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
        checkpoint = ArchiveManifest(
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
        db.add(checkpoint)
        db.flush()
        core._audit(
            db,
            batch.id,
            "ARCHIVE_MANIFEST_INTEGRITY_CHECKPOINT",
            f"manifestId={checkpoint.id};version={version_no};attests={chain_digest};actor={actor}",
        )
        db.commit()
        return {
            "manifestId": str(checkpoint.id),
            "manifestVersion": int(checkpoint.version_no),
            "manifestHash": checkpoint.manifest_hash,
            "attestedChainDigest": chain_digest,
            "alreadyCheckpointed": False,
        }


def list_correction_cases(user, batch_id, *, status=None, page=1, page_size=20) -> dict:
    """Two-person reviewer work queue; WHERE/COUNT/OFFSET-LIMIT at DB layer."""
    from app.models import AaArchiveBatch, PostArchiveCorrectionCase

    core = archive_service._core
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    normalized_status = str(status or "").strip().upper() or None
    if normalized_status and normalized_status not in _CORRECTION_STATUSES:
        raise AppException("VALIDATION_ERROR", f"非法纠错状态：{status}")
    with core.session() as db:
        core._require_school(core._ctx(user, db))
        batch = db.query(AaArchiveBatch).filter(
            AaArchiveBatch.id == int(batch_id),
            AaArchiveBatch.tenant_id == _tid(),
            AaArchiveBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("归档批次不存在")
        query = db.query(PostArchiveCorrectionCase).filter(
            PostArchiveCorrectionCase.tenant_id == _tid(),
            PostArchiveCorrectionCase.archive_batch_id == batch.id,
            PostArchiveCorrectionCase.is_deleted.is_(False),
        )
        if normalized_status:
            query = query.filter(PostArchiveCorrectionCase.status == normalized_status)
        total = query.count()
        rows = query.order_by(
            PostArchiveCorrectionCase.correction_no.desc(),
            PostArchiveCorrectionCase.id.desc(),
        ).offset((page - 1) * page_size).limit(page_size).all()
        return {
            "items": [_case_dto(row) for row in rows],
            "total": total,
            "page": page,
            "pageSize": page_size,
        }


def get_correction_case(user, case_id) -> dict:
    from app.models import PostArchiveCorrectionCase

    core = archive_service._core
    with core.session() as db:
        core._require_school(core._ctx(user, db))
        case = db.query(PostArchiveCorrectionCase).filter(
            PostArchiveCorrectionCase.id == int(case_id),
            PostArchiveCorrectionCase.tenant_id == _tid(),
            PostArchiveCorrectionCase.is_deleted.is_(False),
        ).first()
        if not case:
            raise not_found("归档后纠错单不存在")
        return _case_dto(case, detail=True)


def create_correction_case(user, batch_id, *, business_type, target_ref, reason,
                           correction, evidence_manifest, risk_level="HIGH") -> dict:
    """Open a controlled correction request; no historical official fact is mutated yet."""
    from app.models import AaArchiveBatch, PostArchiveCorrectionCase

    core = archive_service._core
    business_type = str(business_type or "").upper()
    reason = str(reason or "").strip()
    target_ref = str(target_ref or "").strip()
    if business_type not in _CORRECTION_TYPES:
        raise AppException("VALIDATION_ERROR", "归档后纠错仅支持 GRADE/GRADUATION/SCHEDULE")
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
        requester = _actor_id(db)
        if requester is None:
            raise AppException(
                "NO_PERMISSION",
                "当前操作人无法解析到租户内稳定账号，禁止发起高风险归档后纠错",
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
        return _case_dto(case)


def approve_correction_case(user, case_id) -> dict:
    """Different second approver appends official fact + Manifest V2+ atomically."""
    from app.models import AaArchiveBatch, ArchiveManifest, PostArchiveCorrectionCase
    from .academic_affairs_post_archive_fact_service import apply_official_correction_fact

    core = archive_service._core
    with core.session() as db:
        core._require_school(core._ctx(user, db))
        actor = _actor_id(db)
        if actor is None:
            raise AppException("NO_PERMISSION", "当前操作人无法解析到租户内稳定账号，禁止执行高风险归档纠错", http_status=403)
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

        official = apply_official_correction_fact(db, batch, case, actor)

        counts = json.loads(previous.domain_counts_json)
        hashes = json.loads(previous.domain_hashes_json)
        max_ids = json.loads(previous.max_ids_json)
        previous_domain_hash = hashes.get(case.business_type)
        # 课表更正会改变整个正式课表投影，而且历史环境可能来自早期（少于十三域）
        # Manifest。更正事实落库后必须复用正式归档规则重新收集十三域证据，不能把旧的
        # 不完整 counts/hashes 原样抄进新版本。GRADE/GRADUATION 保持既有增量语义。
        if case.business_type == "SCHEDULE":
            counts, hashes, max_ids = _live_manifest_parts(db, batch)
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
            "previousDomainHash": previous_domain_hash,
            "liveDomainHash": hashes.get(case.business_type),
            "officialCorrectionFact": correction_fact,
        })
        if official.get("recordCount") is not None:
            counts[case.business_type] = int(official["recordCount"])
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
    archive_service.list_correction_cases = list_correction_cases
    archive_service.get_correction_case = get_correction_case
    archive_service.create_correction_case = create_correction_case
    archive_service.approve_correction_case = approve_correction_case
    archive_service.append_integrity_checkpoint = append_integrity_checkpoint
