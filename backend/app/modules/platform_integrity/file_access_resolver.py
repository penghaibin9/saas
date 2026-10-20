"""File Center authorization adapter for PLAT-A package artifacts."""
from __future__ import annotations

from sqlalchemy import select

from app.core.permissions import has_permission
from app.models.file import ArchiveManifest
from app.modules.platform_integrity.deterministic_package import STANDARD_PROFILE_V1
from app.modules.platform_integrity.frozen_package_service import (
    PACKAGE_BIZ_TYPE,
    frozen_package_artifact_biz_id,
)
from app.services.file_access_service import register_file_resolver
from app.services.db_service import _tid


@register_file_resolver(PACKAGE_BIZ_TYPE)
def frozen_evidence_package_resolver(db, file_obj, bindings: list[object], user: dict, action: str) -> bool:
    """Authorize through the frozen manifest's owning domain; never via a raw URL."""
    if db is None:
        return False
    try:
        if int(file_obj.tenant_id) != _tid():
            return False
    except (TypeError, ValueError):
        return False
    biz_id = str(file_obj.biz_id or "")
    prefix = biz_id.split(":", 1)[0]
    if not prefix.startswith("m") or not prefix[1:].isdigit():
        return False
    manifest = db.scalars(select(ArchiveManifest).where(
        ArchiveManifest.tenant_id == int(file_obj.tenant_id),
        ArchiveManifest.id == int(prefix[1:]),
        ArchiveManifest.is_deleted.is_(False),
    )).first()
    if not manifest:
        return False
    if str(manifest.module_code or "").upper() != "GRADUATION":
        return False
    if str(manifest.status or "").upper() not in {"FROZEN", "PACKAGED"}:
        return False
    if biz_id != frozen_package_artifact_biz_id(manifest, STANDARD_PROFILE_V1):
        return False
    try:
        from app.models import GraduationStudent
        from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
        from app.modules.graduation.services.graduation_scope_service import assert_student_access

        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == int(file_obj.tenant_id),
            GraduationStudent.id == int(manifest.target_id),
            GraduationStudent.is_deleted.is_(False),
        )).first()
        if not student:
            return False
        actor = user or {}
        if str(actor.get("userType") or "").upper() == "STUDENT":
            current = resolve_current_gd_student(db, actor)
            return bool(current and int(current.id) == int(student.id))
        if not any(has_permission(actor, code) for code in (
            "graduationDesign.archive.view",
            "graduationDesign.archive.file",
            "graduationDesign.archive.export",
        )):
            return False
        assert_student_access(db, student, f"frozen.package.{action}")
        return True
    except Exception:
        return False


__all__ = ["frozen_evidence_package_resolver"]
