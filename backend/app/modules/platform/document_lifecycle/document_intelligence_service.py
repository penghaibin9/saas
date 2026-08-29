"""Source-authorized read projection for PLAT-C jobs and derived artifacts."""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found
from app.models.file import FileAsset, FileJob, FileObject, FileVersion
from app.modules.platform.document_lifecycle.derived_access import (
    authorize_compare_result_read,
    authorize_extracted_artifact_read,
)
from app.modules.platform.document_lifecycle.models import (
    DocumentCompareResult,
    FileDerivedArtifact,
)
from app.modules.platform.document_lifecycle.exact_file_version_read_port import ExactFileVersionReadPort
from app.services.storage import get_backend

MAX_DERIVED_BODY_BYTES = 25 * 1024 * 1024


def _tenant_id() -> int:
    try:
        value = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return value


def _reauthorize_job_payload(payload: dict[str, Any], *, user: dict) -> None:
    contract = str(payload.get("contract") or "")
    if contract == "PLAT_C_DOCUMENT_EXTRACT_V1":
        source = dict(payload.get("source") or {})
        authorize_extracted_artifact_read(
            source_file_version_id=int(source.get("file_version_id") or 0),
            source_sha256=str(source.get("source_sha256") or ""),
            user=user,
        )
        return
    if contract == "PLAT_C_DOCUMENT_COMPARE_V1":
        left = dict(payload.get("left") or {})
        right = dict(payload.get("right") or {})
        authorize_compare_result_read(
            left_file_version_id=int(left.get("file_version_id") or 0),
            left_source_sha256=str(left.get("source_sha256") or ""),
            right_file_version_id=int(right.get("file_version_id") or 0),
            right_source_sha256=str(right.get("source_sha256") or ""),
            user=user,
        )
        return
    raise not_found("文档处理任务不存在")


def job_view(db, *, job_id: int, user: dict) -> dict[str, Any]:
    row = db.scalars(select(FileJob).where(
        FileJob.tenant_id == _tenant_id(),
        FileJob.id == int(job_id),
        FileJob.job_type.in_(("DOCUMENT_EXTRACT", "DOCUMENT_COMPARE")),
        FileJob.is_deleted.is_(False),
    ).limit(1)).first()
    if row is None:
        raise not_found("文档处理任务不存在")
    _reauthorize_job_payload(dict(row.payload_json or {}), user=user)
    return {
        "jobId": str(row.id),
        "jobType": row.job_type,
        "status": row.status,
        "attempts": int(row.attempts or 0),
        "result": row.result_json if row.status == "SUCCEEDED" else None,
        "errorCode": (row.result_json or {}).get("errorCode") if row.status in {"FAILED", "DEAD"} else None,
    }


def version_timeline(db, *, asset_id: int, user: dict, limit: int = 50) -> dict[str, Any]:
    """List only versions that independently pass the exact source ACL."""
    rows = db.execute(
        select(FileVersion.id, FileVersion.version_no, FileObject.sha256)
        .join(FileAsset, (FileAsset.id == FileVersion.asset_id)
              & (FileAsset.tenant_id == FileVersion.tenant_id)
              & FileAsset.is_deleted.is_(False))
        .join(FileObject, (FileObject.id == FileVersion.file_object_id)
              & (FileObject.tenant_id == FileVersion.tenant_id)
              & FileObject.is_deleted.is_(False))
        .where(
            FileVersion.tenant_id == _tenant_id(),
            FileVersion.asset_id == int(asset_id),
            FileVersion.is_deleted.is_(False),
        )
        .order_by(FileVersion.version_no.desc(), FileVersion.id.desc())
        .limit(min(100, max(1, int(limit))))
    ).all()
    port = ExactFileVersionReadPort()
    items = []
    for version_id, version_no, sha256 in rows:
        try:
            source = port.resolve(
                file_version_id=int(version_id),
                expected_sha256=str(sha256 or ""),
                action="compare",
                user=user,
            )
        except AppException:
            continue
        items.append({
            "fileVersionId": str(source.file_version_id),
            "versionNo": int(version_no),
            "sourceSha256": source.source_sha256,
            "mimeType": source.mime_type,
            "ext": source.ext,
            "sizeBytes": source.size_bytes,
            "sensitivityLevel": source.sensitivity_level,
            "allowedActions": ["extract", "compare", "openSource"],
        })
    return {"assetId": str(asset_id), "items": items}


def _load_derived_json(db, *, file_object_id: int, expected_sha256: str) -> dict[str, Any]:
    row = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tenant_id(),
        FileObject.id == int(file_object_id),
        FileObject.biz_type == "DOCUMENT_DERIVATIVE",
        FileObject.is_deleted.is_(False),
    ).limit(1)).first()
    if row is None:
        raise not_found("派生结果不存在")
    actual_sha = str(row.sha256 or "").strip().lower()
    if not hmac.compare_digest(actual_sha, str(expected_sha256 or "").strip().lower()):
        raise not_found("派生结果不存在")
    key = str(row.object_key or row.file_key or "").strip()
    path = get_backend().fetch_local(key) if key else None
    if path is None or not path.is_file():
        raise not_found("派生结果不存在")
    with path.open("rb") as stream:
        body = stream.read(MAX_DERIVED_BODY_BYTES + 1)
    if len(body) > MAX_DERIVED_BODY_BYTES \
            or not hmac.compare_digest(hashlib.sha256(body).hexdigest(), actual_sha):
        raise not_found("派生结果不存在")
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise not_found("派生结果不存在") from exc
    if not isinstance(value, dict):
        raise not_found("派生结果不存在")
    return value


def extracted_artifact_view(db, *, artifact_id: int, user: dict,
                            offset: int = 0, limit: int = 100) -> dict[str, Any]:
    row = db.scalars(select(FileDerivedArtifact).where(
        FileDerivedArtifact.tenant_id == _tenant_id(),
        FileDerivedArtifact.id == int(artifact_id),
    ).limit(1)).first()
    if row is None:
        raise not_found("派生结果不存在")
    authorize_extracted_artifact_read(
        source_file_version_id=int(row.source_file_version_id),
        source_sha256=str(row.source_sha256),
        user=user,
    )
    size = min(200, max(1, int(limit)))
    start = max(0, int(offset))
    blocks: list[dict[str, Any]] = []
    if row.status == "SUCCEEDED" and row.generated_file_object_id and row.content_sha256:
        artifact = _load_derived_json(
            db,
            file_object_id=int(row.generated_file_object_id),
            expected_sha256=str(row.content_sha256),
        )
        blocks = list((artifact.get("document") or {}).get("blocks") or [])
    return {
        "artifactId": str(row.id),
        "status": row.status,
        "sourceFileVersionId": str(row.source_file_version_id),
        "sourceSha256": row.source_sha256,
        "extractorCode": row.extractor_code,
        "extractorVersion": row.extractor_version,
        "blockCount": int(row.block_count or 0),
        "blocks": blocks[start:start + size],
        "nextOffset": start + size if start + size < len(blocks) else None,
    }


def compare_result_view(db, *, result_id: int, user: dict,
                        offset: int = 0, limit: int = 100) -> dict[str, Any]:
    row = db.scalars(select(DocumentCompareResult).where(
        DocumentCompareResult.tenant_id == _tenant_id(),
        DocumentCompareResult.id == int(result_id),
    ).limit(1)).first()
    if row is None:
        raise not_found("派生结果不存在")
    authorize_compare_result_read(
        left_file_version_id=int(row.left_file_version_id),
        left_source_sha256=str(row.left_source_sha256),
        right_file_version_id=int(row.right_file_version_id),
        right_source_sha256=str(row.right_source_sha256),
        user=user,
    )
    size = min(200, max(1, int(limit)))
    start = max(0, int(offset))
    changes: list[dict[str, Any]] = []
    if row.status == "SUCCEEDED" and row.generated_file_object_id and row.diff_sha256:
        artifact = _load_derived_json(
            db,
            file_object_id=int(row.generated_file_object_id),
            expected_sha256=str(row.diff_sha256),
        )
        changes = list(artifact.get("changes") or [])
    return {
        "compareResultId": str(row.id),
        "status": row.status,
        "left": {"fileVersionId": str(row.left_file_version_id), "sourceSha256": row.left_source_sha256},
        "right": {"fileVersionId": str(row.right_file_version_id), "sourceSha256": row.right_source_sha256},
        "algorithmCode": row.algorithm_code,
        "algorithmVersion": row.algorithm_version,
        "summary": row.summary_json,
        "changes": changes[start:start + size],
        "nextOffset": start + size if start + size < len(changes) else None,
    }
