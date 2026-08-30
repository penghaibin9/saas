"""Graduation-owned projection of the shared PLAT-A package artifact."""
from __future__ import annotations

from sqlalchemy import and_, select

from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.models import GraduationStudent
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileJob, FileObject
from app.models.platform_integrity import IntegrityException
from app.modules.platform_integrity.contracts import frozen_manifest_artifact_ref
from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.modules.platform_integrity.file_job_service import (
    FROZEN_PACKAGE_JOB_TYPE,
    package_job_dedupe_key,
)
from app.modules.platform_integrity.frozen_package_service import (
    PACKAGE_BIZ_TYPE,
    PACKAGEABLE_MANIFEST_STATUSES,
    frozen_package_artifact_biz_id,
    is_package_artifact_ready,
)
from app.modules.platform_integrity.manifest_digest import (
    PLATFORM_BUSINESS_SNAPSHOT,
    PLATFORM_MANIFEST_DIGEST_V1,
)
from app.services.db_service import _tid, session

from .definitions import MANIFEST_ARCHIVE_TYPE, MANIFEST_TARGET_TYPE, MODULE_CODE


def _active_manifest(db, gd_student_id: int) -> ArchiveManifest | None:
    return db.scalars(select(ArchiveManifest).where(
        ArchiveManifest.tenant_id == _tid(),
        ArchiveManifest.module_code == MODULE_CODE,
        ArchiveManifest.archive_type == MANIFEST_ARCHIVE_TYPE,
        ArchiveManifest.target_type == MANIFEST_TARGET_TYPE,
        ArchiveManifest.target_id == str(gd_student_id),
        ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
        ArchiveManifest.is_deleted.is_(False),
    ).order_by(ArchiveManifest.revision.desc(), ArchiveManifest.id.desc()).limit(1)).first()


def _package_job_status(db, manifest: ArchiveManifest) -> str:
    if not manifest.manifest_sha256:
        return "NOT_REQUESTED"
    dedupe_key = package_job_dedupe_key(
        tenant_id=_tid(),
        manifest_id=int(manifest.id),
        revision=int(manifest.revision or 1),
        manifest_sha256=str(manifest.manifest_sha256),
        profile_code="STANDARD_V1",
    )
    job = db.scalars(select(FileJob).where(
        FileJob.tenant_id == _tid(),
        FileJob.job_type == FROZEN_PACKAGE_JOB_TYPE,
        FileJob.dedupe_key == dedupe_key,
        FileJob.is_deleted.is_(False),
    ).order_by(FileJob.id.desc()).limit(1)).first()
    return str(job.status or "PENDING").upper() if job else "NOT_REQUESTED"


def _projection(db, manifest: ArchiveManifest) -> dict:
    snapshot_exists = db.scalar(select(ArchiveManifestItem.id).where(
        ArchiveManifestItem.tenant_id == _tid(),
        ArchiveManifestItem.manifest_id == int(manifest.id),
        ArchiveManifestItem.material_code == PLATFORM_BUSINESS_SNAPSHOT,
        ArchiveManifestItem.is_deleted.is_(False),
    ).limit(1))
    if not snapshot_exists:
        return {
            "manifestId": str(manifest.id),
            "revision": int(manifest.revision or 1),
            "manifestStatus": manifest.status,
            "packageStatus": "LEGACY_UNAVAILABLE",
            "digestSchemaVersion": "LEGACY",
            "artifact": None,
        }
    artifact = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(),
        FileObject.biz_type == PACKAGE_BIZ_TYPE,
        FileObject.biz_id == frozen_package_artifact_biz_id(manifest, "STANDARD_V1"),
        FileObject.is_deleted.is_(False),
    ).order_by(FileObject.id.desc()).limit(1)).first()
    artifact_ready = is_package_artifact_ready(artifact)
    artifact_view = None
    if artifact_ready:
        artifact_view = _artifact_view(manifest, artifact, can_download=True)
    return {
        "manifestId": str(manifest.id),
        "revision": int(manifest.revision or 1),
        "manifestStatus": manifest.status,
        "manifestSha256": manifest.manifest_sha256 or "",
        "packageStatus": "AVAILABLE" if artifact_ready else ("UNAVAILABLE" if artifact else _package_job_status(db, manifest)),
        "digestSchemaVersion": PLATFORM_MANIFEST_DIGEST_V1,
        "artifact": artifact_view,
    }


def _artifact_view(manifest: ArchiveManifest, artifact: FileObject, *, can_download: bool) -> dict:
    value = frozen_manifest_artifact_ref(
        tenant_id=_tid(),
        manifest=manifest,
        file_object=artifact,
        profile_code="STANDARD_V1",
        resolver_code=PACKAGE_BIZ_TYPE,
    ).as_dict()
    value.update({"canPreview": False, "canDownload": bool(can_download)})
    return value


def my_frozen_package(user: dict) -> dict:
    if str((user or {}).get("userType") or "").upper() != "STUDENT":
        raise no_permission("该入口仅学生本人可用")
    with session() as db:
        student = resolve_current_gd_student(db, user or {})
        if not student:
            raise not_found("未找到本人毕业设计档案")
        manifest = _active_manifest(db, int(student.id))
        if not manifest:
            return {
                "studentId": str(student.student_id or ""),
                "gdStudentId": str(student.id),
                "packageStatus": "NOT_FROZEN",
                "artifact": None,
            }
        return {
            "studentId": str(student.student_id or ""),
            "gdStudentId": str(student.id),
            **_projection(db, manifest),
        }


def manifest_frozen_package(manifest_id: int, user: dict) -> dict:
    with session() as db:
        manifest = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(),
            ArchiveManifest.id == int(manifest_id),
            ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.is_deleted.is_(False),
        )).first()
        if not manifest:
            raise not_found("毕业归档清单不存在")
        if str(manifest.status or "").upper() not in PACKAGEABLE_MANIFEST_STATUSES:
            raise AppException("FROZEN_MANIFEST_STATE_INVALID", "当前清单状态不允许访问冻结证据包", http_status=409)
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.id == int(manifest.target_id),
            GraduationStudent.is_deleted.is_(False),
        )).first()
        if not student:
            raise not_found("毕业设计学生不存在")
        if not any(has_permission(user or {}, code) for code in (
            "graduationDesign.archive.view",
            "graduationDesign.archive.file",
            "graduationDesign.archive.export",
        )):
            raise no_permission("缺少毕业归档查看权限")
        assert_student_access(db, student, "frozen.package.view")
        return {"gdStudentId": str(student.id), **_projection(db, manifest)}


def teacher_integrity_summary(user: dict, *, limit: int = 100) -> dict:
    if str((user or {}).get("userType") or "").upper() == "STUDENT":
        raise no_permission("教师入口不对学生开放")
    if not any(has_permission(user or {}, code) for code in (
        "graduationDesign.view",
        "graduationDesign.archive.view",
        "graduationDesign.archive.file",
    )):
        raise no_permission("缺少毕业设计查看权限")
    page_size = max(1, min(int(limit or 100), 100))
    with session() as db:
        rows = list(db.execute(
            select(IntegrityException, ArchiveManifest)
            .join(ArchiveManifest, and_(
                ArchiveManifest.tenant_id == IntegrityException.tenant_id,
                ArchiveManifest.id == IntegrityException.manifest_id,
                ArchiveManifest.is_deleted.is_(False),
            ))
            .where(
                IntegrityException.tenant_id == _tid(),
                IntegrityException.module_code == MODULE_CODE,
                IntegrityException.status.in_(("OPEN", "ACKNOWLEDGED")),
                IntegrityException.is_deleted.is_(False),
            )
            .order_by(IntegrityException.id.desc())
            .limit(page_size)
        ).all())
        visible = []
        exception_student_ids: dict[int, str] = {}
        exception_gd_ids = set()
        for _exception, manifest in rows:
            try:
                exception_gd_ids.add(int(manifest.target_id))
            except (TypeError, ValueError):
                continue
        exception_students = {int(student.id): student for student in db.scalars(
            select(GraduationStudent).where(
                GraduationStudent.tenant_id == _tid(),
                GraduationStudent.id.in_(exception_gd_ids or {-1}),
                GraduationStudent.is_deleted.is_(False),
            ).limit(page_size)
        ).all()}
        for exception, manifest in rows:
            try:
                student_id = int(manifest.target_id)
            except (TypeError, ValueError):
                continue
            student = exception_students.get(student_id)
            if not student:
                continue
            try:
                assert_student_access(db, student, "integrity.summary")
            except Exception:
                continue
            visible.append(exception)
            exception_student_ids[int(exception.id)] = str(student.student_id or "")
        status_counts = {"OPEN": 0, "ACKNOWLEDGED": 0}
        for row in visible:
            status_counts[str(row.status)] = status_counts.get(str(row.status), 0) + 1
        has_snapshot = select(ArchiveManifestItem.id).where(
                ArchiveManifestItem.tenant_id == ArchiveManifest.tenant_id,
                ArchiveManifestItem.manifest_id == ArchiveManifest.id,
                ArchiveManifestItem.material_code == PLATFORM_BUSINESS_SNAPSHOT,
                ArchiveManifestItem.is_deleted.is_(False),
            ).exists()
        package_candidates = list(db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(),
            ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
            ArchiveManifest.is_deleted.is_(False),
            has_snapshot,
        ).order_by(ArchiveManifest.id.desc()).limit(page_size)).all())
        latest_by_target: dict[str, ArchiveManifest] = {}
        for manifest in package_candidates:
            latest_by_target.setdefault(str(manifest.target_id), manifest)
        gd_ids = []
        for value in latest_by_target:
            try:
                gd_ids.append(int(value))
            except (TypeError, ValueError):
                continue
        students = {int(row.id): row for row in db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.id.in_(gd_ids or {-1}),
            GraduationStudent.is_deleted.is_(False),
        ).limit(page_size)).all()}
        scoped_manifests: list[tuple[ArchiveManifest, GraduationStudent]] = []
        for manifest in latest_by_target.values():
            try:
                student = students.get(int(manifest.target_id))
            except (TypeError, ValueError):
                student = None
            if not student:
                continue
            try:
                assert_student_access(db, student, "integrity.package.summary")
            except Exception:
                continue
            scoped_manifests.append((manifest, student))
        artifact_identities = {
            int(manifest.id): frozen_package_artifact_biz_id(manifest, "STANDARD_V1")
            for manifest, _student in scoped_manifests
        }
        artifacts = list(db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(),
            FileObject.biz_type == PACKAGE_BIZ_TYPE,
            FileObject.biz_id.in_(set(artifact_identities.values()) or {"-"}),
            FileObject.is_deleted.is_(False),
        ).order_by(FileObject.id.desc()).limit(page_size)).all())
        manifest_by_identity = {value: key for key, value in artifact_identities.items()}
        artifact_by_manifest: dict[int, FileObject] = {}
        for artifact in artifacts:
            manifest_id = manifest_by_identity.get(str(artifact.biz_id or ""))
            if manifest_id is not None:
                artifact_by_manifest.setdefault(manifest_id, artifact)
        can_download = any(has_permission(user or {}, code) for code in (
            "graduationDesign.archive.view",
            "graduationDesign.archive.file",
            "graduationDesign.archive.export",
        ))
        dedupe_by_manifest = {
            int(manifest.id): package_job_dedupe_key(
                tenant_id=_tid(),
                manifest_id=int(manifest.id),
                revision=int(manifest.revision or 1),
                manifest_sha256=str(manifest.manifest_sha256 or ""),
                profile_code="STANDARD_V1",
            )
            for manifest, _student in scoped_manifests
            if manifest.manifest_sha256
        }
        jobs = list(db.scalars(select(FileJob).where(
            FileJob.tenant_id == _tid(),
            FileJob.job_type == FROZEN_PACKAGE_JOB_TYPE,
            FileJob.dedupe_key.in_(set(dedupe_by_manifest.values()) or {"-"}),
            FileJob.is_deleted.is_(False),
        ).limit(page_size)).all())
        job_status_by_key = {str(job.dedupe_key): str(job.status or "PENDING").upper() for job in jobs}
        packages = []
        for manifest, student in scoped_manifests:
            artifact = artifact_by_manifest.get(int(manifest.id))
            artifact_ready = is_package_artifact_ready(artifact)
            dedupe = dedupe_by_manifest.get(int(manifest.id))
            packages.append({
                "gdStudentId": str(student.id),
                "studentId": str(student.student_id or ""),
                "studentNo": student.student_no or "",
                "studentName": student.name or "",
                "manifestId": str(manifest.id),
                "revision": int(manifest.revision or 1),
                "packageStatus": "AVAILABLE" if artifact_ready else ("UNAVAILABLE" if artifact else job_status_by_key.get(str(dedupe), "NOT_REQUESTED")),
                "artifact": _artifact_view(manifest, artifact, can_download=can_download) if artifact_ready else None,
                "target": {
                    "type": "TEACHER_STUDENT_DETAIL",
                    "path": "/pages/teacher/student-detail/index",
                    "query": {"id": str(student.student_id or "")},
                },
            })
        return {
            "scope": "GRADUATION_DATA_SCOPE",
            "total": len(visible),
            "statusCounts": status_counts,
            "items": [{
                "id": str(row.id),
                "exceptionType": row.exception_type,
                "status": row.status,
                "severity": row.severity,
                "subjectId": row.subject_id,
                "lastDetectedAt": row.last_detected_at.isoformat(timespec="seconds"),
                "target": {
                    "type": "TEACHER_STUDENT_DETAIL",
                    "path": "/pages/teacher/student-detail/index",
                    "query": {"id": exception_student_ids.get(int(row.id), "")},
                },
            } for row in visible],
            "packages": packages,
        }


__all__ = ["manifest_frozen_package", "my_frozen_package", "teacher_integrity_summary"]
