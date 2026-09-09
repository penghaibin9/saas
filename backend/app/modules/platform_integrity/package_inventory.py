"""Machine-readable production package taxonomy for PLAT-A C0.

This ledger classifies existing authorities; it does not route, rewrite, or own
their input semantics. Keep the source-path coverage tests in sync when a new
manifest/package writer enters production.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

FROZEN_EVIDENCE = "FROZEN_EVIDENCE"
DOMAIN_SNAPSHOT = "DOMAIN_SNAPSHOT"
EXPORT_ONLY = "EXPORT_ONLY"
LEGACY = "LEGACY"
UNKNOWN = "UNKNOWN"
ALLOWED_CLASSIFICATIONS = frozenset({FROZEN_EVIDENCE, DOMAIN_SNAPSHOT, EXPORT_ONLY, LEGACY})


@dataclass(frozen=True, slots=True)
class ProductionPackagePath:
    code: str
    classification: str
    selected_scope: bool
    manifest_writers: tuple[str, ...] = ()
    builders: tuple[str, ...] = ()
    package_file_writers: tuple[str, ...] = ()
    file_job_types: tuple[str, ...] = ()
    resolver_codes: tuple[str, ...] = ()
    download_endpoints: tuple[str, ...] = ()
    authority_note: str = ""


PRODUCTION_PACKAGE_PATHS = (
    ProductionPackagePath(
        code="GRADUATION_MATERIAL_MANIFEST_V2",
        classification=FROZEN_EVIDENCE,
        selected_scope=True,
        manifest_writers=("backend/app/modules/graduation/materials/manifest_service.py",),
        builders=("backend/app/modules/platform_integrity/frozen_package_service.py",),
        package_file_writers=("backend/app/modules/graduation/materials/manifest_service.py",),
        file_job_types=("FROZEN_EVIDENCE_PACKAGE",),
        resolver_codes=("FROZEN_EVIDENCE_PACKAGE", "GRADUATION_ARCHIVE_PACKAGE"),
        download_endpoints=("/api/v1/files/download/{file_id}",),
        authority_note="New snapshot manifests use PLATFORM_MANIFEST_DIGEST_V1; historical manifests retain legacy semantics.",
    ),
    ProductionPackagePath(
        code="INTERNSHIP_MATERIAL_MANIFEST",
        classification=FROZEN_EVIDENCE,
        selected_scope=False,
        manifest_writers=(
            "backend/app/modules/internship/services/internship_material_center_compat.py",
            "backend/app/modules/internship/services/internship_material_center_facade.py",
            "backend/app/modules/internship/services/internship_material_center_service.py",
        ),
        builders=("backend/app/modules/internship/services/internship_streaming_package_service.py",),
        package_file_writers=("backend/app/modules/internship/services/internship_streaming_package_service.py",),
        resolver_codes=("INTERNSHIP_EVIDENCE_PACKAGE",),
        download_endpoints=(
            "/api/v1/internship/archive-packages/{package_id}/download",
            "/api/v1/internship/evidence-packages/{package_id}/download",
        ),
        authority_note="Frozen items exist, but its domain adapter remains the current package/state authority until separately migrated.",
    ),
    ProductionPackagePath(
        code="AFFAIRS_MATERIAL_MANIFEST",
        classification=FROZEN_EVIDENCE,
        selected_scope=False,
        manifest_writers=("backend/app/modules/student_affairs/services/affairs_material_center_service.py",),
        builders=(),
        resolver_codes=("AFFAIRS_ARCHIVE_MANIFEST",),
        authority_note="Material-version manifest is frozen, but it must not redefine the Affairs profile archive input semantics.",
    ),
    ProductionPackagePath(
        code="AFFAIRS_PROFILE_ARCHIVE",
        classification=DOMAIN_SNAPSHOT,
        selected_scope=False,
        builders=("backend/app/services/affairs_archive_service.py",),
        package_file_writers=("backend/app/services/affairs_archive_service.py",),
        resolver_codes=("AFFAIRS_ARCHIVE",),
        download_endpoints=("/api/v1/files/download/{file_id}",),
        authority_note="Live profile/timeline XLSX, domain state machine, lease and FileVersion writer stay authoritative.",
    ),
    ProductionPackagePath(
        code="INTERNSHIP_ARCHIVE_SNAPSHOT_V2",
        classification=DOMAIN_SNAPSHOT,
        selected_scope=False,
        builders=("backend/app/modules/internship/services/internship_archive_service.py",),
        package_file_writers=("backend/app/modules/internship/services/internship_archive_service.py",),
        resolver_codes=("INTERNSHIP_ARCHIVE_PACKAGE",),
        download_endpoints=("/api/v1/internship/archive-packages/{package_id}/download",),
        authority_note="Builds from the internship-owned immutable archive snapshot and keeps its domain package record.",
    ),
    ProductionPackagePath(
        code="INTERNSHIP_EVIDENCE_EXPORT",
        classification=EXPORT_ONLY,
        selected_scope=False,
        builders=("backend/app/modules/internship/services/internship_evidence_package_service.py",),
        package_file_writers=("backend/app/modules/internship/services/internship_evidence_package_service.py",),
        resolver_codes=("INTERNSHIP_EVIDENCE_PACKAGE",),
        download_endpoints=("/api/v1/internship/evidence-packages/{package_id}/download",),
        authority_note="On-demand domain evidence export; not a manifest-only platform frozen build.",
    ),
    ProductionPackagePath(
        code="ACADEMIC_ARCHIVE_EXPORT",
        classification=EXPORT_ONLY,
        selected_scope=False,
        manifest_writers=(
            "backend/app/modules/academic_affairs/services/academic_affairs_archive_manifest_service.py",
            "backend/app/services/sandbox_school_academic_archive_seed.py",
        ),
        builders=("backend/app/modules/academic_affairs/services/academic_affairs_archive_core_service.py",),
        download_endpoints=("/api/v1/academic-affairs/archive/batches/{bid}/export",),
        authority_note=(
            "Academic term archive/export authority is not File Center ArchiveManifest truth; "
            "the 20K sandbox writer seeds the same formal academic manifest algorithm for release evidence."
        ),
    ),
    ProductionPackagePath(
        code="GRADUATION_BULK_ARCHIVE_EXPORT",
        classification=EXPORT_ONLY,
        selected_scope=False,
        builders=("backend/app/modules/graduation/materials/export_service.py",),
        resolver_codes=("GRADUATION_ARCHIVE_PACKAGE", "GRADUATION_ARCHIVE_INDEX"),
        download_endpoints=("/api/v1/graduation/material-center/packages/{file_id}/download",),
        authority_note="Batch export remains a job/operator-scoped export and does not replace per-manifest frozen artifacts.",
    ),
)


def machine_ledger() -> list[dict]:
    rows = []
    seen: set[str] = set()
    for item in PRODUCTION_PACKAGE_PATHS:
        if item.code in seen:
            raise RuntimeError(f"duplicate package taxonomy code: {item.code}")
        if item.classification not in ALLOWED_CLASSIFICATIONS:
            raise RuntimeError(f"unclassified production package path: {item.code}")
        seen.add(item.code)
        rows.append(asdict(item))
    return rows


__all__ = [
    "ALLOWED_CLASSIFICATIONS",
    "DOMAIN_SNAPSHOT",
    "EXPORT_ONLY",
    "FROZEN_EVIDENCE",
    "LEGACY",
    "PRODUCTION_PACKAGE_PATHS",
    "ProductionPackagePath",
    "machine_ledger",
]
