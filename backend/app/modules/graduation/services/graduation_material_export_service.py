"""Deprecated thin facade for V2 manifest queries and archive exports."""
from app.modules.graduation.materials.export_service import create_export_job, create_student_export_job, run_export_job
from app.modules.graduation.materials.manifest_service import file_archive as freeze_manifest, revoke_manifest
from app.modules.graduation.materials.query_service import get_export_job, latest_manifest

__all__ = [
    "create_export_job", "create_student_export_job", "freeze_manifest", "get_export_job",
    "latest_manifest", "revoke_manifest", "run_export_job",
]
