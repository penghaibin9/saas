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
    if replace_exact(
        "backend/app/modules/graduation/services/graduation_material_export_service.py",
        export_old,
        export_new,
        "System-generated PDF evidence is persisted outside the business read",
    ):
        changed.append("backend/app/modules/graduation/services/graduation_material_export_service.py")

    library_old = '''                "sensitivityLevel": row.sensitivity_level, "assetId": str(row.asset_id or ""),
                "currentVersionId": str(row.current_version_id or ""),
                "currentVersion": current_file, "versions": versions,
'''
    library_new = '''                "sensitivityLevel": row.sensitivity_level, "assetId": str(row.asset_id or ""),
                "currentVersionId": str(row.current_version_id or ""),
                "version": int(row.version or 0),
                "currentVersion": current_file, "versions": versions,
'''
    if replace_exact(
        "backend/app/modules/graduation/services/graduation_material_catalog_service.py",
        library_old,
        library_new,
        '"version": int(row.version or 0),\n                "currentVersion": current_file',
    ):
        changed.append("backend/app/modules/graduation/services/graduation_material_catalog_service.py")

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
    if replace_exact(
        "backend/app/modules/graduation/services/graduation_material_catalog_service.py",
        scan_old,
        scan_new,
        "scan_abnormal_student_ids = {",
    ):
        if "backend/app/modules/graduation/services/graduation_material_catalog_service.py" not in changed:
            changed.append("backend/app/modules/graduation/services/graduation_material_catalog_service.py")

    row_old = '''            approved = sum(item.review_status in {"APPROVED", "NOT_REQUIRED"} for item in required)
            rows.append({
'''
    row_new = '''            approved = sum(item.review_status in {"APPROVED", "NOT_REQUIRED"} for item in required)
            scan_abnormal = sum(int(item.id) in abnormal_material_ids for item in materials)
            rows.append({
'''
    replace_exact(
        "backend/app/modules/graduation/services/graduation_material_catalog_service.py",
        row_old,
        row_new,
        "scan_abnormal = sum(int(item.id) in abnormal_material_ids",
    )

    ready_old = '''                "approvedRequiredCount": approved,
                "archiveReady": bool(required and approved == len(required) and missing == pending == returned == 0),
'''
    ready_new = '''                "approvedRequiredCount": approved, "scanAbnormalCount": scan_abnormal,
                "archiveReady": bool(
                    required and approved == len(required)
                    and missing == pending == returned == scan_abnormal == 0
                ),
'''
    replace_exact(
        "backend/app/modules/graduation/services/graduation_material_catalog_service.py",
        ready_old,
        ready_new,
        '"scanAbnormalCount": scan_abnormal',
    )

    summary_old = '''                "completeStudents": max(0, total - len(missing_students | pending_students | returned_students)),
                "missingStudents": len(missing_students), "scanAbnormalStudents": 0,
'''
    summary_new = '''                "completeStudents": max(0, total - len(
                    missing_students | pending_students | returned_students | scan_abnormal_student_ids
                )),
                "missingStudents": len(missing_students),
                "scanAbnormalStudents": len(scan_abnormal_student_ids),
'''
    replace_exact(
        "backend/app/modules/graduation/services/graduation_material_catalog_service.py",
        summary_old,
        summary_new,
        '"scanAbnormalStudents": len(scan_abnormal_student_ids)',
    )

    print("phase 6 business residual patch complete:", ", ".join(changed) if changed else "already applied")


if __name__ == "__main__":
    main()
