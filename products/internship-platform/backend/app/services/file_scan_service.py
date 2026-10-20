"""Durable standalone file scanning, using the existing FileJob/FileScanRecord contract.

Scan bytes outside database locks. An attempt token fences stale consumers; completion,
file readiness, scan evidence and the audit outbox commit in the same transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import exists, or_, select

from app.core.context import get_tenant, set_tenant
from app.db.session import get_sessionmaker
from app.models.file import FileJob, FileObject, FileScanRecord
from app.services.clamav_client import ClamAVClient, ClamAVError, ClamAVUnavailable
from app.services.file_scan_config import get_file_scan_config
from app.services.storage import get_backend


@dataclass(frozen=True)
class Claim:
    job_id: int
    tenant_id: int
    file_id: int
    attempt: int
    token: str
    file_key: str | None
    digest: str | None
    size: int | None
    started_at: datetime


def enqueue_file_scan(db, row):
    """Call only inside the upload transaction, after its file row is flushed."""
    if not row.scan_required:
        return
    job = db.scalar(select(FileJob).where(
        FileJob.tenant_id == row.tenant_id, FileJob.dedupe_key == f'FILE_SCAN:{row.id}'))
    if job is None:
        db.add(FileJob(tenant_id=row.tenant_id, file_id=row.id, job_type='FILE_SCAN',
                       dedupe_key=f'FILE_SCAN:{row.id}', status='PENDING', attempts=0,
                       max_attempts=get_file_scan_config().max_attempts,
                       # MySQL DATETIME(0) rounds fractional seconds; enqueue must be due now.
                       available_at=datetime.utcnow().replace(microsecond=0)))
    row.storage_zone = 'QUARANTINE'


def reconcile_pending_uploads(limit=100):
    """Recover pre-worker uploads; never reset an existing dead or completed job."""
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('scan reconciliation limit must be in 1..1000')
    with get_sessionmaker()() as db:
        rows = db.scalars(select(FileObject).where(
            FileObject.scan_required.is_(True), FileObject.is_deleted.is_(False),
            FileObject.status == 'QUARANTINED', FileObject.scan_status == 'PENDING',
            ~exists(select(FileJob.id).where(
                FileJob.tenant_id == FileObject.tenant_id,
                FileJob.dedupe_key == 'FILE_SCAN:' + FileObject.id.cast(FileJob.dedupe_key.type))),
        ).order_by(FileObject.id).limit(limit).with_for_update(skip_locked=True)).all()
        for row in rows:
            enqueue_file_scan(db, row)
        db.commit()
        return len(rows)


def claim_one():
    config = get_file_scan_config()
    now = datetime.utcnow()
    with get_sessionmaker()() as db:
        job = db.scalar(select(FileJob).where(
            FileJob.job_type == 'FILE_SCAN', FileJob.is_deleted.is_(False),
            FileJob.available_at <= now,
            or_(FileJob.status.in_(('PENDING', 'RETRY')),
                (FileJob.status == 'RUNNING') &
                (FileJob.locked_at < now - timedelta(seconds=config.stale_lock_seconds))),
        ).order_by(FileJob.available_at, FileJob.id).limit(1).with_for_update(skip_locked=True))
        if job is None:
            return None
        job.attempts += 1
        job.status, job.locked_at, job.locked_by = 'RUNNING', now, uuid4().hex
        row = db.scalar(select(FileObject).where(
            FileObject.id == job.file_id, FileObject.tenant_id == job.tenant_id))
        claim = Claim(job.id, job.tenant_id, job.file_id, job.attempts, job.locked_by,
                      row.file_key if row else None, row.sha256 if row else None,
                      row.size_bytes if row else None, now)
        db.commit()
        return claim


def scan_claim(claim, client=None):
    """Hash the scanned snapshot before and after the real INSTREAM client call."""
    with get_sessionmaker()() as db:
        row = db.scalar(select(FileObject).where(
            FileObject.id == claim.file_id, FileObject.tenant_id == claim.tenant_id,
            FileObject.is_deleted.is_(False)))
        if not row or not row.scan_required or row.status != 'QUARANTINED':
            raise ClamAVError('FileNotQuarantined')
        key, digest, size = row.file_key, row.sha256, row.size_bytes
        if (key, digest, size) != (claim.file_key, claim.digest, claim.size):
            raise ClamAVError('StorageIdentityChanged')
    if not get_file_scan_config().enabled:
        raise ClamAVUnavailable('ScannerDisabled')
    path = get_backend().fetch_local(key)
    if not path or not path.is_file():
        raise ClamAVError('StorageMissing')

    def fingerprint():
        hasher = sha256()
        total = 0
        with path.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                hasher.update(chunk)
                total += len(chunk)
        return hasher.hexdigest(), total

    if not digest or fingerprint() != (digest, size):
        raise ClamAVError('StorageIntegrityMismatch')
    scanner = client or ClamAVClient()
    version = scanner.version()
    result = scanner.scan_path(path)
    if fingerprint() != (digest, size):
        raise ClamAVError('StorageChangedDuringScan')
    if result.status not in ('CLEAN', 'INFECTED'):
        raise ClamAVError('InvalidScanResult')
    return result, version


def finish_claim(claim, *, result=None, engine_version='', error=None):
    """A previous attempt cannot unlock, release or overwrite a newer attempt."""
    from app.modules.internship.services.internship_audit_service import add_audit

    with get_sessionmaker()() as db:
        job = db.scalar(select(FileJob).where(
            FileJob.id == claim.job_id, FileJob.tenant_id == claim.tenant_id,
            FileJob.is_deleted.is_(False)).with_for_update())
        if not job or job.status != 'RUNNING' or job.attempts != claim.attempt or job.locked_by != claim.token:
            return {'processed': False, 'reason': 'superseded'}
        row = db.scalar(select(FileObject).where(
            FileObject.id == claim.file_id, FileObject.tenant_id == claim.tenant_id,
            FileObject.is_deleted.is_(False)).with_for_update())
        if not row or not row.scan_required or row.status != 'QUARANTINED':
            job.status, job.last_error = 'DEAD', 'FileNotQuarantined'
            job.locked_at = job.locked_by = None
            db.commit()
            return {'processed': True, 'jobStatus': 'DEAD'}
        now = datetime.utcnow()
        before = row.scan_status
        if (row.file_key, row.sha256, row.size_bytes) != (claim.file_key, claim.digest, claim.size):
            error = ClamAVError('StorageIdentityChanged')
        # Store exception class only: driver messages and scanner responses may expose paths.
        code = type(error).__name__[:80] if error else None
        if error:
            exhausted = claim.attempt >= job.max_attempts
            job.status = 'DEAD' if exhausted else 'RETRY'
            job.available_at = now + timedelta(seconds=min(
                3600, get_file_scan_config().retry_base_seconds * 2 ** min(claim.attempt - 1, 10)))
            job.last_error = row.scan_last_error = code
            row.scan_status = 'ERROR' if exhausted else 'PENDING'
        else:
            if result is None or result.status not in ('CLEAN', 'INFECTED'):
                raise ValueError('valid scan result required')
            row.scan_status = result.status
            row.status = 'AVAILABLE' if result.clean else 'REJECTED'
            row.storage_zone = 'ACTIVE' if result.clean else 'REJECTED'
            row.scanned_at = now
            row.available_at = now if result.clean else None
            row.rejected_at = None if result.clean else now
            row.scan_engine = 'CLAMAV'
            pieces = engine_version.split('/')
            row.scan_engine_version = pieces[0][:120] or None
            row.scan_signature_version = pieces[1][:120] if len(pieces) > 1 else None
            row.scan_last_error = None
            job.status, job.last_error = 'SUCCEEDED', None
        row.scan_attempts = claim.attempt
        job.result_json = {'scanStatus': row.scan_status}
        job.locked_at = job.locked_by = None
        db.add(FileScanRecord(tenant_id=claim.tenant_id, file_id=row.id, attempt=claim.attempt,
            engine='CLAMAV', engine_version=row.scan_engine_version,
            signature_version=row.scan_signature_version, result='ERROR' if error else result.status,
            threat_name=(result.signature or '')[:300] if not error else None,
            started_at=claim.started_at, completed_at=now, error_code=code))
        previous_tenant = get_tenant()
        try:
            set_tenant(claim.tenant_id)
            add_audit(db, target_type='FILE', target_id=row.id, action='FILE_SCAN_RESULT',
                user={'realName': '文件安全扫描', 'userType': 'SYSTEM'},
                before_status=before, after_status=row.scan_status,
                detail={'jobId': str(job.id), 'attempt': claim.attempt, 'errorCode': code})
            db.commit()
        finally:
            set_tenant(previous_tenant)
        return {'processed': True, 'jobStatus': job.status, 'scanStatus': row.scan_status}


def process_next_scan_job(client=None):
    claim = claim_one()
    if claim is None:
        return {'processed': False, 'reason': 'empty'}
    try:
        with get_sessionmaker()() as db:
            job = db.get(FileJob, claim.job_id)
            if claim.attempt > job.max_attempts:
                raise ClamAVError('AttemptsExhausted')
        result, version = scan_claim(claim, client)
    except Exception as exc:
        return finish_claim(claim, error=exc)
    # Persistence errors propagate. Do not turn an ambiguous COMMIT into a second completion.
    return finish_claim(claim, result=result, engine_version=version)
