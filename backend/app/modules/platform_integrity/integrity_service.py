"""Bounded, read-only integrity detectors and federated exception projection."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from contextvars import copy_context
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import case, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, not_found
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileBinding, FileObject, FileVersion
from app.models.platform_integrity import IntegrityException
from app.modules.platform_integrity.frozen_package_service import PACKAGE_BIZ_TYPE
from app.modules.platform_integrity.manifest_digest import (
    PLATFORM_BUSINESS_SNAPSHOT,
    platform_manifest_digest,
)
from app.modules.platform_integrity.probe_registry import ProbeRequest, get_integrity_probe
from app.services.db_service import _tid, session
from app.services.storage import get_backend

FROZEN_MANIFEST_ITEM_DRIFT = "FROZEN_MANIFEST_ITEM_DRIFT"
PACKAGED_FILE_MISSING = "PACKAGED_FILE_MISSING"
PACKAGE_SOURCE_VERSION_MISMATCH = "PACKAGE_SOURCE_VERSION_MISMATCH"
FILE_BINDING_BROKEN_REFERENCE = "FILE_BINDING_BROKEN_REFERENCE"
MANIFEST_ITEM_LIMIT_EXCEEDED = "MANIFEST_ITEM_LIMIT_EXCEEDED"
ALLOWED_STATUSES = frozenset({"OPEN", "ACKNOWLEDGED", "RESOLVED", "IGNORED"})
MAX_PAGE_SIZE = 200
MAX_ITEMS_PER_MANIFEST = 1000
MAX_DEEP_SHA_PER_PAGE = 20
_PROBE_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="integrity-probe")


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    exception_type: str
    detector_code: str
    module_code: str | None
    subject_type: str
    subject_id: str
    title: str
    message: str
    severity: str = "HIGH"
    manifest_id: int | None = None
    file_id: int | None = None
    evidence: dict = field(default_factory=dict)
    detector_version: str = "V1"


@dataclass(frozen=True, slots=True)
class DetectorPage:
    detector_code: str
    status: str
    findings: tuple[IntegrityFinding, ...]
    next_cursor: int | None
    scanned: int
    deep_sha_scanned: int = 0
    error: str | None = None


def _bounded_limit(value: int) -> int:
    return max(1, min(int(value or 100), MAX_PAGE_SIZE))


def _cursor_before(value) -> int:
    try:
        return max(0, int(value or 1) - 1)
    except (TypeError, ValueError):
        return 0


def _fingerprint_payload(finding: IntegrityFinding) -> dict:
    return {
        "exceptionType": finding.exception_type,
        "detectorCode": finding.detector_code,
        "moduleCode": finding.module_code or "",
        "subjectType": finding.subject_type,
        "subjectId": finding.subject_id,
        "manifestId": int(finding.manifest_id or 0),
        "fileId": int(finding.file_id or 0),
    }


def stable_fingerprint(finding: IntegrityFinding) -> str:
    body = json.dumps(_fingerprint_payload(finding), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _sha256_path(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as reader:
        while True:
            chunk = reader.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _finding(
    exception_type: str,
    manifest: ArchiveManifest,
    *,
    item: ArchiveManifestItem | None = None,
    message: str,
    evidence: dict | None = None,
    severity: str = "HIGH",
) -> IntegrityFinding:
    return IntegrityFinding(
        exception_type=exception_type,
        detector_code="FROZEN_MANIFEST_V1",
        module_code=str(manifest.module_code or ""),
        subject_type="ARCHIVE_MANIFEST",
        subject_id=str(manifest.id),
        manifest_id=int(manifest.id),
        file_id=int(item.file_object_id) if item else None,
        title=exception_type,
        message=message,
        severity=severity,
        evidence={
            "manifestId": str(manifest.id),
            "materialCode": str(item.material_code) if item else "",
            "versionId": str(item.version_id) if item else "",
            "fileObjectId": str(item.file_object_id) if item else "",
            **(evidence or {}),
        },
    )


def scan_frozen_manifest_page(
    db,
    *,
    tenant_id: int,
    after_id: int = 0,
    limit: int = 100,
    deep_sha: bool = False,
    deep_sha_limit: int = MAX_DEEP_SHA_PER_PAGE,
) -> DetectorPage:
    """Keyset scan new platform manifests; every per-manifest read is explicitly bounded."""
    if int(tenant_id) != _tid():
        raise AppException("TENANT_SCOPE_MISMATCH", "探测租户与请求上下文不一致", http_status=409)
    page_size = _bounded_limit(limit)
    has_snapshot = select(ArchiveManifestItem.id).where(
            ArchiveManifestItem.tenant_id == ArchiveManifest.tenant_id,
            ArchiveManifestItem.manifest_id == ArchiveManifest.id,
            ArchiveManifestItem.material_code == PLATFORM_BUSINESS_SNAPSHOT,
            ArchiveManifestItem.is_deleted.is_(False),
        ).exists()
    manifests = list(db.scalars(
        select(ArchiveManifest)
        .where(
            ArchiveManifest.tenant_id == int(tenant_id),
            ArchiveManifest.id > int(after_id or 0),
            ArchiveManifest.is_deleted.is_(False),
            has_snapshot,
        )
        .order_by(ArchiveManifest.id)
        .limit(page_size)
    ).all())
    findings: list[IntegrityFinding] = []
    backend = get_backend()
    deep_budget = min(MAX_DEEP_SHA_PER_PAGE, max(0, int(deep_sha_limit))) if deep_sha else 0
    deep_scanned = 0
    for manifest in manifests:
        items = list(db.scalars(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == int(tenant_id),
            ArchiveManifestItem.manifest_id == int(manifest.id),
            ArchiveManifestItem.is_deleted.is_(False),
        ).order_by(
            ArchiveManifestItem.sort_no,
            ArchiveManifestItem.material_code,
            ArchiveManifestItem.version_id,
            ArchiveManifestItem.id,
        ).limit(MAX_ITEMS_PER_MANIFEST + 1)).all())
        if len(items) > MAX_ITEMS_PER_MANIFEST:
            findings.append(_finding(
                MANIFEST_ITEM_LIMIT_EXCEEDED,
                manifest,
                message=f"冻结清单材料数超过单清单安全上限 {MAX_ITEMS_PER_MANIFEST}",
                evidence={"observedAtLeast": MAX_ITEMS_PER_MANIFEST + 1},
            ))
            continue
        if platform_manifest_digest(manifest, items) != str(manifest.manifest_sha256 or "").lower():
            findings.append(_finding(FROZEN_MANIFEST_ITEM_DRIFT, manifest, message="冻结清单摘要与固定字段不一致"))
        version_ids = {int(item.version_id) for item in items}
        object_ids = {int(item.file_object_id) for item in items}
        versions = {int(row.id): row for row in db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == int(tenant_id),
            FileVersion.id.in_(version_ids or {-1}),
            FileVersion.is_deleted.is_(False),
        ).limit(MAX_ITEMS_PER_MANIFEST)).all()}
        objects = {int(row.id): row for row in db.scalars(select(FileObject).where(
            FileObject.tenant_id == int(tenant_id),
            FileObject.id.in_(object_ids or {-1}),
            FileObject.is_deleted.is_(False),
        ).limit(MAX_ITEMS_PER_MANIFEST)).all()}
        for item in items:
            version = versions.get(int(item.version_id))
            file_obj = objects.get(int(item.file_object_id))
            if not version or int(version.file_object_id) != int(item.file_object_id):
                findings.append(_finding(
                    PACKAGE_SOURCE_VERSION_MISMATCH,
                    manifest,
                    item=item,
                    message="清单引用的 FileVersion 不存在或不再指向固定 FileObject",
                ))
                continue
            if not file_obj:
                findings.append(_finding(
                    FILE_BINDING_BROKEN_REFERENCE,
                    manifest,
                    item=item,
                    message="清单引用的 FileObject 不存在",
                    severity="CRITICAL",
                ))
                continue
            metadata_matches = (
                int(file_obj.size_bytes or 0) == int(item.size_snapshot or 0)
                and str(file_obj.sha256 or "").lower() == str(item.sha256_snapshot or "").lower()
            )
            if not metadata_matches:
                findings.append(_finding(
                    FROZEN_MANIFEST_ITEM_DRIFT,
                    manifest,
                    item=item,
                    message="清单固定的文件大小或摘要与 FileObject 投影不一致",
                ))
                continue
            storage_key = str(file_obj.object_key or file_obj.file_key)
            if not backend.exists(storage_key):
                findings.append(_finding(
                    PACKAGED_FILE_MISSING,
                    manifest,
                    item=item,
                    message="清单引用的物理文件不存在",
                    severity="CRITICAL",
                ))
                continue
            if deep_scanned < deep_budget:
                deep_scanned += 1
                local_path = backend.fetch_local(storage_key)
                if local_path is None:
                    findings.append(_finding(
                        PACKAGED_FILE_MISSING,
                        manifest,
                        item=item,
                        message="深度校验无法读取物理文件",
                        severity="CRITICAL",
                    ))
                else:
                    actual_size, actual_sha = _sha256_path(local_path)
                    if actual_size != int(item.size_snapshot or 0) or actual_sha != str(item.sha256_snapshot or "").lower():
                        findings.append(_finding(
                            FROZEN_MANIFEST_ITEM_DRIFT,
                            manifest,
                            item=item,
                            message="深度 SHA-256 与冻结清单不一致",
                            evidence={"deepShaChecked": True},
                        ))
        artifacts = list(db.scalars(select(FileObject).where(
            FileObject.tenant_id == int(tenant_id),
            FileObject.biz_type == PACKAGE_BIZ_TYPE,
            FileObject.biz_id.like(f"m{manifest.id}:r{manifest.revision}:%"),
            FileObject.is_deleted.is_(False),
        ).order_by(FileObject.id.desc()).limit(2)).all())
        for artifact in artifacts:
            if not backend.exists(str(artifact.object_key or artifact.file_key)):
                findings.append(IntegrityFinding(
                    exception_type=PACKAGED_FILE_MISSING,
                    detector_code="FROZEN_MANIFEST_V1",
                    module_code=str(manifest.module_code or ""),
                    subject_type="PACKAGE_ARTIFACT",
                    subject_id=str(artifact.id),
                    manifest_id=int(manifest.id),
                    file_id=int(artifact.id),
                    title=PACKAGED_FILE_MISSING,
                    message="已登记的冻结证据包物理文件不存在",
                    severity="CRITICAL",
                    evidence={"manifestId": str(manifest.id), "fileId": str(artifact.id)},
                ))
    next_cursor = int(manifests[-1].id) if len(manifests) == page_size else None
    return DetectorPage(
        detector_code="FROZEN_MANIFEST_V1",
        status="CONCLUSIVE",
        findings=tuple(findings),
        next_cursor=next_cursor,
        scanned=len(manifests),
        deep_sha_scanned=deep_scanned,
    )


def scan_file_binding_page(
    db,
    *,
    tenant_id: int,
    after_id: int = 0,
    limit: int = 100,
) -> DetectorPage:
    if int(tenant_id) != _tid():
        raise AppException("TENANT_SCOPE_MISMATCH", "探测租户与请求上下文不一致", http_status=409)
    page_size = _bounded_limit(limit)
    bindings = list(db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == int(tenant_id),
        FileBinding.id > int(after_id or 0),
        FileBinding.is_deleted.is_(False),
    ).order_by(FileBinding.id).limit(page_size)).all())
    file_ids = {int(row.file_id) for row in bindings}
    existing_ids = set(db.scalars(select(FileObject.id).where(
        FileObject.tenant_id == int(tenant_id),
        FileObject.id.in_(file_ids or {-1}),
        FileObject.is_deleted.is_(False),
    ).limit(page_size)).all())
    findings = tuple(IntegrityFinding(
        exception_type=FILE_BINDING_BROKEN_REFERENCE,
        detector_code="FILE_BINDING_REFERENCE_V1",
        module_code=str(binding.module_code or "") or None,
        subject_type="FILE_BINDING",
        subject_id=str(binding.id),
        file_id=int(binding.file_id),
        title=FILE_BINDING_BROKEN_REFERENCE,
        message="FileBinding 引用的 FileObject 不存在",
        severity="MEDIUM",
        evidence={"bindingId": str(binding.id), "fileId": str(binding.file_id)},
    ) for binding in bindings if int(binding.file_id) not in existing_ids)
    return DetectorPage(
        detector_code="FILE_BINDING_REFERENCE_V1",
        status="CONCLUSIVE",
        findings=findings,
        next_cursor=int(bindings[-1].id) if len(bindings) == page_size else None,
        scanned=len(bindings),
    )


def run_registered_probe(
    code: str,
    *,
    tenant_id: int,
    after_id: int = 0,
    limit: int = 100,
    timeout_ms: int = 2000,
) -> DetectorPage:
    """Invoke only a domain-registered probe; failures remain explicitly inconclusive."""
    if int(tenant_id) != _tid():
        raise AppException("TENANT_SCOPE_MISMATCH", "探测租户与请求上下文不一致", http_status=409)
    probe = get_integrity_probe(code)
    if probe is None:
        return DetectorPage(
            detector_code=str(code or "").upper(),
            status="INCONCLUSIVE",
            findings=(),
            next_cursor=None,
            scanned=0,
            error="PROBE_NOT_REGISTERED",
        )
    request = ProbeRequest(
        tenant_id=int(tenant_id),
        after_id=max(0, int(after_id or 0)),
        limit=_bounded_limit(limit),
        timeout_ms=max(100, min(int(timeout_ms or 2000), 5000)),
    )
    context = copy_context()
    future = _PROBE_EXECUTOR.submit(context.run, probe, request)
    try:
        result = future.result(timeout=request.timeout_ms / 1000)
        if not isinstance(result, DetectorPage):
            raise TypeError("registered probe must return DetectorPage")
        return result
    except FutureTimeoutError:
        future.cancel()
        return DetectorPage(
            detector_code=str(code or "").upper(),
            status="INCONCLUSIVE",
            findings=(),
            next_cursor=None,
            scanned=0,
            error="PROBE_TIMEOUT",
        )
    except Exception as exc:
        return DetectorPage(
            detector_code=str(code or "").upper(),
            status="INCONCLUSIVE",
            findings=(),
            next_cursor=None,
            scanned=0,
            error=type(exc).__name__,
        )


def record_detector_page(db, page: DetectorPage, *, detected_at: datetime | None = None) -> list[IntegrityException]:
    """Write only the federated read model. INCONCLUSIVE pages never create false positives."""
    if page.status != "CONCLUSIVE":
        return []
    tenant_id = _tid()
    now = detected_at or datetime.utcnow()
    rows: list[IntegrityException] = []
    for finding in page.findings:
        fingerprint = stable_fingerprint(finding)
        if db.get_bind().dialect.name == "mysql":
            _mysql_upsert_exception(db, tenant_id, fingerprint, finding, now)
            row = db.scalars(select(IntegrityException).where(
                IntegrityException.tenant_id == tenant_id,
                IntegrityException.fingerprint == fingerprint,
            ).with_for_update()).one()
            rows.append(row)
            continue
        lookup = select(IntegrityException).where(
            IntegrityException.tenant_id == tenant_id,
            IntegrityException.fingerprint == fingerprint,
            IntegrityException.is_deleted.is_(False),
        ).with_for_update()
        row = db.scalars(lookup).first()
        if row is None:
            row = IntegrityException(
                tenant_id=tenant_id,
                exception_type=finding.exception_type,
                fingerprint=fingerprint,
                status="OPEN",
                severity=finding.severity,
                detector_code=finding.detector_code,
                detector_version=finding.detector_version,
                module_code=finding.module_code,
                subject_type=finding.subject_type,
                subject_id=finding.subject_id,
                manifest_id=finding.manifest_id,
                file_id=finding.file_id,
                title=finding.title[:200],
                message=finding.message[:1000],
                evidence_json=finding.evidence,
                occurrence_count=1,
                first_detected_at=now,
                last_detected_at=now,
            )
            try:
                with db.begin_nested():
                    db.add(row)
                    db.flush()
            except IntegrityError:
                row = db.scalars(lookup).first()
                if row is None:
                    raise
                _refresh_exception(row, finding, now)
        else:
            _refresh_exception(row, finding, now)
        rows.append(row)
    db.flush()
    return rows


def _mysql_upsert_exception(
    db,
    tenant_id: int,
    fingerprint: str,
    finding: IntegrityFinding,
    now: datetime,
) -> None:
    """Use the declared unique fingerprint as the MySQL concurrency authority."""
    statement = mysql_insert(IntegrityException).values(
        tenant_id=tenant_id,
        exception_type=finding.exception_type,
        fingerprint=fingerprint,
        status="OPEN",
        severity=finding.severity,
        detector_code=finding.detector_code,
        detector_version=finding.detector_version,
        module_code=finding.module_code,
        subject_type=finding.subject_type,
        subject_id=finding.subject_id,
        manifest_id=finding.manifest_id,
        file_id=finding.file_id,
        title=finding.title[:200],
        message=finding.message[:1000],
        evidence_json=finding.evidence,
        occurrence_count=1,
        first_detected_at=now,
        last_detected_at=now,
        created_at=now,
        updated_at=now,
        is_deleted=False,
        version=0,
    )
    was_resolved = IntegrityException.status == "RESOLVED"
    statement = statement.on_duplicate_key_update(
        status=case((was_resolved, "OPEN"), else_=IntegrityException.status),
        severity=finding.severity,
        message=finding.message[:1000],
        evidence_json=finding.evidence,
        occurrence_count=IntegrityException.occurrence_count + 1,
        last_detected_at=now,
        resolved_at=case((was_resolved, None), else_=IntegrityException.resolved_at),
        resolved_by=case((was_resolved, None), else_=IntegrityException.resolved_by),
        resolution_note=case((was_resolved, None), else_=IntegrityException.resolution_note),
        is_deleted=False,
        updated_at=now,
        version=IntegrityException.version + 1,
    )
    db.execute(statement)


def _refresh_exception(row: IntegrityException, finding: IntegrityFinding, now: datetime) -> None:
    row.last_detected_at = now
    row.occurrence_count = int(row.occurrence_count or 0) + 1
    row.message = finding.message[:1000]
    row.evidence_json = finding.evidence
    row.severity = finding.severity
    if row.status == "RESOLVED":
        row.status = "OPEN"
        row.resolved_at = None
        row.resolved_by = None
        row.resolution_note = None
    row.version = int(row.version or 0) + 1


def list_integrity_exceptions(
    *,
    after_id: int = 0,
    limit: int = 50,
    status: str | None = None,
    module_code: str | None = None,
) -> dict:
    tenant_id = _tid()
    page_size = _bounded_limit(limit)
    filters = [
        IntegrityException.tenant_id == tenant_id,
        IntegrityException.id > int(after_id or 0),
        IntegrityException.is_deleted.is_(False),
    ]
    if status:
        normalized = str(status).upper()
        if normalized not in ALLOWED_STATUSES:
            raise AppException("VALIDATION_ERROR", "完整性异常状态不合法", http_status=422)
        filters.append(IntegrityException.status == normalized)
    if module_code:
        filters.append(IntegrityException.module_code == str(module_code).upper())
    with session() as db:
        rows = list(db.scalars(select(IntegrityException).where(*filters).order_by(
            IntegrityException.id,
        ).limit(page_size)).all())
        return {
            "items": [_view(row) for row in rows],
            "nextCursor": str(rows[-1].id) if len(rows) == page_size else None,
            "pageSize": page_size,
            "overview": _overview(db, tenant_id),
        }


def _overview(db, tenant_id: int) -> dict:
    active = (
        IntegrityException.tenant_id == tenant_id,
        IntegrityException.status.in_(("OPEN", "ACKNOWLEDGED")),
        IntegrityException.is_deleted.is_(False),
    )
    now = datetime.utcnow()

    def count(*extra) -> int:
        return int(db.scalar(select(func.count()).select_from(IntegrityException).where(*active, *extra)) or 0)

    modules = list(db.execute(select(
        func.coalesce(IntegrityException.module_code, "PLATFORM"),
        func.count(),
    ).where(*active).group_by(IntegrityException.module_code).order_by(func.count().desc()).limit(50)).all())
    return {
        "critical": count(IntegrityException.severity == "CRITICAL"),
        "high": count(IntegrityException.severity.in_(("HIGH", "ERROR"))),
        "medium": count(IntegrityException.severity.in_(("MEDIUM", "WARNING"))),
        "todayNew": count(IntegrityException.first_detected_at >= now.replace(hour=0, minute=0, second=0, microsecond=0)),
        "unresolved7d": count(IntegrityException.first_detected_at <= now - timedelta(days=7)),
        "byModule": [{"moduleCode": str(module), "count": int(total)} for module, total in modules],
    }


def recheck_integrity_exception(
    exception_id: int,
    *,
    expected_version: int,
    actor_id: int | None,
    timeout_ms: int = 2000,
) -> dict:
    """Re-run one bounded detector page and only update the exception projection."""
    tenant_id = _tid()
    with session() as db:
        row = db.scalars(select(IntegrityException).where(
            IntegrityException.tenant_id == tenant_id,
            IntegrityException.id == int(exception_id),
            IntegrityException.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("完整性异常不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "异常状态已变化，请刷新后重试", http_status=409)
        if row.detector_code == "FROZEN_MANIFEST_V1":
            page = scan_frozen_manifest_page(
                db,
                tenant_id=tenant_id,
                after_id=_cursor_before(row.manifest_id),
                limit=1,
                deep_sha=False,
            )
        elif row.detector_code == "FILE_BINDING_REFERENCE_V1":
            page = scan_file_binding_page(
                db,
                tenant_id=tenant_id,
                after_id=_cursor_before(row.subject_id),
                limit=1,
            )
        else:
            page = run_registered_probe(
                row.detector_code,
                tenant_id=tenant_id,
                after_id=_cursor_before(row.subject_id),
                limit=1,
                timeout_ms=timeout_ms,
            )
        if page.status == "CONCLUSIVE":
            record_detector_page(db, page)
            db.refresh(row)
            still_present = any(stable_fingerprint(finding) == row.fingerprint for finding in page.findings)
            if not still_present:
                row.status = "RESOLVED"
                row.resolved_at = datetime.utcnow()
                row.resolved_by = actor_id
                row.resolution_note = "RECHECK_CONCLUSIVE_CLEAR"
                row.version = int(row.version or 0) + 1
        db.commit()
        return {
            "probeStatus": page.status,
            "error": page.error,
            "findingCount": len(page.findings),
            "exception": _view(row),
        }


def transition_integrity_exception(
    exception_id: int,
    *,
    status: str,
    expected_version: int,
    actor_id: int | None,
    note: str | None = None,
) -> dict:
    tenant_id = _tid()
    normalized = str(status or "").upper()
    if normalized not in ALLOWED_STATUSES - {"OPEN"}:
        raise AppException("VALIDATION_ERROR", "仅允许确认、解决或忽略异常", http_status=422)
    now = datetime.utcnow()
    with session() as db:
        row = db.scalars(select(IntegrityException).where(
            IntegrityException.tenant_id == tenant_id,
            IntegrityException.id == int(exception_id),
            IntegrityException.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("完整性异常不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "异常状态已变化，请刷新后重试", http_status=409)
        row.status = normalized
        row.version = int(row.version or 0) + 1
        row.resolution_note = str(note or "").strip()[:4000] or None
        if normalized == "ACKNOWLEDGED":
            row.acknowledged_at = now
            row.acknowledged_by = actor_id
        elif normalized == "RESOLVED":
            row.resolved_at = now
            row.resolved_by = actor_id
        elif normalized == "IGNORED":
            row.ignored_at = now
            row.ignored_by = actor_id
        db.commit()
        return _view(row)


def _view(row: IntegrityException) -> dict:
    return {
        "id": str(row.id),
        "exceptionType": row.exception_type,
        "fingerprint": row.fingerprint,
        "status": row.status,
        "severity": row.severity,
        "detectorCode": row.detector_code,
        "moduleCode": row.module_code or "",
        "subjectType": row.subject_type,
        "subjectId": row.subject_id,
        "manifestId": str(row.manifest_id or ""),
        "fileId": str(row.file_id or ""),
        "title": row.title,
        "message": row.message or "",
        "evidence": row.evidence_json or {},
        "occurrenceCount": int(row.occurrence_count or 0),
        "firstDetectedAt": row.first_detected_at.isoformat(timespec="seconds") if row.first_detected_at else None,
        "lastDetectedAt": row.last_detected_at.isoformat(timespec="seconds") if row.last_detected_at else None,
        "version": int(row.version or 0),
        "target": _typed_target(row),
    }


def _typed_target(row: IntegrityException) -> dict | None:
    if str(row.module_code or "").upper() == "GRADUATION" and row.manifest_id:
        return {
            "type": "GRADUATION_ARCHIVE_MANIFEST",
            "routeName": "graduation-risk-archive",
            "routeParams": {},
            "query": {"panel": "archive", "manifestId": str(row.manifest_id)},
        }
    return None


__all__ = [
    "DetectorPage",
    "FILE_BINDING_BROKEN_REFERENCE",
    "FROZEN_MANIFEST_ITEM_DRIFT",
    "IntegrityFinding",
    "PACKAGED_FILE_MISSING",
    "PACKAGE_SOURCE_VERSION_MISMATCH",
    "list_integrity_exceptions",
    "record_detector_page",
    "recheck_integrity_exception",
    "run_registered_probe",
    "scan_file_binding_page",
    "scan_frozen_manifest_page",
    "stable_fingerprint",
    "transition_integrity_exception",
]
