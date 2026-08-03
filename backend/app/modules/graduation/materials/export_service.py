"""Streaming graduation archive ZIP/XLSX export orchestration.

This service never creates or revises manifests.  It packages immutable V2
manifest evidence and verifies every referenced byte before publishing a job.
"""
from __future__ import annotations

import hashlib
import json
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from sqlalchemy import and_, func, select

from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.models import GraduationBatch, GraduationStudent
from app.models.data_exchange import ExportJob
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileObject
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _iso, _tid, session
from app.services.file_content_security import sanitize_filename
from app.services.file_scan_constants import SCAN_NOT_REQUIRED
from app.services.message_identity import resolve_message_user_id
from app.services.storage import get_backend

from .definitions import MANIFEST_ARCHIVE_TYPE, MANIFEST_TARGET_TYPE, MODULE_CODE
from .query_service import student_scope_predicate
from .rule_service import active_rule, rule_items


EXPORT_TTL_HOURS = 24


def _actor_id(user: dict | None) -> int | None:
    return resolve_message_user_id(user or {}) or None


def _actor_name(user: dict | None) -> str:
    actor = user or {}
    return str(actor.get("realName") or actor.get("name") or actor.get("loginName") or "系统")[:100]


def _safe_excel(value: Any) -> Any:
    return "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value


def _sha256_path(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def _persist_path(db, source: Path, filename: str, *, biz_type: str, biz_id: str, user: dict) -> FileObject:
    safe_name = sanitize_filename(filename)
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else "bin"
    key = f"exports/{_tid()}/{datetime.utcnow():%Y%m%d}/{uuid.uuid4().hex}.{ext}"
    backend = get_backend()
    staged = backend.staging_path(key)
    staged.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != staged.resolve():
        with source.open("rb") as src, staged.open("wb") as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                dst.write(chunk)
    sha256, size = _sha256_path(staged)
    backend.persist(key, staged)
    mime = {
        "zip": "application/zip",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(ext, "application/octet-stream")
    now = datetime.utcnow()
    row = FileObject(
        tenant_id=_tid(), file_key=key, file_name=safe_name, ext=ext, mime_type=mime,
        size_bytes=size, sha256=sha256, biz_type=biz_type, biz_id=str(biz_id),
        owner_user_id=_actor_id(user), visibility="BIZ_SCOPED", security_level="HIGHLY_SENSITIVE",
        status="AVAILABLE", storage_backend=str(settings.FILE_STORAGE_BACKEND or "local").lower(),
        storage_zone="EXPORT", upload_source="SYSTEM", scan_required=False,
        scan_status=SCAN_NOT_REQUIRED, scan_attempts=0, scanned_at=now, available_at=now,
        created_by=_actor_id(user),
    )
    db.add(row)
    db.flush()
    return row


def _scope_students(db, scope_type: str, scope_value: str, batch_id: int, user: dict) -> list[GraduationStudent]:
    kind = str(scope_type or "BATCH").upper()
    stmt = select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(batch_id),
        GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
        student_scope_predicate(user),
    )
    if kind == "STUDENT":
        if not str(scope_value or "").isdigit():
            raise not_found("归档范围不存在")
        stmt = stmt.where(GraduationStudent.id == int(scope_value))
    elif kind == "CLASS":
        stmt = stmt.where(GraduationStudent.class_id == str(scope_value))
    elif kind == "MAJOR":
        stmt = stmt.where(GraduationStudent.major_id == str(scope_value))
    elif kind == "COLLEGE":
        stmt = stmt.where(GraduationStudent.college_id == str(scope_value))
    elif kind != "BATCH":
        raise AppException("VALIDATION_ERROR", "归档范围类型不支持")
    rows = list(db.scalars(stmt.order_by(
        GraduationStudent.college_id, GraduationStudent.class_id,
        GraduationStudent.student_no, GraduationStudent.id,
    )).all())
    if not rows:
        raise not_found("归档范围不存在")
    return rows


def _job_view(row: ExportJob) -> dict:
    return {
        "id": str(row.id), "status": row.status, "progress": int(row.progress or 0),
        "rowCount": int(row.row_count or 0), "fileObjectId": str(row.file_object_id or ""),
        "expiresAt": _iso(row.expires_at), "revokedAt": _iso(row.revoked_at),
        "revokeReason": row.revoke_reason or "", "result": row.result_json or {},
        "errorMessage": row.error_message or "", "version": int(row.version or 0),
        "createdAt": _iso(row.created_at), "updatedAt": _iso(row.updated_at),
    }


def _job(db, job_id: int, user: dict, *, lock: bool = False) -> ExportJob:
    stmt = select(ExportJob).where(
        ExportJob.tenant_id == _tid(), ExportJob.id == int(job_id),
        ExportJob.module_code == MODULE_CODE, ExportJob.adapter_type == "GRADUATION_ARCHIVE",
        ExportJob.is_deleted.is_(False),
    )
    if _actor_id(user):
        stmt = stmt.where(ExportJob.operator_id == _actor_id(user))
    if lock:
        stmt = stmt.with_for_update()
    row = db.scalars(stmt).first()
    if not row:
        raise not_found("毕业设计归档任务不存在")
    return row


def create_export_job(*, batch_id: int, scope_type: str, scope_value: str, user: dict) -> dict:
    with session() as db:
        students = _scope_students(db, scope_type, scope_value, int(batch_id), user)
        row = ExportJob(
            tenant_id=_tid(), module_code=MODULE_CODE, export_type="GRADUATION_ARCHIVE_ZIP_XLSX",
            purpose=f"毕业设计{str(scope_type).upper()}归档包与档案清单",
            adapter_type="GRADUATION_ARCHIVE", adapter_ref=uuid.uuid4().hex,
            filter_snapshot_json={"batchId": str(batch_id), "scopeType": str(scope_type).upper(),
                                  "scopeValue": str(scope_value or "")},
            data_scope_snapshot_json={"actor": _actor_name(user), "studentCount": len(students)},
            status="CREATED", progress=0, row_count=0,
            expires_at=datetime.utcnow() + timedelta(hours=EXPORT_TTL_HOURS),
            operator_id=_actor_id(user), created_by=_actor_id(user), result_json={"retryable": True},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {**_job_view(row), "studentCount": len(students)}


def create_student_export_job(gd_student_id: int, user: dict) -> dict:
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(gd_student_id),
            GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
        )).first()
        if not student:
            raise not_found("毕业设计学生不存在")
        assert_student_access(db, student, "archive.export")
        batch_id = int(student.batch_id or 0)
    return create_export_job(batch_id=batch_id, scope_type="STUDENT", scope_value=str(gd_student_id), user=user)


def _latest_manifests(db, students: list[GraduationStudent]) -> list[tuple[GraduationStudent, ArchiveManifest]]:
    target_ids = {str(student.id) for student in students}
    latest = select(
        ArchiveManifest.target_id.label("target_id"), func.max(ArchiveManifest.revision).label("revision"),
    ).where(
        ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
        ArchiveManifest.archive_type == MANIFEST_ARCHIVE_TYPE,
        ArchiveManifest.target_type == MANIFEST_TARGET_TYPE,
        ArchiveManifest.target_id.in_(target_ids), ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
        ArchiveManifest.is_deleted.is_(False),
    ).group_by(ArchiveManifest.target_id).subquery()
    manifests = list(db.scalars(select(ArchiveManifest).join(
        latest, and_(ArchiveManifest.target_id == latest.c.target_id,
                     ArchiveManifest.revision == latest.c.revision),
    ).where(ArchiveManifest.tenant_id == _tid())).all())
    by_student = {str(row.target_id): row for row in manifests}
    missing = [student.student_no or student.name for student in students if str(student.id) not in by_student]
    if missing:
        raise AppException("DATA_CONFLICT", "以下学生尚未生成有效 Manifest：" + "、".join(missing[:20]))
    return [(student, by_student[str(student.id)]) for student in students]


def _write_xlsx(path: Path, rows: list[dict]) -> None:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("毕业设计档案清单")
    fields = ["batch", "college", "major", "class", "studentNo", "studentName", "advisor", "topic",
              "materialCode", "materialName", "fileName", "fileVersion", "fileSize", "sha256",
              "scanStatus", "reviewStatus", "submittedAt", "revision"]
    sheet.append(["批次", "学院", "专业", "班级", "学号", "姓名", "指导教师", "题目",
                  "材料代码", "材料名称", "文件名", "文件版本", "文件大小", "SHA-256",
                  "扫描状态", "审核状态", "上传时间", "归档 revision"])
    for row in rows:
        sheet.append([_safe_excel(row.get(field, "")) for field in fields])
    workbook.save(path)


def run_export_job(job_id: int, user: dict) -> dict:
    with session() as db:
        row = _job(db, job_id, user, lock=True)
        if row.status == "SUCCEEDED":
            return _job_view(row)
        if row.status not in {"CREATED", "FAILED"} or row.revoked_at:
            raise AppException("DATA_CONFLICT", "归档任务当前不可执行")
        snapshot = dict(row.filter_snapshot_json or {})
        row.status = "PROCESSING"
        row.progress = 5
        row.error_message = None
        row.version = int(row.version or 0) + 1
        db.commit()
    try:
        with session() as db:
            students = _scope_students(db, snapshot.get("scopeType"), snapshot.get("scopeValue"),
                                       int(snapshot.get("batchId")), user)
            pairs = _latest_manifests(db, students)
            manifest_ids = {int(manifest.id) for _, manifest in pairs}
            items = list(db.scalars(select(ArchiveManifestItem).where(
                ArchiveManifestItem.tenant_id == _tid(),
                ArchiveManifestItem.manifest_id.in_(manifest_ids),
                ArchiveManifestItem.is_deleted.is_(False),
            ).order_by(ArchiveManifestItem.manifest_id, ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all())
            files = {int(row.id): row for row in db.scalars(select(FileObject).where(
                FileObject.tenant_id == _tid(),
                FileObject.id.in_({int(item.file_object_id) for item in items} or {-1}),
                FileObject.status == "AVAILABLE", FileObject.is_deleted.is_(False),
            )).all()}
            rule = active_rule(db, int(snapshot.get("batchId")))
            names = {item.material_code: item.material_name for item in rule_items(db, int(rule.id))}
            manifests = {int(manifest.id): (student, manifest) for student, manifest in pairs}
            batch = db.get(GraduationBatch, int(snapshot.get("batchId")))
            backend = get_backend()
            xlsx_path = backend.staging_path(f"exports/{_tid()}/{uuid.uuid4().hex}.xlsx")
            zip_path = backend.staging_path(f"exports/{_tid()}/{uuid.uuid4().hex}.zip")
            xlsx_path.parent.mkdir(parents=True, exist_ok=True)
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            index_rows: list[dict] = []
            package_items: list[dict] = []
            used_paths: set[str] = set()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                for item in items:
                    student, manifest = manifests[int(item.manifest_id)]
                    file_obj = files.get(int(item.file_object_id))
                    if not file_obj:
                        raise AppException("DATA_CONFLICT", "Manifest 引用文件不存在或已失效")
                    source = backend.fetch_local(file_obj.file_key)
                    if not source or not source.exists():
                        raise AppException("DATA_CONFLICT", "Manifest 引用文件字节不存在")
                    actual_sha, actual_size = _sha256_path(source)
                    if actual_sha != item.sha256_snapshot or actual_size != int(item.size_snapshot or 0):
                        raise AppException("DATA_CONFLICT", "Manifest 文件哈希或大小已变化")
                    student_dir = sanitize_filename(f"{student.student_no or student.id}_{student.name}")
                    base = sanitize_filename(item.file_name_snapshot)
                    archive_path = f"students/{student_dir}/materials/{int(item.sort_no):03d}_{item.material_code}_{base}"
                    suffix = 2
                    original = archive_path
                    while archive_path in used_paths:
                        stem, dot, ext = original.rpartition(".")
                        archive_path = f"{stem}_{suffix}.{ext}" if dot else f"{original}_{suffix}"
                        suffix += 1
                    if archive_path.startswith(("/", "\\")) or ".." in Path(archive_path).parts:
                        raise AppException("DATA_CONFLICT", "归档文件路径不安全")
                    used_paths.add(archive_path)
                    archive.write(source, archive_path)
                    row_data = {
                        "batch": batch.batch_name if batch else snapshot.get("batchId"),
                        "college": student.college_id or "", "major": student.major_id or "",
                        "class": student.class_name or student.class_id or "", "studentNo": student.student_no or "",
                        "studentName": student.name, "advisor": student.advisor_name or "", "topic": student.topic_title or "",
                        "materialCode": item.material_code, "materialName": names.get(item.material_code, item.material_code),
                        "fileName": item.file_name_snapshot, "fileVersion": str(item.version_id),
                        "fileSize": int(item.size_snapshot or 0), "sha256": item.sha256_snapshot,
                        "scanStatus": item.scan_result, "reviewStatus": item.review_status or "",
                        "submittedAt": _iso(item.submitted_at_snapshot), "revision": int(manifest.revision),
                    }
                    index_rows.append(row_data)
                    package_items.append({
                        "gdStudentId": str(student.id), "studentNo": student.student_no or "",
                        "manifestId": str(manifest.id), "revision": int(manifest.revision),
                        "materialCode": item.material_code, "fileVersionId": str(item.version_id),
                        "fileObjectId": str(item.file_object_id), "archivePath": archive_path,
                        "sizeBytes": int(item.size_snapshot or 0), "sha256": item.sha256_snapshot,
                    })
                _write_xlsx(xlsx_path, index_rows)
                archive.write(xlsx_path, "档案清单.xlsx")
                archive.writestr("manifest.json", json.dumps({
                    "schemaVersion": "GRADUATION_EXPORT_PACKAGE_V2", "tenantId": str(_tid()),
                    "batchId": str(snapshot.get("batchId")), "scopeType": snapshot.get("scopeType"),
                    "scopeValue": snapshot.get("scopeValue"), "generatedAt": datetime.utcnow().isoformat() + "Z",
                    "generatedBy": _actor_name(user), "studentCount": len(students),
                    "manifestCount": len(pairs), "materialFileCount": len(package_items), "items": package_items,
                }, ensure_ascii=False, indent=2, sort_keys=True))
            with zipfile.ZipFile(zip_path, "r") as check:
                if len([name for name in check.namelist() if "/materials/" in name]) != len(package_items):
                    raise AppException("DATA_CONFLICT", "ZIP 文件数与 manifest.json 不一致")
            xlsx_file = _persist_path(db, xlsx_path, f"毕业设计档案清单_{datetime.now():%Y%m%d_%H%M}.xlsx",
                                      biz_type="GRADUATION_ARCHIVE_INDEX", biz_id=str(job_id), user=user)
            zip_file = _persist_path(db, zip_path, f"毕业设计归档包_{datetime.now():%Y%m%d_%H%M}.zip",
                                     biz_type="GRADUATION_ARCHIVE_PACKAGE", biz_id=str(job_id), user=user)
            row = _job(db, job_id, user, lock=True)
            row.status = "SUCCEEDED"
            row.progress = 100
            row.row_count = len(index_rows)
            row.file_object_id = int(zip_file.id)
            row.finished_at = datetime.utcnow()
            row.result_json = {
                "zipFileObjectId": str(zip_file.id), "zipFileName": zip_file.file_name,
                "zipSha256": zip_file.sha256, "zipSizeBytes": int(zip_file.size_bytes or 0),
                "xlsxFileObjectId": str(xlsx_file.id), "xlsxFileName": xlsx_file.file_name,
                "xlsxSha256": xlsx_file.sha256, "studentCount": len(students),
                "manifestIds": [str(manifest.id) for _, manifest in pairs],
                "materialFileCount": len(package_items), "retryable": False,
            }
            row.version = int(row.version or 0) + 1
            from .manifest_service import mark_packaged_in_session

            mark_packaged_in_session(db, [int(manifest.id) for _, manifest in pairs], int(zip_file.id))
            db.commit()
            return _job_view(row)
    except Exception as exc:
        with session() as db:
            row = _job(db, job_id, user, lock=True)
            row.status = "FAILED"
            row.error_message = str(exc)[:4000]
            row.progress = 0
            row.result_json = {**(row.result_json or {}), "retryable": True}
            row.version = int(row.version or 0) + 1
            db.commit()
        raise


__all__ = ["create_export_job", "create_student_export_job", "run_export_job"]
