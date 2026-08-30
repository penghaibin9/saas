"""Source-bound authorization for derived document artifacts.

Registration under ``DOCUMENT_DERIVATIVE`` uses this resolver.  These functions never
authorize from the generated file owner; every read re-enters the exact
source version port, and comparison is denied unless both sides still authorize.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found
from app.modules.platform.document_lifecycle.models import (
    DocumentCompareResult,
    FileDerivedArtifact,
)
from app.modules.platform.document_lifecycle.exact_file_version_read_port import (
    ExactFileVersionReadPort,
    ExactSourceVersion,
    IExactFileVersionReadPort,
)


def authorize_extracted_artifact_read(
    *, source_file_version_id: int, source_sha256: str, user: dict,
    port: IExactFileVersionReadPort | None = None,
) -> ExactSourceVersion:
    return (port or ExactFileVersionReadPort()).resolve(
        file_version_id=source_file_version_id,
        expected_sha256=source_sha256,
        action="derived-read",
        user=user,
    )


def authorize_compare_result_read(
    *,
    left_file_version_id: int,
    left_source_sha256: str,
    right_file_version_id: int,
    right_source_sha256: str,
    user: dict,
    port: IExactFileVersionReadPort | None = None,
) -> tuple[ExactSourceVersion, ExactSourceVersion]:
    exact_port = port or ExactFileVersionReadPort()
    left = exact_port.resolve(
        file_version_id=left_file_version_id,
        expected_sha256=left_source_sha256,
        action="derived-read",
        user=user,
    )
    right = exact_port.resolve(
        file_version_id=right_file_version_id,
        expected_sha256=right_source_sha256,
        action="derived-read",
        user=user,
    )
    return left, right


def document_derivative_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """Resolve only the persisted artifact-to-FileObject relation, then reauthorize sources."""
    del bindings, action
    try:
        tenant_id = int(current_tenant_id() or 0)
        generated_file_id = int(getattr(file_obj, "id", 0) or 0)
        object_tenant_id = int(getattr(file_obj, "tenant_id", 0) or 0)
    except (TypeError, ValueError):
        return False
    if tenant_id <= 0 or generated_file_id <= 0 or object_tenant_id != tenant_id \
            or bool(getattr(file_obj, "is_deleted", False)) \
            or str(getattr(file_obj, "biz_type", "")).upper() != "DOCUMENT_DERIVATIVE":
        return False
    try:
        artifacts = list(db.scalars(select(FileDerivedArtifact).where(
            FileDerivedArtifact.tenant_id == tenant_id,
            FileDerivedArtifact.generated_file_object_id == generated_file_id,
            FileDerivedArtifact.status == "SUCCEEDED",
        ).limit(2)).all())
        comparisons = list(db.scalars(select(DocumentCompareResult).where(
            DocumentCompareResult.tenant_id == tenant_id,
            DocumentCompareResult.generated_file_object_id == generated_file_id,
            DocumentCompareResult.status == "SUCCEEDED",
        ).limit(2)).all())
        if len(artifacts) + len(comparisons) != 1:
            return False
        if artifacts:
            artifact = artifacts[0]
            authorize_extracted_artifact_read(
                source_file_version_id=int(artifact.source_file_version_id),
                source_sha256=str(artifact.source_sha256).strip().lower(),
                user=user,
            )
            return True
        result = comparisons[0]
        authorize_compare_result_read(
            left_file_version_id=int(result.left_file_version_id),
            left_source_sha256=str(result.left_source_sha256).strip().lower(),
            right_file_version_id=int(result.right_file_version_id),
            right_source_sha256=str(result.right_source_sha256).strip().lower(),
            user=user,
        )
        return True
    except (AppException, AttributeError, TypeError, ValueError):
        return False


def require_compare_result_read(**kwargs) -> tuple[ExactSourceVersion, ExactSourceVersion]:
    try:
        return authorize_compare_result_read(**kwargs)
    except AppException as exc:
        # Preserve File Center's non-enumerable 404 contract for either-side revocation.
        raise not_found("派生结果不存在") from exc
