"""Bounded worker for credential-free PLAT-C extraction and comparison jobs.

The request path authorizes the actor and pins immutable source identity.  The worker
uses internal storage access only, rechecks version/object/SHA/size before reading bytes,
and writes the full extracted body or diff to a generated ``FileObject``.  It never
writes FileAsset/FileVersion/source FileBinding current truth.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy import or_, select

from app.core.context import current_tenant_id, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.file import FileAsset, FileJob, FileObject, FileVersion
from app.modules.platform.document_lifecycle.file_job_dag import (
    COMPARE_ALGORITHM,
    COMPARE_ALGORITHM_VERSION,
    EXTRACTOR_CODE,
    EXTRACTOR_VERSION,
    _assert_credential_free,
)
from app.modules.platform.document_lifecycle.models import (
    DocumentCompareResult,
    FileDerivedArtifact,
)
from app.modules.platform.document_lifecycle.paragraph_page_compare import compare_documents
from app.modules.platform.document_lifecycle.safe_text_parser import ParserBudgets, extract_text
from app.services import file_service
from app.services.storage import get_backend

JOB_TYPES = ("DOCUMENT_EXTRACT", "DOCUMENT_COMPARE")
PENDING_STATES = ("PENDING", "RETRY")
LOCK_STALE_AFTER = timedelta(minutes=10)
RETRY_BASE_SECONDS = 30

_SENSITIVITY_RANK = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "NORMAL": 1,
    "PERSONAL": 2,
    "SENSITIVE": 3,
    "HIGHLY_SENSITIVE": 4,
}


def _normalize_sensitivity(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    return normalized if normalized in _SENSITIVITY_RANK else "HIGHLY_SENSITIVE"


@dataclass(frozen=True, slots=True)
class WorkerSource:
    tenant_id: int
    asset_id: int
    file_version_id: int
    file_object_id: int
    source_sha256: str
    mime_type: str | None
    ext: str | None
    size_bytes: int
    sensitivity_level: str
    retention_until: datetime | None
    legal_hold: bool
    data: bytes


def _now() -> datetime:
    return datetime.utcnow()


def _fail(code: str, message: str) -> AppException:
    return AppException(code, message, http_status=422)


def _payload_int(payload: dict[str, Any], key: str) -> int:
    try:
        value = int(payload[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise _fail("DOCUMENT_SOURCE_IDENTITY_INVALID", "派生任务源身份不完整") from exc
    if value <= 0:
        raise _fail("DOCUMENT_SOURCE_IDENTITY_INVALID", "派生任务源身份不完整")
    return value


def load_pinned_source(db, *, tenant_id: int, payload: dict[str, Any],
                       budgets: ParserBudgets | None = None) -> WorkerSource:
    """Recheck the immutable relation and bytes without carrying request credentials."""
    limits = budgets or ParserBudgets()
    version_id = _payload_int(payload, "file_version_id")
    object_id = _payload_int(payload, "file_object_id")
    asset_id = _payload_int(payload, "asset_id")
    expected_sha = str(payload.get("source_sha256") or "").strip().lower()
    if len(expected_sha) != 64 or any(ch not in "0123456789abcdef" for ch in expected_sha):
        raise _fail("DOCUMENT_SOURCE_IDENTITY_INVALID", "派生任务源 SHA 不正确")

    row = db.execute(
        select(FileVersion, FileAsset, FileObject)
        .join(FileAsset, (FileAsset.id == FileVersion.asset_id)
              & (FileAsset.tenant_id == FileVersion.tenant_id)
              & FileAsset.is_deleted.is_(False))
        .join(FileObject, (FileObject.id == FileVersion.file_object_id)
              & (FileObject.tenant_id == FileVersion.tenant_id)
              & FileObject.is_deleted.is_(False))
        .where(
            FileVersion.tenant_id == tenant_id,
            FileVersion.id == version_id,
            FileVersion.asset_id == asset_id,
            FileVersion.file_object_id == object_id,
            FileVersion.is_deleted.is_(False),
        )
        .limit(1)
    ).first()
    if row is None:
        raise _fail("DOCUMENT_SOURCE_CHANGED", "源文件版本关系已变化")
    version, asset, file_object = row
    actual_sha = str(file_object.sha256 or "").strip().lower()
    if not hmac.compare_digest(actual_sha, expected_sha):
        raise _fail("DOCUMENT_SOURCE_CHANGED", "源文件 SHA 已变化")
    pinned_size = int(payload.get("size_bytes") or 0)
    actual_size = int(file_object.size_bytes or 0)
    if pinned_size < 0 or pinned_size != actual_size or actual_size > limits.max_source_bytes:
        raise _fail("DOCUMENT_SOURCE_CHANGED", "源文件大小与任务快照不一致")

    key = str(file_object.object_key or file_object.file_key or "").strip()
    path = get_backend().fetch_local(key) if key else None
    if path is None or not path.is_file():
        raise _fail("DOCUMENT_SOURCE_MISSING", "源文件存储对象不存在")
    with path.open("rb") as stream:
        data = stream.read(limits.max_source_bytes + 1)
    if len(data) > limits.max_source_bytes or len(data) != actual_size:
        raise _fail("DOCUMENT_SOURCE_CHANGED", "源文件实际大小与任务快照不一致")
    if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), expected_sha):
        raise _fail("DOCUMENT_SOURCE_CHANGED", "源文件实际内容与任务快照不一致")

    sensitivity = _normalize_sensitivity(
        asset.sensitivity_level or file_object.security_level or "PERSONAL"
    )
    return WorkerSource(
        tenant_id=tenant_id,
        asset_id=int(version.asset_id),
        file_version_id=int(version.id),
        file_object_id=int(file_object.id),
        source_sha256=expected_sha,
        mime_type=file_object.mime_type,
        ext=file_object.ext,
        size_bytes=actual_size,
        sensitivity_level=sensitivity,
        retention_until=file_object.retention_until,
        legal_hold=bool(file_object.legal_hold),
        data=data,
    )


def _max_sensitivity(*sources: WorkerSource) -> str:
    return max(
        (_normalize_sensitivity(source.sensitivity_level) for source in sources),
        key=lambda value: _SENSITIVITY_RANK[value],
    )


def _max_retention(*sources: WorkerSource) -> datetime | None:
    values = [source.retention_until for source in sources if source.retention_until is not None]
    return max(values) if values else None


def _store_artifact_bytes(db, *, data: bytes, filename: str, sensitivity: str) -> FileObject:
    meta = file_service.store_bytes(
        data,
        filename,
        "DOCUMENT_DERIVATIVE",
        "text/plain",
        biz_id=None,
        user={},
        visibility="PRIVATE",
        security_level=sensitivity,
        db=db,
    )
    file_id = int(meta["fileId"])
    row = db.scalars(select(FileObject).where(
        FileObject.id == file_id,
        FileObject.tenant_id == int(current_tenant_id() or 0),
        FileObject.is_deleted.is_(False),
    )).one()
    return row


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _execute_extract(db, job: FileJob, payload: dict[str, Any],
                     artifact_writer: Callable[..., FileObject]) -> dict[str, Any]:
    if payload.get("contract") != "PLAT_C_DOCUMENT_EXTRACT_V1" \
            or payload.get("extractorCode") != EXTRACTOR_CODE \
            or payload.get("extractorVersion") != EXTRACTOR_VERSION:
        raise _fail("DOCUMENT_JOB_CONTRACT_INVALID", "文档抽取任务版本不受支持")
    source = load_pinned_source(db, tenant_id=int(job.tenant_id), payload=dict(payload.get("source") or {}))
    existing = db.scalars(select(FileDerivedArtifact).where(
        FileDerivedArtifact.tenant_id == int(job.tenant_id),
        FileDerivedArtifact.source_file_version_id == source.file_version_id,
        FileDerivedArtifact.source_sha256 == source.source_sha256,
        FileDerivedArtifact.derivative_kind == "EXTRACTED_TEXT",
        FileDerivedArtifact.extractor_code == EXTRACTOR_CODE,
        FileDerivedArtifact.extractor_version == EXTRACTOR_VERSION,
    ).limit(1)).first()
    if existing is not None and existing.status == "SUCCEEDED":
        return {"artifactId": str(existing.id), "deduped": True}

    document = extract_text(source.data, ext=source.ext, mime_type=source.mime_type)
    body = _json_bytes({
        "contract": "PLAT_C_EXTRACTED_ARTIFACT_V1",
        "extractorCode": EXTRACTOR_CODE,
        "extractorVersion": EXTRACTOR_VERSION,
        "source": {
            "fileVersionId": str(source.file_version_id),
            "sourceSha256": source.source_sha256,
        },
        "document": asdict(document),
    })
    generated = artifact_writer(
        db, data=body, filename=f"plat-c-extracted-{source.file_version_id}.txt",
        sensitivity=source.sensitivity_level,
    )
    row = existing or FileDerivedArtifact(
        tenant_id=int(job.tenant_id),
        source_file_version_id=source.file_version_id,
        source_sha256=source.source_sha256,
        derivative_kind="EXTRACTED_TEXT",
        extractor_code=EXTRACTOR_CODE,
        extractor_version=EXTRACTOR_VERSION,
        sensitivity_level=source.sensitivity_level,
    )
    if existing is None:
        db.add(row)
    row.generated_file_object_id = int(generated.id)
    row.content_sha256 = hashlib.sha256(body).hexdigest()
    row.block_count = len(document.blocks)
    row.status = "SUCCEEDED"
    row.error_code = None
    row.error_message = None
    row.retention_until = source.retention_until
    row.legal_hold = source.legal_hold
    db.flush()
    return {"artifactId": str(row.id), "blockCount": row.block_count, "deduped": False}


def _execute_compare(db, job: FileJob, payload: dict[str, Any],
                     artifact_writer: Callable[..., FileObject]) -> dict[str, Any]:
    if payload.get("contract") != "PLAT_C_DOCUMENT_COMPARE_V1" \
            or payload.get("algorithmCode") != COMPARE_ALGORITHM \
            or payload.get("algorithmVersion") != COMPARE_ALGORITHM_VERSION:
        raise _fail("DOCUMENT_JOB_CONTRACT_INVALID", "文档比较任务版本不受支持")
    left = load_pinned_source(db, tenant_id=int(job.tenant_id), payload=dict(payload.get("left") or {}))
    right = load_pinned_source(db, tenant_id=int(job.tenant_id), payload=dict(payload.get("right") or {}))
    existing = db.scalars(select(DocumentCompareResult).where(
        DocumentCompareResult.tenant_id == int(job.tenant_id),
        DocumentCompareResult.left_file_version_id == left.file_version_id,
        DocumentCompareResult.left_source_sha256 == left.source_sha256,
        DocumentCompareResult.right_file_version_id == right.file_version_id,
        DocumentCompareResult.right_source_sha256 == right.source_sha256,
        DocumentCompareResult.algorithm_code == COMPARE_ALGORITHM,
        DocumentCompareResult.algorithm_version == COMPARE_ALGORITHM_VERSION,
    ).limit(1)).first()
    if existing is not None and existing.status == "SUCCEEDED":
        return {"compareResultId": str(existing.id), "summary": existing.summary_json, "deduped": True}

    comparison = compare_documents(
        extract_text(left.data, ext=left.ext, mime_type=left.mime_type),
        extract_text(right.data, ext=right.ext, mime_type=right.mime_type),
    )
    body = _json_bytes({
        "contract": "PLAT_C_DOCUMENT_COMPARE_ARTIFACT_V1",
        "algorithmCode": comparison.algorithm_code,
        "algorithmVersion": comparison.algorithm_version,
        "left": {"fileVersionId": str(left.file_version_id), "sourceSha256": left.source_sha256},
        "right": {"fileVersionId": str(right.file_version_id), "sourceSha256": right.source_sha256},
        "changes": [asdict(change) for change in comparison.changes],
    })
    sensitivity = _max_sensitivity(left, right)
    generated = artifact_writer(
        db, data=body,
        filename=f"plat-c-compare-{left.file_version_id}-{right.file_version_id}.txt",
        sensitivity=sensitivity,
    )
    summary = {
        "unchanged": comparison.unchanged,
        "added": comparison.added,
        "removed": comparison.removed,
        "modified": comparison.modified,
    }
    row = existing or DocumentCompareResult(
        tenant_id=int(job.tenant_id),
        left_file_version_id=left.file_version_id,
        left_source_sha256=left.source_sha256,
        right_file_version_id=right.file_version_id,
        right_source_sha256=right.source_sha256,
        algorithm_code=COMPARE_ALGORITHM,
        algorithm_version=COMPARE_ALGORITHM_VERSION,
        sensitivity_level=sensitivity,
    )
    if existing is None:
        db.add(row)
    row.generated_file_object_id = int(generated.id)
    row.diff_sha256 = hashlib.sha256(body).hexdigest()
    row.summary_json = summary
    row.status = "SUCCEEDED"
    row.error_code = None
    row.error_message = None
    row.retention_until = _max_retention(left, right)
    row.legal_hold = left.legal_hold or right.legal_hold
    db.flush()
    return {"compareResultId": str(row.id), "summary": summary, "deduped": False}


def claim_next_job(worker_id: str) -> int | None:
    now = _now()
    db = get_sessionmaker()()
    try:
        row = db.scalars(
            select(FileJob)
            .where(
                FileJob.job_type.in_(JOB_TYPES),
                FileJob.is_deleted.is_(False),
                FileJob.available_at <= now,
                or_(
                    FileJob.status.in_(PENDING_STATES),
                    (FileJob.status == "RUNNING") & (FileJob.locked_at < now - LOCK_STALE_AFTER),
                ),
            )
            .order_by(FileJob.available_at, FileJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()
        if row is None:
            db.rollback()
            return None
        row.status = "RUNNING"
        row.attempts = int(row.attempts or 0) + 1
        row.locked_at = now
        row.locked_by = worker_id[:120]
        row.last_error = None
        db.commit()
        return int(row.id)
    finally:
        db.close()


def complete_job(job_id: int, *, artifact_writer: Callable[..., FileObject] | None = None) -> dict[str, Any]:
    db = get_sessionmaker()()
    previous_tenant = current_tenant_id()
    try:
        job = db.get(FileJob, int(job_id))
        if job is None or job.status != "RUNNING" or job.job_type not in JOB_TYPES:
            return {"processed": False, "reason": "job-not-running"}
        set_tenant(int(job.tenant_id))
        payload = dict(job.payload_json or {})
        _assert_credential_free(payload)
        writer = artifact_writer or _store_artifact_bytes
        if job.job_type == "DOCUMENT_EXTRACT":
            result = _execute_extract(db, job, payload, writer)
        else:
            result = _execute_compare(db, job, payload, writer)
        job.status = "SUCCEEDED"
        job.result_json = result
        job.last_error = None
        job.locked_at = None
        job.locked_by = None
        db.commit()
        return {"processed": True, "jobStatus": job.status, **result}
    except Exception as exc:  # worker must persist a bounded failure and retry state
        db.rollback()
        job = db.get(FileJob, int(job_id))
        if job is None:
            return {"processed": False, "reason": "job-missing"}
        exhausted = int(job.attempts or 0) >= int(job.max_attempts or 1)
        job.status = "DEAD" if exhausted else "RETRY"
        job.available_at = _now() + timedelta(
            seconds=min(3600, RETRY_BASE_SECONDS * (2 ** max(0, int(job.attempts or 1) - 1)))
        )
        job.last_error = f"{exc.__class__.__name__}: {exc}"[:4000]
        job.result_json = {"errorCode": getattr(exc, "code", exc.__class__.__name__)[:80]}
        job.locked_at = None
        job.locked_by = None
        db.commit()
        return {"processed": True, "jobStatus": job.status, "errorCode": job.result_json["errorCode"]}
    finally:
        db.close()
        set_tenant(previous_tenant)


def process_next_job(worker_id: str | None = None) -> dict[str, Any]:
    identity = worker_id or f"{socket.gethostname()}:{id(worker_id)}"
    job_id = claim_next_job(identity)
    if job_id is None:
        return {"processed": False, "reason": "empty"}
    return complete_job(job_id)
