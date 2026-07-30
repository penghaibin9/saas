#!/usr/bin/env python3
"""One-time fail-closed patches for Stage 6 business acceptance residuals."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: str, old: str, new: str, marker: str) -> bool:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return False
    if old not in text:
        raise SystemExit(f"refusing to patch changed source: {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def main() -> None:
    changed: list[str] = []
    export_path = "backend/app/modules/graduation/services/graduation_material_export_service.py"
    catalog_path = "backend/app/modules/graduation/services/graduation_material_catalog_service.py"

    export_old = '''    if proposal_id: catalog.sync_record("PROPOSAL", proposal_id, user)
    if final_id: catalog.sync_record("FINAL", final_id, user)
    with session() as db:
        student = db.get(GraduationStudent, int(student_id))
        catalog.ensure_structured_snapshots(db, student, user)
        db.commit()
'''
    export_new = '''    if proposal_id: catalog.sync_record("PROPOSAL", proposal_id, user)
    if final_id: catalog.sync_record("FINAL", final_id, user)
    # System-generated PDF evidence is persisted outside the business read
    # transaction, then bound in a fresh transaction. This avoids MySQL default
    # REPEATABLE READ visibility gaps without weakening the file security gate.
    from app.modules.graduation.services import graduation_structured_snapshot_service as structured_snapshots
    structured_snapshots.prepare_all(int(student_id), user)
'''
    if replace_exact(export_path, export_old, export_new,
                     "System-generated PDF evidence is persisted outside the business read"):
        changed.append(export_path)

    freeze_old = '''        selected: list[tuple[GraduationStudentMaterial, FileVersion, FileObject]] = []
        missing: list[str] = []
        for material in materials:
            spec = catalog.SPEC_BY_CODE.get(material.material_code)
            archive_required = bool((spec or {}).get("archiveRequired", material.archive_status != "NOT_ARCHIVED"))
            required = material.material_code in required_codes
            if not archive_required and not material.current_version_id:
                continue
            if not material.current_version_id:
                if required: missing.append(material.material_name)
                continue
            version = db.scalars(select(FileVersion).where(
                FileVersion.tenant_id == _tid(), FileVersion.id == int(material.current_version_id),
                FileVersion.asset_id == int(material.asset_id), FileVersion.is_current.is_(True),
                FileVersion.is_deleted.is_(False),
            ).with_for_update()).first()
            file_obj = db.get(FileObject, int(version.file_object_id)) if version else None
            if not version or not file_obj:
                if required: missing.append(material.material_name)
                continue
            if version.status != "APPROVED" or material.review_status not in {"APPROVED", "NOT_REQUIRED"}:
                if required: missing.append(f"{material.material_name}（未审核通过）")
                continue
            try:
                legacy_ready = __import__(
                    "app.modules.graduation.services.graduation_material_center_service",
                    fromlist=["_require_file_ready"],
                )
                legacy_ready._require_file_ready(file_obj)
            except AppException:
                if required: missing.append(f"{material.material_name}（安全状态异常）")
                continue
            selected.append((material, version, file_obj))
        if missing:
            raise AppException("DATA_CONFLICT", "归档材料未齐全：" + "、".join(sorted(set(missing))))
'''
    freeze_new = '''        selected: list[tuple[GraduationStudentMaterial, FileVersion, FileObject]] = []
        problems: list[str] = []
        for material in materials:
            spec = catalog.SPEC_BY_CODE.get(material.material_code)
            archive_required = bool((spec or {}).get("archiveRequired", material.archive_status != "NOT_ARCHIVED"))
            required = material.material_code in required_codes
            if not archive_required and not material.current_version_id:
                continue
            if not material.current_version_id:
                if required:
                    problems.append(material.material_name)
                continue
            version = db.scalars(select(FileVersion).where(
                FileVersion.tenant_id == _tid(), FileVersion.id == int(material.current_version_id),
                FileVersion.asset_id == int(material.asset_id), FileVersion.is_current.is_(True),
                FileVersion.is_deleted.is_(False),
            ).with_for_update()).first()
            file_obj = db.get(FileObject, int(version.file_object_id)) if version else None
            # An optional material may be absent, but once submitted it must never be
            # silently omitted because its current version is unsafe or unapproved.
            if not version or not file_obj:
                problems.append(f"{material.material_name}（当前版本不存在）")
                continue
            if version.status != "APPROVED" or material.review_status not in {"APPROVED", "NOT_REQUIRED"}:
                problems.append(f"{material.material_name}（未审核通过）")
                continue
            try:
                legacy_ready = __import__(
                    "app.modules.graduation.services.graduation_material_center_service",
                    fromlist=["_require_file_ready"],
                )
                legacy_ready._require_file_ready(file_obj)
            except AppException:
                problems.append(f"{material.material_name}（安全状态异常）")
                continue
            selected.append((material, version, file_obj))
        if problems:
            raise AppException("DATA_CONFLICT", "归档材料未齐全或存在异常：" + "、".join(sorted(set(problems))))
'''
    if replace_exact(export_path, freeze_old, freeze_new,
                     "An optional material may be absent, but once submitted"):
        if export_path not in changed:
            changed.append(export_path)

    package_old = '''            row.version = int(row.version or 0) + 1
            for _, manifest in pairs:
                manifest.status = "PACKAGED"; manifest.package_file_id = int(zip_file.id)
            db.commit(); return _export_job_view(row)
'''
    package_new = '''            row.version = int(row.version or 0) + 1
            for _, manifest in pairs:
                manifest.status = "PACKAGED"
                manifest.package_file_id = int(zip_file.id)
                manifest_codes = {
                    item.material_code for item in items if int(item.manifest_id) == int(manifest.id)
                }
                archived_materials = db.scalars(select(GraduationStudentMaterial).where(
                    GraduationStudentMaterial.tenant_id == _tid(),
                    GraduationStudentMaterial.gd_student_id == int(manifest.target_id),
                    GraduationStudentMaterial.material_code.in_(manifest_codes or {"__NONE__"}),
                    GraduationStudentMaterial.is_deleted.is_(False),
                ).with_for_update()).all()
                for material in archived_materials:
                    material.archive_status = "ARCHIVED"
                    material.version = int(material.version or 0) + 1
            db.commit(); return _export_job_view(row)
'''
    if replace_exact(export_path, package_old, package_new,
                     'material.archive_status = "ARCHIVED"'):
        if export_path not in changed:
            changed.append(export_path)

    revoke_old = '''        for material in materials:
            material.archive_status = "ELIGIBLE" if material.review_status == "APPROVED" else "NOT_ARCHIVED"
            material.version = int(material.version or 0) + 1
        archive = db.scalars(select(GraduationArchiveRecord).where(
'''
    revoke_new = '''        for material in materials:
            material.archive_status = "ELIGIBLE" if material.review_status == "APPROVED" else "NOT_ARCHIVED"
            material.version = int(material.version or 0) + 1
        manifest_items = db.scalars(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == _tid(),
            ArchiveManifestItem.manifest_id == int(manifest.id),
            ArchiveManifestItem.is_deleted.is_(False),
        )).all()
        version_ids = {int(item.version_id) for item in manifest_items}
        versions = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.id.in_(version_ids or {-1}),
            FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
        ).with_for_update()).all()
        for version in versions:
            if version.status == "ARCHIVED":
                version.status = "APPROVED"
        student.stage = "FINAL_CHECK"
        student.version = int(student.version or 0) + 1
        archive = db.scalars(select(GraduationArchiveRecord).where(
'''
    if replace_exact(export_path, revoke_old, revoke_new,
                     'student.stage = "FINAL_CHECK"'):
        if export_path not in changed:
            changed.append(export_path)

    library_old = '''                "sensitivityLevel": row.sensitivity_level, "assetId": str(row.asset_id or ""),
                "currentVersionId": str(row.current_version_id or ""),
                "currentVersion": current_file, "versions": versions,
'''
    library_new = '''                "sensitivityLevel": row.sensitivity_level, "assetId": str(row.asset_id or ""),
                "currentVersionId": str(row.current_version_id or ""),
                "version": int(row.version or 0),
                "currentVersion": current_file, "versions": versions,
'''
    if replace_exact(catalog_path, library_old, library_new,
                     '"version": int(row.version or 0),\n                "currentVersion": current_file'):
        changed.append(catalog_path)

    scan_old = '''        all_materials = db.scalars(material_stmt).all()
        if scan_status:
            version_ids = {int(row.current_version_id) for row in all_materials if row.current_version_id}
            matched_versions = set(db.scalars(select(FileVersion.id).join(
                FileObject, FileObject.id == FileVersion.file_object_id
            ).where(
                FileVersion.tenant_id == _tid(), FileVersion.id.in_(version_ids or {-1}),
                FileObject.scan_status == scan_status.upper(),
            )).all())
            all_materials = [row for row in all_materials if row.current_version_id in matched_versions]
'''
    scan_new = '''        all_materials = db.scalars(material_stmt).all()
        version_ids = {int(row.current_version_id) for row in all_materials if row.current_version_id}
        state_rows = db.execute(select(
            FileVersion.id, FileObject.scan_status, FileObject.status,
        ).join(FileObject, FileObject.id == FileVersion.file_object_id).where(
            FileVersion.tenant_id == _tid(), FileVersion.id.in_(version_ids or {-1}),
            FileVersion.is_deleted.is_(False), FileObject.is_deleted.is_(False),
        )).all()
        version_states = {
            int(version_id): (str(scan or "").upper(), str(status or "").upper())
            for version_id, scan, status in state_rows
        }
        abnormal_scan_states = {"PENDING", "RUNNING", "SCANNING", "ERROR", "FAILED", "SCAN_FAILED", "INFECTED"}
        abnormal_material_ids = {
            int(row.id) for row in all_materials
            if row.current_version_id and (
                version_states.get(int(row.current_version_id), ("", ""))[0] in abnormal_scan_states
                or version_states.get(int(row.current_version_id), ("", ""))[1] != "AVAILABLE"
            )
        }
        scan_abnormal_student_ids = {
            int(row.gd_student_id) for row in all_materials if int(row.id) in abnormal_material_ids
        }
        if scan_status:
            wanted_scan_status = scan_status.upper()
            matched_versions = {
                version_id for version_id, (actual_scan, _status) in version_states.items()
                if actual_scan == wanted_scan_status
            }
            all_materials = [
                row for row in all_materials
                if row.current_version_id and int(row.current_version_id) in matched_versions
            ]
'''
    if replace_exact(catalog_path, scan_old, scan_new, "scan_abnormal_student_ids = {"):
        if catalog_path not in changed:
            changed.append(catalog_path)

    row_old = '''            approved = sum(item.review_status in {"APPROVED", "NOT_REQUIRED"} for item in required)
            rows.append({
'''
    row_new = '''            approved = sum(item.review_status in {"APPROVED", "NOT_REQUIRED"} for item in required)
            scan_abnormal = sum(int(item.id) in abnormal_material_ids for item in materials)
            rows.append({
'''
    replace_exact(catalog_path, row_old, row_new,
                  "scan_abnormal = sum(int(item.id) in abnormal_material_ids")

    ready_old = '''                "approvedRequiredCount": approved,
                "archiveReady": bool(required and approved == len(required) and missing == pending == returned == 0),
'''
    ready_new = '''                "approvedRequiredCount": approved, "scanAbnormalCount": scan_abnormal,
                "archiveReady": bool(
                    required and approved == len(required)
                    and missing == pending == returned == scan_abnormal == 0
                ),
'''
    replace_exact(catalog_path, ready_old, ready_new, '"scanAbnormalCount": scan_abnormal')

    summary_old = '''                "completeStudents": max(0, total - len(missing_students | pending_students | returned_students)),
                "missingStudents": len(missing_students), "scanAbnormalStudents": 0,
'''
    summary_new = '''                "completeStudents": max(0, total - len(
                    missing_students | pending_students | returned_students | scan_abnormal_student_ids
                )),
                "missingStudents": len(missing_students),
                "scanAbnormalStudents": len(scan_abnormal_student_ids),
'''
    replace_exact(catalog_path, summary_old, summary_new,
                  '"scanAbnormalStudents": len(scan_abnormal_student_ids)')

    print("phase 6 business residual patch complete:", ", ".join(changed) if changed else "already applied")


if __name__ == "__main__":
    main()
