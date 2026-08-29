"""Source-bound authorization for derived document artifacts.

Registration under ``DOCUMENT_DERIVATIVE`` is intentionally deferred to C7.  These
functions never authorize from the generated file owner; every read re-enters the exact
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
    """Candidate C7 File Center resolver; fail closed on malformed or stale scope."""
    del action
    try:
        tenant_id = int(current_tenant_id() or 0)
        generated_file_id = int(getattr(file_obj, "id", 0) or 0)
        object_tenant_id = int(getattr(file_obj, "tenant_id", 0) or 0)
    except (TypeError, ValueError):
        return False
    if tenant_id <= 0 or generated_file_id <= 0 or object_tenant_id != tenant_id \
            or bool(getattr(file_obj, "is_deleted", False)):
        return False
    active = [
        item for item in bindings
        if not bool(getattr(item, "is_deleted", False))
        and str(getattr(item, "status", "")).upper() == "ACTIVE"
        and str(getattr(item, "biz_type", "")).upper() == "DOCUMENT_DERIVATIVE"
        and str(getattr(item, "file_id", "") or "").strip() == str(generated_file_id)
    ]
    for binding in active:
        scope = getattr(binding, "scope_json", None) or {}
        try:
            kind = str(scope.get("derivativeKind") or "").upper()
            if kind == "EXTRACTED_TEXT":
                artifact_id = int(scope["artifactId"])
                source_version_id = int(scope["sourceFileVersionId"])
                source_sha256 = str(scope["sourceSha256"]).strip().lower()
                persisted = db.scalars(select(FileDerivedArtifact.id).where(
                    FileDerivedArtifact.tenant_id == tenant_id,
                    FileDerivedArtifact.id == artifact_id,
                    FileDerivedArtifact.generated_file_object_id == generated_file_id,
                    FileDerivedArtifact.source_file_version_id == source_version_id,
                    FileDerivedArtifact.source_sha256 == source_sha256,
                    FileDerivedArtifact.status == "SUCCEEDED",
                ).limit(1)).first()
                if persisted is None:
                    continue
                authorize_extracted_artifact_read(
                    source_file_version_id=source_version_id,
                    source_sha256=source_sha256,
                    user=user,
                )
                return True
            if kind == "DOCUMENT_DIFF":
                result_id = int(scope["compareResultId"])
                left_version_id = int(scope["leftFileVersionId"])
                left_sha256 = str(scope["leftSourceSha256"]).strip().lower()
                right_version_id = int(scope["rightFileVersionId"])
                right_sha256 = str(scope["rightSourceSha256"]).strip().lower()
                persisted = db.scalars(select(DocumentCompareResult.id).where(
                    DocumentCompareResult.tenant_id == tenant_id,
                    DocumentCompareResult.id == result_id,
                    DocumentCompareResult.generated_file_object_id == generated_file_id,
                    DocumentCompareResult.left_file_version_id == left_version_id,
                    DocumentCompareResult.left_source_sha256 == left_sha256,
                    DocumentCompareResult.right_file_version_id == right_version_id,
                    DocumentCompareResult.right_source_sha256 == right_sha256,
                    DocumentCompareResult.status == "SUCCEEDED",
                ).limit(1)).first()
                if persisted is None:
                    continue
                authorize_compare_result_read(
                    left_file_version_id=left_version_id,
                    left_source_sha256=left_sha256,
                    right_file_version_id=right_version_id,
                    right_source_sha256=right_sha256,
                    user=user,
                )
                return True
        except (AppException, KeyError, TypeError, ValueError):
            continue
    return False


def require_compare_result_read(**kwargs) -> tuple[ExactSourceVersion, ExactSourceVersion]:
    try:
        return authorize_compare_result_read(**kwargs)
    except AppException as exc:
        # Preserve File Center's non-enumerable 404 contract for either-side revocation.
        raise not_found("派生结果不存在") from exc
