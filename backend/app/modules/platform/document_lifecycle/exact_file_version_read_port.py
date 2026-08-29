"""Source-bound, read-only access to one immutable ``FileVersion``.

The existing ``file_version_service`` projects a business binding family.  Document
derivation needs a narrower contract: one exact version, its exact byte identity and the
same File Center/domain authorization used by source preview.  This module composes those
authorities and owns no FileObject/FileAsset/FileVersion/FileBinding mutation.
"""
from __future__ import annotations

import hmac
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.file import FileAsset, FileBinding, FileObject, FileVersion
from app.services import file_access_resolvers as _file_access_resolvers  # noqa: F401
from app.services.file_access_service import authorize_file_object

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_ACTIONS = {
    "meta": "meta",
    "preview": "preview",
    "extract": "preview",
    "compare": "preview",
    "derived-read": "preview",
}


@dataclass(frozen=True, slots=True)
class ExactSourceVersion:
    tenant_id: int
    asset_id: int
    file_version_id: int
    file_object_id: int
    version_no: int
    source_sha256: str
    mime_type: str | None
    ext: str | None
    size_bytes: int
    sensitivity_level: str
    source_binding_refs: tuple[dict[str, Any], ...]


@runtime_checkable
class IExactFileVersionReadPort(Protocol):
    def resolve(
        self,
        *,
        file_version_id: int,
        expected_sha256: str,
        action: str,
        user: dict,
    ) -> ExactSourceVersion: ...


@dataclass(frozen=True, slots=True)
class _ExactVersionRows:
    version: FileVersion
    asset: FileAsset
    file_object: FileObject
    all_file_bindings: tuple[FileBinding, ...]
    exact_bindings: tuple[FileBinding, ...]


def _load_exact_version(db, tenant_id: int, file_version_id: int) -> _ExactVersionRows | None:
    row = db.execute(
        select(FileVersion, FileAsset, FileObject)
        .join(
            FileAsset,
            (FileAsset.id == FileVersion.asset_id)
            & (FileAsset.tenant_id == FileVersion.tenant_id)
            & FileAsset.is_deleted.is_(False),
        )
        .join(
            FileObject,
            (FileObject.id == FileVersion.file_object_id)
            & (FileObject.tenant_id == FileVersion.tenant_id)
            & FileObject.is_deleted.is_(False),
        )
        .where(
            FileVersion.id == file_version_id,
            FileVersion.tenant_id == tenant_id,
            FileVersion.is_deleted.is_(False),
        )
        .limit(1)
    ).first()
    if row is None:
        return None

    version, asset, file_object = row
    bindings = tuple(db.scalars(
        select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.file_id == int(file_object.id),
            FileBinding.is_deleted.is_(False),
        ).order_by(FileBinding.version_no.desc(), FileBinding.id.desc())
    ).all())
    exact = tuple(
        binding
        for binding in bindings
        if binding.version_id is not None
        and int(binding.version_id) == int(version.id)
        and binding.asset_id is not None
        and int(binding.asset_id) == int(asset.id)
    )
    return _ExactVersionRows(
        version=version,
        asset=asset,
        file_object=file_object,
        all_file_bindings=bindings,
        exact_bindings=exact,
    )


def _binding_ref(binding: FileBinding) -> dict[str, Any]:
    """Return bounded business identity only; never copy storage/session credentials."""
    return {
        "bindingId": int(binding.id),
        "bizType": str(binding.biz_type),
        "bizId": str(binding.biz_id),
        "relationType": str(binding.relation_type),
        "moduleCode": str(binding.module_code) if binding.module_code else None,
        "subjectType": str(binding.subject_type),
        "subjectId": str(binding.subject_id) if binding.subject_id else None,
        "batchId": str(binding.batch_id) if binding.batch_id else None,
        "assetId": int(binding.asset_id) if binding.asset_id is not None else None,
        "fileVersionId": int(binding.version_id) if binding.version_id is not None else None,
        "status": str(binding.status),
    }


class ExactFileVersionReadPort(IExactFileVersionReadPort):
    """Production exact-version adapter over current File Center authorization."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
        loader: Callable[[Any, int, int], _ExactVersionRows | None] | None = None,
        authorizer: Callable[..., bool] | None = None,
    ) -> None:
        self._session_factory = session_factory or get_sessionmaker()
        self._loader = loader or _load_exact_version
        self._authorizer = authorizer or authorize_file_object

    def resolve(
        self,
        *,
        file_version_id: int,
        expected_sha256: str,
        action: str,
        user: dict,
    ) -> ExactSourceVersion:
        tenant_id = self._tenant_id()
        version_id = self._version_id(file_version_id)
        expected_sha = self._expected_sha(expected_sha256)
        source_action = self._source_action(action)

        db = self._session_factory()
        try:
            rows = self._loader(db, tenant_id, version_id)
            if rows is None or not rows.exact_bindings:
                raise not_found("文件版本不存在")

            actual_sha = str(rows.file_object.sha256 or "").strip().lower()
            if not _SHA256_RE.fullmatch(actual_sha) or not hmac.compare_digest(actual_sha, expected_sha):
                # Do not reveal whether the version exists when its pinned byte identity differs.
                raise not_found("文件版本不存在")

            if not self._authorizer(
                rows.file_object,
                list(rows.all_file_bindings),
                user or {},
                source_action,
                db=db,
            ):
                raise not_found("文件版本不存在")

            return ExactSourceVersion(
                tenant_id=tenant_id,
                asset_id=int(rows.asset.id),
                file_version_id=int(rows.version.id),
                file_object_id=int(rows.file_object.id),
                version_no=int(rows.version.version_no),
                source_sha256=actual_sha,
                mime_type=rows.file_object.mime_type,
                ext=rows.file_object.ext,
                size_bytes=int(rows.file_object.size_bytes or 0),
                sensitivity_level=str(
                    rows.asset.sensitivity_level
                    or rows.file_object.security_level
                    or "PERSONAL"
                ).upper(),
                source_binding_refs=tuple(_binding_ref(item) for item in rows.exact_bindings),
            )
        finally:
            db.close()

    @staticmethod
    def _tenant_id() -> int:
        raw = str(current_tenant_id() or "").strip()
        if not raw.isdigit() or int(raw) <= 0:
            raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
        return int(raw)

    @staticmethod
    def _version_id(value: int) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "fileVersionId 格式不正确") from exc
        if normalized <= 0:
            raise AppException("VALIDATION_ERROR", "fileVersionId 格式不正确")
        return normalized

    @staticmethod
    def _expected_sha(value: str) -> str:
        normalized = str(value or "").strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise AppException("VALIDATION_ERROR", "expectedSha256 格式不正确")
        return normalized

    @staticmethod
    def _source_action(value: str) -> str:
        normalized = str(value or "").strip().lower()
        source_action = _SOURCE_ACTIONS.get(normalized)
        if source_action is None:
            raise AppException("VALIDATION_ERROR", "不支持的文件版本读取动作")
        return source_action
