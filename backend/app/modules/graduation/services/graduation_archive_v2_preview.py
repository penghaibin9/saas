"""GD-018 V2 archive preview/freeze consistency bridge.

The legacy archive snapshot owns batch scope and business-state truth.  This module
adds the active material-rule contract and preserved FileVersion evidence without
replacing that snapshot.  Batch filing then prepares deterministic system snapshots,
re-verifies the exact user preview token, and finally re-checks the rule/material
fingerprint from inside the canonical manifest writer's final transaction.
"""
from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar
from collections import defaultdict

from sqlalchemy import and_, select

from app.core.exceptions import AppException
from app.models import GraduationGuidance, GraduationPlagiarismCheck
from app.models.file import FileObject, FileVersion
from app.models.graduation_material import (
    GraduationMaterialItem,
    GraduationMaterialRule,
    GraduationStudentMaterial,
)
from app.services.db_service import _tid, session
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED

_SYSTEM_SNAPSHOT_CODES = {
    "TASKBOOK", "PROPOSAL_REPORT", "PROPOSAL_DEFENSE", "GUIDANCE_RECORD",
    "MIDTERM_REPORT", "PLAGIARISM_REPORT", "REVIEW_ATTACHMENT",
    "DEFENSE_RECORD", "GRADE_MATERIAL",
}
_LEGACY_SOURCE_BY_CODE = {
    "TASKBOOK": "taskbook",
    "PROPOSAL_REPORT": "proposal",
    "MIDTERM_REPORT": "midterm",
    "REVIEW_ATTACHMENT": "review",
    "DEFENSE_RECORD": "defenseScore",
    "GRADE_MATERIAL": "grade",
}
_FREEZE_EXPECTED: ContextVar[dict | None] = ContextVar("gd_archive_v2_freeze_expected", default=None)


def _hash(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _locked(stmt, lock: bool):
    return stmt.with_for_update() if lock else stmt


def _load_rule_items(db, batch_id: int, *, lock: bool = False):
    stmt = select(GraduationMaterialRule, GraduationMaterialItem).join(
        GraduationMaterialItem,
        and_(
            GraduationMaterialItem.tenant_id == GraduationMaterialRule.tenant_id,
            GraduationMaterialItem.rule_id == GraduationMaterialRule.id,
            GraduationMaterialItem.enabled.is_(True),
            GraduationMaterialItem.is_deleted.is_(False),
        ),
    ).where(
        GraduationMaterialRule.tenant_id == _tid(),
        GraduationMaterialRule.batch_id == int(batch_id),
        GraduationMaterialRule.status == "ENABLED",
        GraduationMaterialRule.enabled.is_(True),
        GraduationMaterialRule.is_deleted.is_(False),
    ).order_by(
        GraduationMaterialRule.rule_version.desc(), GraduationMaterialRule.id.desc(),
        GraduationMaterialItem.sort_no, GraduationMaterialItem.id,
    )
    pairs = list(db.execute(_locked(stmt, lock)).all())
    rule_ids = {int(rule.id) for rule, _ in pairs}
    if not pairs:
        raise AppException("MATERIAL_RULE_NOT_INITIALIZED", "当前批次尚未初始化材料规则")
    if len(rule_ids) != 1:
        raise AppException("MATERIAL_RULE_CONFLICT", "当前批次存在多个启用材料规则")
    rule = pairs[0][0]
    items = [item for _, item in pairs]
    archive_items = [item for item in items if item.archive_required]
    projection = {
        "ruleId": str(rule.id), "ruleCode": rule.rule_code,
        "ruleVersion": int(rule.rule_version or 1),
        "items": [{
            "code": item.material_code, "name": item.material_name,
            "required": bool(item.required), "archiveRequired": bool(item.archive_required),
            "reviewRequired": bool(item.review_required), "versionPolicy": item.version_policy,
            "ownerRole": item.owner_role, "stage": item.biz_stage,
            "maxFiles": int(item.max_files or 1), "maxSizeBytes": int(item.max_size_bytes or 0),
            "allowedExt": item.allowed_ext_json or [],
        } for item in archive_items],
    }
    return rule, archive_items, _hash(projection)


def _load_material_rows(db, student_ids: list[int], *, lock: bool = False):
    if not student_ids:
        return {}
    stmt = select(GraduationStudentMaterial, FileVersion, FileObject).outerjoin(
        FileVersion,
        and_(
            FileVersion.tenant_id == GraduationStudentMaterial.tenant_id,
            FileVersion.id == GraduationStudentMaterial.current_version_id,
            FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
        ),
    ).outerjoin(
        FileObject,
        and_(
            FileObject.tenant_id == GraduationStudentMaterial.tenant_id,
            FileObject.id == FileVersion.file_object_id,
            FileObject.is_deleted.is_(False),
        ),
    ).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.gd_student_id.in_(student_ids),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).order_by(GraduationStudentMaterial.gd_student_id, GraduationStudentMaterial.material_code)
    grouped: dict[int, dict[str, tuple]] = defaultdict(dict)
    for material, version, file_obj in db.execute(_locked(stmt, lock)).all():
        grouped[int(material.gd_student_id)][str(material.material_code)] = (material, version, file_obj)
    return grouped


def _projection(material, version, file_obj) -> dict:
    return {
        "code": material.material_code,
        "materialVersion": int(material.version or 0),
        "ruleId": str(material.rule_id or ""), "ruleVersion": int(material.rule_version or 0),
        "businessStatus": material.business_status, "reviewStatus": material.review_status,
        "requiredStatus": material.required_status, "archiveStatus": material.archive_status,
        "currentVersionId": str(material.current_version_id or ""),
        "fileVersion": ({
            "id": str(version.id), "versionNo": int(version.version_no or 0),
            "sourceChannel": str(version.source_channel or "").upper(),
            "status": version.status, "isCurrent": bool(version.is_current),
            "fileObjectId": str(version.file_object_id),
        } if version else None),
        "fileObject": ({
            "id": str(file_obj.id), "status": file_obj.status,
            "scanStatus": str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper(),
            "sha256": file_obj.sha256 or "", "sizeBytes": int(file_obj.size_bytes or 0),
        } if file_obj else None),
    }


def _ready(material, version, file_obj) -> bool:
    if not material or not material.current_version_id or not version or not file_obj:
        return False
    if str(version.status or "").upper() != "APPROVED":
        return False
    if str(material.review_status or "").upper() not in {"APPROVED", "NOT_REQUIRED"}:
        return False
    scan = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
    if not is_downloadable_status(file_obj.status) or scan not in READY_SCAN_STATES:
        return False
    return bool(file_obj.sha256 and len(str(file_obj.sha256)) == 64)


def _material_hashes(items, grouped_materials: dict[int, dict[str, tuple]], student_ids: list[int]):
    archive_codes = {item.material_code for item in items}
    preserved: dict[int, str] = {}
    full: dict[int, str] = {}
    for sid in student_ids:
        all_rows = []
        preserved_rows = []
        for code in sorted(archive_codes):
            triple = grouped_materials.get(sid, {}).get(code)
            if not triple:
                continue
            material, version, file_obj = triple
            projected = _projection(material, version, file_obj)
            all_rows.append(projected)
            if version and str(version.source_channel or "").upper() != "SYSTEM_GENERATED":
                preserved_rows.append(projected)
        full[sid] = _hash(all_rows)
        preserved[sid] = _hash(preserved_rows)
    return preserved, full


def _source_maps(db, student_ids: list[int], *, lock: bool = False):
    guidance_ids: set[int] = set()
    plagiarism: dict[int, object] = {}
    if not student_ids:
        return guidance_ids, plagiarism
    guidance_stmt = select(GraduationGuidance).where(
        GraduationGuidance.tenant_id == _tid(),
        GraduationGuidance.gd_student_id.in_(student_ids),
        GraduationGuidance.void_reason.is_(None),
        GraduationGuidance.is_deleted.is_(False),
    ).order_by(GraduationGuidance.gd_student_id, GraduationGuidance.id)
    for row in db.scalars(_locked(guidance_stmt, lock)).all():
        guidance_ids.add(int(row.gd_student_id))
    plagiarism_stmt = select(GraduationPlagiarismCheck).where(
        GraduationPlagiarismCheck.tenant_id == _tid(),
        GraduationPlagiarismCheck.gd_student_id.in_(student_ids),
        GraduationPlagiarismCheck.status == "DONE",
        GraduationPlagiarismCheck.is_deleted.is_(False),
    ).order_by(GraduationPlagiarismCheck.gd_student_id, GraduationPlagiarismCheck.id)
    for row in db.scalars(_locked(plagiarism_stmt, lock)).all():
        sid = int(row.gd_student_id)
        current = plagiarism.get(sid)
        if current is None or int(row.id) > int(current.id):
            plagiarism[sid] = row
    return guidance_ids, plagiarism


def _source_ready(code: str, legacy_present: dict[str, bool], sid: int, guidance_ids: set[int], plagiarism: dict[int, object]) -> bool:
    legacy_key = _LEGACY_SOURCE_BY_CODE.get(code)
    if legacy_key:
        return bool(legacy_present.get(legacy_key))
    if code == "GUIDANCE_RECORD":
        return sid in guidance_ids
    if code == "PLAGIARISM_REPORT":
        row = plagiarism.get(sid)
        return bool(row and (not bool(row.over_threshold) or str(row.dispute_status or "").upper() == "APPROVED"))
    return False


def enrich_snapshot(db, batch, snapshot: dict, *, lock: bool = False) -> dict:
    """Add V2 rule/readiness and preserved-upload evidence using four bounded SQL reads."""
    rows = snapshot.get("rows") or []
    _, items, rule_hash = _load_rule_items(db, int(batch.id), lock=lock)
    student_ids = [int(row["studentId"]) for row in rows]
    grouped = _load_material_rows(db, student_ids, lock=lock)
    guidance_ids, plagiarism = _source_maps(db, student_ids, lock=lock)
    preserved_hashes, _ = _material_hashes(items, grouped, student_ids)

    for row in rows:
        sid = int(row["studentId"])
        legacy_present = {
            str(item.get("item")): bool(item.get("present"))
            for item in (row.get("checklist") or [])
        }
        legacy_labels = {str(item.get("label")) for item in (row.get("checklist") or [])}
        extras = [
            value for value in (row.get("missing") or [])
            if str(value) not in legacy_labels and str(value) != "成果定稿文件"
        ]
        checklist = []
        missing = []
        for item in items:
            triple = grouped.get(sid, {}).get(item.material_code)
            material, version, file_obj = triple if triple else (None, None, None)
            if material is not None:
                present = _ready(material, version, file_obj)
            elif item.material_code in _SYSTEM_SNAPSHOT_CODES:
                present = _source_ready(item.material_code, legacy_present, sid, guidance_ids, plagiarism)
            else:
                present = False
            checklist.append({
                "item": item.material_code, "label": item.material_name,
                "required": bool(item.required), "present": bool(present),
            })
            if item.required and not present:
                missing.append(item.material_name)
        row["checklist"] = checklist
        row["missing"] = list(dict.fromkeys([*missing, *extras]))
        row["v2RuleHash"] = rule_hash
        row["v2PreservedHash"] = preserved_hashes.get(sid, _hash([]))
    return snapshot


def _freeze_state(db, batch_id: int, student_ids: list[int], *, lock: bool = False):
    _, items, rule_hash = _load_rule_items(db, int(batch_id), lock=lock)
    grouped = _load_material_rows(db, student_ids, lock=lock)
    preserved, full = _material_hashes(items, grouped, student_ids)
    return {"ruleHash": rule_hash, "preserved": preserved, "full": full}


def _guarded_collect_factory(original_collect):
    def guarded_collect(db, student, user):
        expected = _FREEZE_EXPECTED.get()
        if expected:
            sid = int(student.id)
            state = _freeze_state(db, int(student.batch_id), [sid], lock=True)
            current_rule = state["ruleHash"]
            current_preserved = state["preserved"].get(sid, _hash([]))
            current_full = state["full"].get(sid, _hash([]))
            if (
                current_rule != expected.get("ruleHash")
                or current_preserved != expected.get("preservedHash")
                or current_full != expected.get("fullHash")
            ):
                raise AppException("DATA_CONFLICT", "归档预览后材料规则或 FileVersion 已变化，请重新预览")
        return original_collect(db, student, user)

    guarded_collect._gd_archive_v2_freeze_guard = True
    return guarded_collect


def install_archive_v2_guard() -> None:
    """Install once during archive consistency bootstrap; keep canonical writer ownership."""
    from app.modules.graduation.services import graduation_archive_batch_scale as scale

    current_snapshot = scale.build_snapshot
    if not getattr(current_snapshot, "_gd_archive_v2_enriched", False):
        def wrapped_snapshot(db, batch, mode: str, *, lock: bool = False):
            return enrich_snapshot(db, batch, current_snapshot(db, batch, mode, lock=lock), lock=lock)

        wrapped_snapshot._gd_archive_v2_enriched = True
        wrapped_snapshot._gd_archive_v2_original = current_snapshot
        scale.build_snapshot = wrapped_snapshot

    from app.modules.graduation.materials import manifest_service as manifests

    current_collect = manifests._collect_items
    if not getattr(current_collect, "_gd_archive_v2_freeze_guard", False):
        manifests._collect_items = _guarded_collect_factory(current_collect)

    current_file_archive = manifests.file_archive
    if not getattr(current_file_archive, "_gd_archive_v2_context_guard", False):
        def guarded_file_archive(gd_student_id: int, archive_batch_no, user: dict, *, _expected: dict | None = None):
            token = _FREEZE_EXPECTED.set(_expected)
            try:
                return current_file_archive(gd_student_id, archive_batch_no, user)
            finally:
                _FREEZE_EXPECTED.reset(token)

        guarded_file_archive._gd_archive_v2_context_guard = True
        guarded_file_archive._gd_archive_v2_original = current_file_archive
        manifests.file_archive = guarded_file_archive
    else:
        guarded_file_archive = current_file_archive

    current_batch_file = manifests.batch_file
    if getattr(current_batch_file, "_gd_archive_v2_batch_guard", False):
        return

    def guarded_batch_file(archive_batch_no, batch_id: int, preview_token: str, user: dict) -> dict:
        if not str(preview_token or "").strip():
            raise AppException("VALIDATION_ERROR", "执行前必须先完成归档预览")
        from app.modules.graduation.services.graduation_archive_consistency import verify_batch_file_preview
        from app.modules.graduation.services.graduation_archive_batch_scale import row_block_reasons
        from app.modules.graduation.materials import snapshot_service

        requested = manifests._archive_no(archive_batch_no)
        initial = verify_batch_file_preview(int(batch_id), str(preview_token))
        prep_errors: dict[int, AppException] = {}
        for row in initial.get("rows") or []:
            sid = int(row["studentId"])
            if row_block_reasons(row, "FILE"):
                continue
            try:
                snapshot_service.prepare_all(sid, user)
            except AppException as exc:
                prep_errors[sid] = exc

        # The exact token is checked again after structured FileVersions are prepared.
        # System-generated versions are intentionally excluded from the signed preserved hash,
        # while the business-source truth and readiness remain part of the signed snapshot.
        verified = verify_batch_file_preview(int(batch_id), str(preview_token))
        executable_ids = [
            int(row["studentId"]) for row in (verified.get("rows") or [])
            if not row_block_reasons(row, "FILE") and int(row["studentId"]) not in prep_errors
        ]
        with session() as db:
            post_prepare = _freeze_state(db, int(batch_id), executable_ids, lock=False)

        filed = skipped = failed = 0
        manifests_ids: list[str] = []
        errors: list[dict] = []
        for row in verified.get("rows") or []:
            sid = int(row["studentId"])
            if row_block_reasons(row, "FILE"):
                skipped += 1
                continue
            prep_error = prep_errors.get(sid)
            if prep_error:
                failed += 1
                errors.append({"gdStudentId": str(sid), "code": prep_error.code, "message": prep_error.message})
                continue
            expected = {
                "ruleHash": row.get("v2RuleHash"),
                "preservedHash": row.get("v2PreservedHash"),
                "fullHash": post_prepare["full"].get(sid, _hash([])),
            }
            try:
                result = manifests.file_archive(sid, requested, user, _expected=expected)
                manifests_ids.append(result["manifestId"])
                filed += 1
            except AppException as exc:
                failed += 1
                errors.append({"gdStudentId": str(sid), "code": exc.code, "message": exc.message})
        return {
            "batchId": str(batch_id), "batchName": verified.get("batchName") or "",
            "archiveBatchNo": requested, "filed": filed, "skipped": skipped, "failed": failed,
            "manifestIds": manifests_ids, "errors": errors,
        }

    guarded_batch_file._gd_archive_v2_batch_guard = True
    guarded_batch_file._gd_archive_v2_original = current_batch_file
    manifests.batch_file = guarded_batch_file


__all__ = ["enrich_snapshot", "install_archive_v2_guard"]
