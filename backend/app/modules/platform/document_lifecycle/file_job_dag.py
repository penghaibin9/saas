"""Credential-free FileJob request DAG for PLAT-C extraction and comparison."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.file import FileJob
from app.modules.platform.document_lifecycle.exact_file_version_read_port import (
    ExactFileVersionReadPort,
    ExactSourceVersion,
    IExactFileVersionReadPort,
)

EXTRACTOR_CODE = "SAFE_TEXT_LAYER"
EXTRACTOR_VERSION = "PARAGRAPH_PAGE_V1"
COMPARE_ALGORITHM = "PARAGRAPH_PAGE_V1"
COMPARE_ALGORITHM_VERSION = "1.0.0"

_FORBIDDEN_KEY_PARTS = (
    "authorization", "token", "cookie", "session", "password", "secret",
    "ticket", "presigned", "signedurl", "storageurl", "refresh",
)
_FORBIDDEN_VALUE_RE = re.compile(
    r"(?:^|\s)(?:bearer|basic)\s+\S+|"
    r"(?:[a-z][a-z0-9+.-]*:)?//|"
    r"(?:^|[;&\s])(?:access_token|refresh_token|sessionid|cookie|ticket)=",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PinnedSource:
    file_version_id: int
    file_object_id: int
    asset_id: int
    source_sha256: str
    mime_type: str | None
    ext: str | None
    size_bytes: int
    sensitivity_level: str


@dataclass(frozen=True, slots=True)
class DerivedJobSpec:
    job_type: str
    file_id: int
    dedupe_key: str
    payload: dict[str, Any]


def _pin(source: ExactSourceVersion) -> PinnedSource:
    return PinnedSource(
        file_version_id=source.file_version_id,
        file_object_id=source.file_object_id,
        asset_id=source.asset_id,
        source_sha256=source.source_sha256,
        mime_type=source.mime_type,
        ext=source.ext,
        size_bytes=source.size_bytes,
        sensitivity_level=source.sensitivity_level,
    )


def _canonical_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _assert_credential_free(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
            if any(part in normalized for part in _FORBIDDEN_KEY_PARTS):
                raise AppException("VALIDATION_ERROR", f"FileJob 禁止保存凭证字段: {path}.{key}")
            _assert_credential_free(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_credential_free(child, f"{path}[{index}]")
    elif isinstance(value, str) and _FORBIDDEN_VALUE_RE.search(value):
        raise AppException("VALIDATION_ERROR", f"FileJob 禁止保存凭证或临时 URL: {path}")


def prepare_extract_job(
    *,
    file_version_id: int,
    expected_sha256: str,
    user: dict,
    port: IExactFileVersionReadPort,
) -> DerivedJobSpec:
    source = _pin(port.resolve(
        file_version_id=file_version_id,
        expected_sha256=expected_sha256,
        action="extract",
        user=user,
    ))
    payload = {
        "contract": "PLAT_C_DOCUMENT_EXTRACT_V1",
        "source": asdict(source),
        "derivativeKind": "EXTRACTED_TEXT",
        "extractorCode": EXTRACTOR_CODE,
        "extractorVersion": EXTRACTOR_VERSION,
    }
    _assert_credential_free(payload)
    return DerivedJobSpec(
        job_type="DOCUMENT_EXTRACT",
        file_id=source.file_object_id,
        dedupe_key=f"doc-extract:{_canonical_hash(payload)}",
        payload=payload,
    )


def prepare_compare_job(
    *,
    left_file_version_id: int,
    left_expected_sha256: str,
    right_file_version_id: int,
    right_expected_sha256: str,
    user: dict,
    port: IExactFileVersionReadPort,
) -> DerivedJobSpec:
    left = _pin(port.resolve(
        file_version_id=left_file_version_id,
        expected_sha256=left_expected_sha256,
        action="compare",
        user=user,
    ))
    right = _pin(port.resolve(
        file_version_id=right_file_version_id,
        expected_sha256=right_expected_sha256,
        action="compare",
        user=user,
    ))
    payload = {
        "contract": "PLAT_C_DOCUMENT_COMPARE_V1",
        "left": asdict(left),
        "right": asdict(right),
        "algorithmCode": COMPARE_ALGORITHM,
        "algorithmVersion": COMPARE_ALGORITHM_VERSION,
    }
    _assert_credential_free(payload)
    return DerivedJobSpec(
        job_type="DOCUMENT_COMPARE",
        file_id=left.file_object_id,
        dedupe_key=f"doc-compare:{_canonical_hash(payload)}",
        payload=payload,
    )


def _tenant_id() -> int:
    raw = str(current_tenant_id() or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return int(raw)


def persist_job_spec(db, spec: DerivedJobSpec, *, tenant_id: int) -> FileJob:
    existing = db.scalars(select(FileJob).where(
        FileJob.tenant_id == tenant_id,
        FileJob.dedupe_key == spec.dedupe_key,
    ).limit(1)).first()
    if existing is not None:
        return existing

    nested = db.begin_nested()
    try:
        row = FileJob(
            tenant_id=tenant_id,
            job_type=spec.job_type,
            file_id=spec.file_id,
            dedupe_key=spec.dedupe_key,
            status="PENDING",
            max_attempts=3,
            payload_json=spec.payload,
        )
        db.add(row)
        db.flush()
        nested.commit()
        return row
    except IntegrityError:
        nested.rollback()
        existing = db.scalars(select(FileJob).where(
            FileJob.tenant_id == tenant_id,
            FileJob.dedupe_key == spec.dedupe_key,
        ).limit(1)).first()
        if existing is None:
            raise
        return existing


def enqueue_extract(*, file_version_id: int, expected_sha256: str, user: dict) -> FileJob:
    spec = prepare_extract_job(
        file_version_id=file_version_id,
        expected_sha256=expected_sha256,
        user=user,
        port=ExactFileVersionReadPort(),
    )
    return _persist_owned(spec)


def enqueue_compare(
    *,
    left_file_version_id: int,
    left_expected_sha256: str,
    right_file_version_id: int,
    right_expected_sha256: str,
    user: dict,
) -> FileJob:
    spec = prepare_compare_job(
        left_file_version_id=left_file_version_id,
        left_expected_sha256=left_expected_sha256,
        right_file_version_id=right_file_version_id,
        right_expected_sha256=right_expected_sha256,
        user=user,
        port=ExactFileVersionReadPort(),
    )
    return _persist_owned(spec)


def _persist_owned(spec: DerivedJobSpec) -> FileJob:
    db = get_sessionmaker()()
    try:
        row = persist_job_spec(db, spec, tenant_id=_tenant_id())
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
