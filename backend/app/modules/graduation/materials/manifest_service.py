"""Sole V2 graduation archive manifest writer."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.models import GraduationArchiveRecord, GraduationRiskCase, GraduationStudent
from app.models.data_exchange import ExportJob
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileObject, FileVersion
from app.models.graduation_material import GraduationStudentMaterial
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _iso, _tid, session
from app.services.file_access_service import require_file_access
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED
from app.services.message_identity import resolve_message_user_id

from .definitions import (
    MANIFEST_ARCHIVE_TYPE,
    MANIFEST_SCHEMA_VERSION,
    MANIFEST_TARGET_TYPE,
    MODULE_CODE,
)
from .rule_service import active_rule, rule_items


ACTIVE_STATUSES = ("FROZEN", "PACKAGED")


def _actor_id(user: dict | None) -> int | None:
    return resolve_message_user_id(user or {}) or None


def _actor_name(user: dict | None) -> str:
    actor = user or {}
    return str(actor.get("realName") or actor.get("name") or actor.get("loginName") or "系统")[:100]


def _archive_no(value: str | None) -> str:
    normalized = str(value or f"GDARCH-{datetime.utcnow():%Y%m%d}").strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,99}", normalized):
        raise AppException("VALIDATION_ERROR", "archiveBatchNo 格式不正确")
    return normalized


def _manifest_view(db, manifest: ArchiveManifest) -> dict:
    items = list(db.scalars(select(ArchiveManifestItem).where(
        ArchiveManifestItem.tenant_id == _tid(),
        ArchiveManifestItem.manifest_id == int(manifest.id),
        ArchiveManifestItem.is_deleted.is_(False),
    ).order_by(ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all())
    return {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "manifestId": str(manifest.id), "revision": int(manifest.revision or 1),
        "status": manifest.status, "ruleVersion": manifest.rule_version or "",
        "manifestSha256": manifest.manifest_sha256 or "",
        "packageFileId": str(manifest.package_file_id or ""),
        "frozenAt": _iso(manifest.frozen_at), "revokedAt": _iso(manifest.revoked_at),
        "revokeReason": manifest.revoke_reason or "", "itemCount": len(items),
        "items": [{
            "materialCode": item.material_code, "assetId": str(item.asset_id),
            "fileVersionId": str(item.version_id), "versionId": str(item.version_id),
            "fileObjectId": str(item.file_object_id), "fileName": item.file_name_snapshot,
            "sizeBytes": item.size_snapshot, "sha256": item.sha256_snapshot,
            "scanResult": item.scan_result, "reviewStatus": item.review_status,
            "uploader": item.uploader_snapshot or "", "submittedAt": _iso(item.submitted_at_snapshot),
            "sortNo": int(item.sort_no or 0),
        } for item in items],
    }


def _student_for_update(db, gd_student_id: int) -> GraduationStudent:
    row = db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(gd_student_id),
        GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
    ).with_for_update()).first()
    if not row:
        raise not_found("毕业设计学生不存在")
    return row


def _assert_no_open_risk(db, student: GraduationStudent) -> None:
    count = int(db.scalar(select(func.count()).select_from(GraduationRiskCase).where(
        GraduationRiskCase.tenant_id == _tid(),
        GraduationRiskCase.gd_student_id == int(student.id),
        GraduationRiskCase.status.in_(("OPEN", "PROCESSING")),
        GraduationRiskCase.is_deleted.is_(False),
    )) or 0)
    if count:
        raise AppException("DATA_CONFLICT", f"该生仍有 {count} 条未关闭风险，不能归档")


def _active_manifest(db, gd_student_id: int, *, lock: bool = False) -> ArchiveManifest | None:
    stmt = select(ArchiveManifest).where(
        ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
        ArchiveManifest.archive_type == MANIFEST_ARCHIVE_TYPE,
        ArchiveManifest.target_type == MANIFEST_TARGET_TYPE,
        ArchiveManifest.target_id == str(gd_student_id),
        ArchiveManifest.status.in_(ACTIVE_STATUSES), ArchiveManifest.is_deleted.is_(False),
    ).order_by(ArchiveManifest.revision.desc(), ArchiveManifest.id.desc())
    if lock:
        stmt = stmt.with_for_update()
    rows = list(db.scalars(stmt).all())
    if len(rows) > 1:
        raise AppException("MANIFEST_CONFLICT", "同一学生存在多个有效 V2 Manifest")
    return rows[0] if rows else None


def _collect_items(db, student: GraduationStudent, user: dict) -> tuple[object, list[tuple]]:
    rule = active_rule(db, int(student.batch_id), lock=True)
    definitions = rule_items(db, int(rule.id), lock=True)
    materials = {row.material_code: row for row in db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(student.batch_id),
        GraduationStudentMaterial.gd_student_id == int(student.id),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).all()}
    selected: list[tuple] = []
    problems: list[str] = []
    for item in definitions:
        if not item.archive_required:
            continue
        material = materials.get(item.material_code)
        if not material or not material.current_version_id:
            if item.required:
                problems.append(f"{item.material_name}（缺失）")
            continue
        version = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.id == int(material.current_version_id),
            FileVersion.asset_id == int(material.asset_id or 0), FileVersion.is_current.is_(True),
            FileVersion.is_deleted.is_(False),
        ).with_for_update()).first()
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(),
            FileObject.id == int(version.file_object_id if version else 0),
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not version or not file_obj:
            problems.append(f"{item.material_name}（当前版本或文件不存在）")
            continue
        if version.status != "APPROVED" or material.review_status not in {"APPROVED", "NOT_REQUIRED"}:
            problems.append(f"{item.material_name}（未审核通过）")
            continue
        scan = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
        if not is_downloadable_status(file_obj.status) or scan not in READY_SCAN_STATES:
            problems.append(f"{item.material_name}（安全状态异常）")
            continue
        # Public resolver owns file authorization. Graduation scope is checked
        # separately above and again by its FileBinding resolver.
        require_file_access(str(file_obj.id), user=user, action="archive")
        if not file_obj.sha256 or len(str(file_obj.sha256)) != 64:
            problems.append(f"{item.material_name}（缺少可信 SHA-256）")
            continue
        selected.append((item, material, version, file_obj))
    if problems:
        raise AppException("DATA_CONFLICT", "归档材料未齐全或存在异常：" + "、".join(sorted(set(problems))))
    if not selected:
        raise AppException("DATA_CONFLICT", "没有可冻结的毕业设计材料版本")
    return rule, selected


def _payload(student: GraduationStudent, archive_no: str, revision: int, rule, selected: list[tuple], user: dict) -> dict:
    return {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "tenantId": str(_tid()), "batchId": str(student.batch_id),
        "gdStudentId": str(student.id), "studentId": str(student.student_id or ""),
        "studentNo": student.student_no or "", "studentName": student.name,
        "topicId": str(student.topic_id or ""), "topicTitle": student.topic_title or "",
        "advisorName": student.advisor_name or "", "archiveBatchNo": archive_no,
        "revision": int(revision), "ruleCode": rule.rule_code,
        "ruleVersion": int(rule.rule_version), "generatedBy": _actor_name(user),
        "items": [{
            "materialCode": material.material_code, "assetId": int(material.asset_id),
            "fileVersionId": int(version.id), "fileObjectId": int(file_obj.id),
            "fileNameSnapshot": file_obj.file_name, "sizeSnapshot": int(file_obj.size_bytes or 0),
            "sha256Snapshot": file_obj.sha256,
            "scanResult": str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper(),
            "reviewStatus": material.review_status,
            "uploaderSnapshot": version.uploader_name_snapshot or "",
            "submittedAt": _iso(version.submitted_at),
        } for _, material, version, file_obj in selected],
    }


def file_archive(gd_student_id: int, archive_batch_no: str | None, user: dict) -> dict:
    """Atomically file one student and freeze exactly one new V2 manifest."""
    requested = _archive_no(archive_batch_no)
    # Preserve retry purity: do not generate snapshots when the same archive
    # request has already frozen its V2 evidence.
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(gd_student_id),
            GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
        )).first()
        if not student:
            raise not_found("毕业设计学生不存在")
        assert_student_access(db, student, "archive.file")
        existing = _active_manifest(db, int(student.id))
        if existing:
            archive = db.scalars(select(GraduationArchiveRecord).where(
                GraduationArchiveRecord.tenant_id == _tid(),
                GraduationArchiveRecord.gd_student_id == int(student.id),
                GraduationArchiveRecord.is_deleted.is_(False),
            )).first()
            if archive and archive.archive_batch_no and str(archive.archive_batch_no) != requested:
                raise AppException("IDEMPOTENCY_CONFLICT", "该归档请求已使用其他备案批次号完成")
            return _manifest_view(db, existing)
    # Structured evidence generation is deliberately outside the final filing
    # transaction. Its own source hash makes this phase idempotent.
    from .snapshot_service import prepare_all

    prepare_all(int(gd_student_id), user)
    with session() as db:
        student = _student_for_update(db, int(gd_student_id))
        assert_student_access(db, student, "archive.file")
        archive = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == _tid(),
            GraduationArchiveRecord.gd_student_id == int(student.id),
            GraduationArchiveRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if not archive:
            raise not_found("毕业设计归档记录不存在")
        active = _active_manifest(db, int(student.id), lock=True)
        if active:
            if archive.archive_batch_no and str(archive.archive_batch_no) != requested:
                raise AppException("IDEMPOTENCY_CONFLICT", "该归档请求已使用其他备案批次号完成")
            # The same request is a pure idempotent read of the frozen evidence.
            return _manifest_view(db, active)
        latest = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.archive_type == MANIFEST_ARCHIVE_TYPE,
            ArchiveManifest.target_type == MANIFEST_TARGET_TYPE,
            ArchiveManifest.target_id == str(student.id), ArchiveManifest.is_deleted.is_(False),
        ).order_by(ArchiveManifest.revision.desc(), ArchiveManifest.id.desc()).with_for_update()).first()
        if latest and latest.status != "REVOKED":
            raise AppException("DATA_CONFLICT", "重新归档前必须先撤销上一版 V2 Manifest")
        if archive.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "仅已提交归档记录可执行备案")
        _assert_no_open_risk(db, student)
        rule, selected = _collect_items(db, student, user)
        revision = int(latest.revision if latest else 0) + 1
        payload = _payload(student, requested, revision, rule, selected, user)
        digest = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        manifest = ArchiveManifest(
            tenant_id=_tid(), module_code=MODULE_CODE, archive_type=MANIFEST_ARCHIVE_TYPE,
            target_type=MANIFEST_TARGET_TYPE, target_id=str(student.id), revision=revision,
            status="FROZEN", rule_version=f"{rule.rule_code}:v{rule.rule_version}",
            manifest_sha256=digest, created_by_name=_actor_name(user), frozen_at=datetime.utcnow(),
            created_by=_actor_id(user),
        )
        db.add(manifest)
        db.flush()
        checklist = []
        selected_by_code = {material.material_code for _, material, _, _ in selected}
        for sort_no, (item, material, version, file_obj) in enumerate(selected, start=1):
            db.add(ArchiveManifestItem(
                tenant_id=_tid(), manifest_id=int(manifest.id), material_code=material.material_code,
                asset_id=int(material.asset_id), version_id=int(version.id), file_object_id=int(file_obj.id),
                file_name_snapshot=file_obj.file_name, size_snapshot=int(file_obj.size_bytes or 0),
                sha256_snapshot=file_obj.sha256, review_status=material.review_status,
                scan_result=str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper(),
                uploader_snapshot=version.uploader_name_snapshot,
                submitted_at_snapshot=version.submitted_at, sort_no=sort_no, created_by=_actor_id(user),
            ))
            material.archive_status = "FROZEN"
            material.archived_revision = revision
            material.version = int(material.version or 0) + 1
            version.status = "ARCHIVED"
        for item in rule_items(db, int(rule.id)):
            if item.archive_required:
                checklist.append({
                    "item": item.material_code, "label": item.material_name,
                    "required": bool(item.required), "present": item.material_code in selected_by_code,
                })
        archive.checklist_json = checklist
        archive.missing_items = []
        archive.status = "FILED"
        archive.verified_by = _actor_name(user)
        archive.filed_at = datetime.utcnow()
        archive.archive_batch_no = requested
        archive.manifest_hash = digest
        archive.reject_reason = None
        archive.version = int(archive.version or 0) + 1
        student.stage = "ARCHIVED"
        student.version = int(student.version or 0) + 1
        db.flush()
        result = _manifest_view(db, manifest)
        db.commit()
        return result


def batch_file(archive_batch_no: str | None, batch_id: int, preview_token: str, user: dict) -> dict:
    """File students independently so one rejected student cannot hide successful rows."""
    if not str(preview_token or "").strip():
        raise AppException("VALIDATION_ERROR", "执行前必须先完成归档预览")
    from app.modules.graduation.services.graduation_archive_consistency import verify_batch_file_preview

    snapshot = verify_batch_file_preview(int(batch_id), str(preview_token))
    requested = _archive_no(archive_batch_no)
    filed = skipped = failed = 0
    manifests: list[str] = []
    errors: list[dict] = []
    for row in snapshot["rows"]:
        gd_student_id = int(row["studentId"])
        if row.get("missing") or int(row.get("openRisks") or 0) > 0:
            skipped += 1
            continue
        try:
            result = file_archive(gd_student_id, requested, user)
            manifests.append(result["manifestId"])
            filed += 1
        except AppException as exc:
            failed += 1
            errors.append({"gdStudentId": str(gd_student_id), "code": exc.code, "message": exc.message})
    return {
        "batchId": str(batch_id), "batchName": snapshot.get("batchName") or "",
        "archiveBatchNo": requested, "filed": filed, "skipped": skipped, "failed": failed,
        "manifestIds": manifests, "errors": errors,
    }


def revoke_manifest(gd_student_id: int, reason: str, user: dict) -> dict:
    """Reopen the business record without mutating frozen evidence versions or files."""
    normalized = str(reason or "").strip()
    if len(normalized) < 5:
        raise AppException("VALIDATION_ERROR", "撤销原因必填且不少于 5 个字")
    with session() as db:
        student = _student_for_update(db, int(gd_student_id))
        assert_student_access(db, student, "archive.revoke")
        manifest = _active_manifest(db, int(student.id), lock=True)
        if not manifest:
            raise not_found("有效 V2 Manifest 不存在")
        manifest.status = "REVOKED"
        manifest.revoked_at = datetime.utcnow()
        manifest.revoked_by = _actor_name(user)
        manifest.revoke_reason = normalized[:500]
        materials = list(db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(student.id),
            GraduationStudentMaterial.archived_revision == int(manifest.revision),
            GraduationStudentMaterial.is_deleted.is_(False),
        ).with_for_update()).all())
        for material in materials:
            material.archive_status = (
                "ELIGIBLE" if material.review_status in {"APPROVED", "NOT_REQUIRED"} else "NOT_ARCHIVED"
            )
            material.version = int(material.version or 0) + 1
        archive = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == _tid(),
            GraduationArchiveRecord.gd_student_id == int(student.id),
            GraduationArchiveRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if archive:
            archive.status = "SUBMITTED"
            archive.reject_reason = normalized[:500]
            archive.version = int(archive.version or 0) + 1
        student.stage = "FINAL_CHECK"
        student.version = int(student.version or 0) + 1
        jobs = list(db.scalars(select(ExportJob).where(
            ExportJob.tenant_id == _tid(), ExportJob.module_code == MODULE_CODE,
            ExportJob.adapter_type == "GRADUATION_ARCHIVE", ExportJob.status == "SUCCEEDED",
            ExportJob.is_deleted.is_(False),
        ).with_for_update()).all())
        revoked_jobs: list[str] = []
        for job in jobs:
            if str(manifest.id) not in {str(value) for value in (job.result_json or {}).get("manifestIds", [])}:
                continue
            job.status = "REVOKED"
            job.revoked_at = datetime.utcnow()
            job.revoke_reason = normalized[:500]
            job.version = int(job.version or 0) + 1
            revoked_jobs.append(str(job.id))
        db.commit()
        return {
            "manifestId": str(manifest.id), "revision": int(manifest.revision),
            "status": manifest.status, "revokedJobs": revoked_jobs, "reason": normalized,
        }


def mark_packaged_in_session(db, manifest_ids: list[int], package_file_id: int) -> None:
    """Finalize package metadata without revising immutable manifest items."""
    manifests = list(db.scalars(select(ArchiveManifest).where(
        ArchiveManifest.tenant_id == _tid(), ArchiveManifest.id.in_(set(manifest_ids) or {-1}),
        ArchiveManifest.module_code == MODULE_CODE,
        ArchiveManifest.archive_type == MANIFEST_ARCHIVE_TYPE,
        ArchiveManifest.target_type == MANIFEST_TARGET_TYPE,
        ArchiveManifest.status.in_(ACTIVE_STATUSES), ArchiveManifest.is_deleted.is_(False),
    ).with_for_update()).all())
    if len(manifests) != len(set(manifest_ids)):
        raise AppException("DATA_CONFLICT", "归档包引用的 V2 Manifest 已变化")
    for manifest in manifests:
        manifest.status = "PACKAGED"
        manifest.package_file_id = int(package_file_id)
        materials = list(db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(manifest.target_id),
            GraduationStudentMaterial.archived_revision == int(manifest.revision),
            GraduationStudentMaterial.is_deleted.is_(False),
        ).with_for_update()).all())
        for material in materials:
            material.archive_status = "ARCHIVED"
            material.version = int(material.version or 0) + 1


__all__ = ["batch_file", "file_archive", "mark_packaged_in_session", "revoke_manifest"]
