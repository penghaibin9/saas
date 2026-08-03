"""阶段 6正式交付编排：安全结构化快照 → 真实 Manifest → ExportJob。"""
from __future__ import annotations

from app.modules.graduation.services import graduation_material_export_service as exports
from app.modules.graduation.services import graduation_structured_snapshot_service as snapshots


def freeze_manifest(gd_student_id: int, archive_batch_no: str, user: dict) -> dict:
    snapshots.prepare_all(int(gd_student_id), user)
    return exports.freeze_manifest(int(gd_student_id), archive_batch_no, user)


latest_manifest = exports.latest_manifest
revoke_manifest = exports.revoke_manifest
create_export_job = exports.create_export_job
create_student_export_job = exports.create_student_export_job
get_export_job = exports.get_export_job
run_export_job = exports.run_export_job
