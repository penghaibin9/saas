"""Stable contracts shared by PLAT-A domain adapters and clients."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SnapshotAssetRef:
    asset_id: int
    version_id: int
    file_object_id: int
    file_name: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class PackageArtifactRef:
    """Platform package output contract; never contains storage location data."""

    tenant_id: int
    package_kind: str
    source_type: str
    source_id: str
    source_version: str
    file_object_id: int
    file_name: str
    size_bytes: int
    sha256: str
    created_at: datetime
    sensitivity_level: str
    resolver_code: str
    profile_code: str

    def as_dict(self) -> dict:
        return {
            "tenantId": str(self.tenant_id),
            "packageKind": self.package_kind,
            "sourceType": self.source_type,
            "sourceId": self.source_id,
            "sourceVersion": self.source_version,
            "fileId": str(self.file_object_id),
            "fileObjectId": str(self.file_object_id),
            "fileName": self.file_name,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
            "createdAt": self.created_at.isoformat(timespec="microseconds") + "Z",
            "sensitivityLevel": self.sensitivity_level,
            "resolverCode": self.resolver_code,
            "profileCode": self.profile_code,
        }


def frozen_manifest_artifact_ref(
    *,
    tenant_id: int,
    manifest: object,
    file_object: object,
    profile_code: str,
    resolver_code: str,
) -> PackageArtifactRef:
    """Project one FileObject without importing a domain model or exposing storage fields."""
    created_at = getattr(file_object, "created_at", None)
    if not isinstance(created_at, datetime):
        raise ValueError("package artifact requires persisted created_at")
    revision = int(getattr(manifest, "revision", 1) or 1)
    manifest_sha = str(getattr(manifest, "manifest_sha256", "") or "").lower()
    return PackageArtifactRef(
        tenant_id=int(tenant_id),
        package_kind="FROZEN_MANIFEST_PACKAGE",
        source_type="ARCHIVE_MANIFEST",
        source_id=str(getattr(manifest, "id")),
        source_version=f"r{revision}:{manifest_sha}",
        file_object_id=int(getattr(file_object, "id")),
        file_name=str(getattr(file_object, "file_name")),
        size_bytes=int(getattr(file_object, "size_bytes", 0) or 0),
        sha256=str(getattr(file_object, "sha256", "") or "").lower(),
        created_at=created_at,
        sensitivity_level=str(getattr(file_object, "security_level", "SENSITIVE") or "SENSITIVE"),
        resolver_code=str(resolver_code),
        profile_code=str(profile_code).upper(),
    )


@dataclass(frozen=True, slots=True)
class FrozenPackageResult:
    manifest_id: int
    revision: int
    manifest_sha256: str
    digest_schema_version: str
    artifact: PackageArtifactRef
    reused: bool

    def as_dict(self) -> dict:
        value = asdict(self)
        value["manifestId"] = str(value.pop("manifest_id"))
        value["manifestSha256"] = value.pop("manifest_sha256")
        value["digestSchemaVersion"] = value.pop("digest_schema_version")
        value["artifact"] = self.artifact.as_dict()
        return value
