"""Isolated MySQL and actual clamd evidence, never a production file store."""
import os
from datetime import datetime, timedelta
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.config import settings
from app.core.context import current_tenant_id, set_tenant
from app.db.session import get_sessionmaker
from app.models import AuditOutbox, InternshipAuditTrail
from app.models.file import FileJob, FileObject, FileScanRecord
from app.services import file_scan_service as scan
from app.services.clamav_client import ClamAVScanResult, ClamAVUnavailable
from app.services.storage import get_backend
from test_yiyang_write_flows_mysql import seed_flow, login, insurance_body, context, PORTAL

EICAR = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'


@pytest.fixture
def flow(monkeypatch):
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('explicit isolated MySQL opt-in required')
    url = make_url(settings.DATABASE_URL)
    assert settings.APP_ENV == 'test' and url.get_backend_name() == 'mysql'
    assert '_test' in url.database and url.host in ('127.0.0.1', 'localhost')
    monkeypatch.setenv('CLAMAV_ENABLED', 'true')
    monkeypatch.setenv('FILE_SCAN_REQUIRED', 'true')
    data = seed_flow()
    try:
        yield data
    finally:
        from sqlalchemy import delete
        set_tenant(None)
        with get_sessionmaker()() as db:
            for model in (FileScanRecord, FileJob, FileObject, AuditOutbox, InternshipAuditTrail):
                db.execute(delete(model).where(model.tenant_id == int(data['tenantId'])))
            db.commit()


def uploaded(flow, *, data=b'Clean synthetic internship attachment.', name='evidence.txt', mime='text/plain'):
    with login(flow, 'STUDENT') as student:
        response = student.post('/api/v1/files', params={'bizType': 'INTERNSHIP_REPORT'},
                                files={'file': (name, data, mime)})
        assert response.status_code == 200, response.text
        meta = response.json()['data']
        assert meta['status'] == 'QUARANTINED' and meta['readyForBusiness'] is False
        assert meta['statusText'] == '待扫描'
        assert student.get('/api/v1/files/download/' + meta['fileId']).status_code == 404
    return int(meta['fileId'])


def job_for(fid):
    with get_sessionmaker()() as db:
        return db.scalar(select(FileJob).where(FileJob.file_id == fid))


class CleanScanner:
    def version(self): return 'ClamAV test/1'
    def scan_path(self, path): return ClamAVScanResult('CLEAN', None, 'stream: OK')


def test_upload_job_and_audit_are_atomic_and_pending_file_is_private(flow):
    fid = uploaded(flow)
    with get_sessionmaker()() as db:
        job = job_for(fid)
        assert job.tenant_id == int(flow['tenantId']) and job.dedupe_key == f'FILE_SCAN:{fid}'
        assert job.status == 'PENDING'
        assert db.get(FileObject, fid).storage_zone == 'QUARANTINE'
        assert db.scalar(select(func.count()).select_from(InternshipAuditTrail).where(
            InternshipAuditTrail.target_id == fid, InternshipAuditTrail.action == 'FILE_UPLOAD')) == 1


def test_upload_enqueue_failure_rolls_back_file_and_audit(flow, monkeypatch):
    with get_sessionmaker()() as db:
        before = db.scalar(select(func.count()).select_from(FileObject))
    def unavailable(*args): raise RuntimeError('simulated enqueue failure')
    monkeypatch.setattr(scan, 'enqueue_file_scan', unavailable)
    with login(flow, 'STUDENT') as student:
        with pytest.raises(RuntimeError):
            student.post('/api/v1/files', files={'file': ('failure.txt', b'content', 'text/plain')})
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(FileObject)) == before


def test_old_pending_file_reconciled_once_and_existing_dead_never_reset(flow):
    fid = uploaded(flow)
    from sqlalchemy import delete
    with get_sessionmaker()() as db:
        db.execute(delete(FileJob).where(FileJob.file_id == fid)); db.commit()
    assert scan.reconcile_pending_uploads() == 1
    assert scan.reconcile_pending_uploads() == 0
    with get_sessionmaker()() as db:
        job = db.get(FileJob, job_for(fid).id); job.status = 'DEAD'; db.commit()
    assert scan.reconcile_pending_uploads() == 0
    assert job_for(fid).status == 'DEAD'


def test_stale_worker_result_cannot_override_reclaimed_attempt(flow):
    fid = uploaded(flow)
    old = scan.claim_one()
    assert old.file_id == fid
    with get_sessionmaker()() as db:
        job = db.get(FileJob, old.job_id)
        job.locked_at = datetime.utcnow() - timedelta(hours=1); db.commit()
    new = scan.claim_one()
    assert new.attempt == old.attempt + 1 and new.token != old.token
    assert scan.finish_claim(old, result=CleanScanner().scan_path(None))['reason'] == 'superseded'
    infected = ClamAVScanResult('INFECTED', 'Test.Threat', 'stream: Test.Threat FOUND')
    assert scan.finish_claim(new, result=infected)['scanStatus'] == 'INFECTED'
    assert scan.finish_claim(old, result=CleanScanner().scan_path(None))['processed'] is False
    with get_sessionmaker()() as db:
        assert db.get(FileObject, fid).status == 'REJECTED'
        assert db.scalar(select(func.count()).select_from(FileScanRecord).where(FileScanRecord.file_id == fid)) == 1


def test_deleted_file_never_resurrects(flow):
    fid = uploaded(flow)
    claim = scan.claim_one()
    with get_sessionmaker()() as db:
        row = db.get(FileObject, fid); row.is_deleted = True; row.status = 'DELETED'; db.commit()
    assert scan.finish_claim(claim, result=CleanScanner().scan_path(None))['jobStatus'] == 'DEAD'
    with get_sessionmaker()() as db:
        assert db.get(FileObject, fid).status == 'DELETED'


def test_scan_failure_backoff_exhaustion_and_sensitive_error_redaction(flow):
    fid = uploaded(flow)
    claim = scan.claim_one()
    with get_sessionmaker()() as db:
        db.get(FileJob, claim.job_id).max_attempts = 2; db.commit()
    assert scan.finish_claim(claim, error=ClamAVUnavailable('/private/path: secret'))['jobStatus'] == 'RETRY'
    assert job_for(fid).available_at > datetime.utcnow()
    assert scan.claim_one() is None
    with get_sessionmaker()() as db:
        db.get(FileJob, claim.job_id).available_at = datetime.utcnow() - timedelta(seconds=1); db.commit()
    assert scan.finish_claim(scan.claim_one(), error=ClamAVUnavailable('secret'))['jobStatus'] == 'DEAD'
    with get_sessionmaker()() as db:
        row = db.get(FileObject, fid)
        assert row.status == 'QUARANTINED' and row.scan_status == 'ERROR'
        assert row.scan_last_error == 'ClamAVUnavailable' and job_for(fid).last_error == 'ClamAVUnavailable'


def test_corrupt_bytes_cannot_be_released(flow):
    fid = uploaded(flow)
    with get_sessionmaker()() as db:
        path = get_backend().fetch_local(db.get(FileObject, fid).file_key)
    path.write_bytes(b'changed after upload')
    assert scan.process_next_scan_job(CleanScanner())['jobStatus'] == 'RETRY'
    with get_sessionmaker()() as db:
        assert db.get(FileObject, fid).status == 'QUARANTINED'


def test_file_metadata_changed_mid_scan_is_not_released(flow):
    fid = uploaded(flow)
    claim = scan.claim_one()
    with get_sessionmaker()() as db:
        db.get(FileObject, fid).sha256 = sha256(b'other').hexdigest(); db.commit()
    assert scan.finish_claim(claim, result=CleanScanner().scan_path(None))['jobStatus'] == 'RETRY'


def test_database_commit_failure_preserves_reclaimable_job(flow, monkeypatch):
    fid = uploaded(flow)
    claim = scan.claim_one()
    factory = get_sessionmaker()
    broken = factory()
    def fail(): raise RuntimeError('connection lost')
    monkeypatch.setattr(broken, 'commit', fail)
    with monkeypatch.context() as patch:
        patch.setattr(scan, 'get_sessionmaker', lambda: lambda: broken)
        with pytest.raises(RuntimeError): scan.finish_claim(claim, result=CleanScanner().scan_path(None))
    assert job_for(fid).status == 'RUNNING'
    with factory() as db:
        assert db.get(FileObject, fid).status == 'QUARANTINED'
        assert db.scalar(select(func.count()).select_from(FileScanRecord).where(FileScanRecord.file_id == fid)) == 0


def test_concurrent_claimers_do_not_claim_the_same_file(flow):
    from concurrent.futures import ThreadPoolExecutor
    ids = [uploaded(flow) for _ in range(6)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: scan.claim_one(), range(6)))
    # SKIP LOCKED can temporarily see an empty queue while another claim holds locks.
    # Unclaimed jobs must stay pending and be recoverable on the next poll.
    claims = [claim for claim in claims if claim is not None]
    while claim := scan.claim_one():
        claims.append(claim)
    assert {claim.file_id for claim in claims} == set(ids)
    assert len({claim.token for claim in claims}) == 6


def test_cross_tenant_job_cannot_release_another_school_file(flow):
    fid = uploaded(flow)
    with get_sessionmaker()() as db:
        job = db.get(FileJob, job_for(fid).id)
        job.tenant_id = int(flow['tenantId']) + 99999
        db.commit()
    claim = scan.claim_one()
    assert scan.finish_claim(claim, result=CleanScanner().scan_path(None))['jobStatus'] == 'DEAD'
    with get_sessionmaker()() as db:
        assert db.get(FileObject, fid).status == 'QUARANTINED'
        db.delete(db.get(FileJob, claim.job_id)); db.commit()


@pytest.mark.parametrize('name', ['evidence.pdf', 'evidence.docx', 'evidence.zip', 'evidence.mp4'])
def test_real_clamd_clean_supported_attachment_can_be_bound_after_scan(flow, name):
    assert os.environ.get('REAL_CLAMAV_ACCEPTANCE') == '1', 'real clamd required; no fake scanner allowed'
    data, mime = b'%PDF-1.4\n% synthetic evidence\n%%EOF\n', 'application/pdf'
    if name.endswith(('.docx', '.zip')):
        output = BytesIO()
        with ZipFile(output, 'w') as archive:
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr('word/document.xml' if name.endswith('.docx') else 'evidence.txt', 'Clean synthetic content')
        data, mime = output.getvalue(), 'application/octet-stream'
    elif name.endswith('.mp4'):
        data, mime = b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom', 'video/mp4'
    fid = uploaded(flow, data=data, name=name, mime=mime)
    claim = scan.claim_one()
    result, version = scan.scan_claim(claim)
    assert result.clean and version.startswith('ClamAV')
    set_tenant(12345)
    assert scan.finish_claim(claim, result=result, engine_version=version)['scanStatus'] == 'CLEAN'
    assert current_tenant_id() == '12345'
    with login(flow, 'STUDENT') as student, login(flow) as school:
        assert student.get('/api/v1/files/'+str(fid)).json()['data']['readyForBusiness'] is True
        assert student.get('/api/v1/files/download/'+str(fid)).content == data
        assert school.get('/api/v1/files/download/'+str(fid)).status_code == 404
        response = student.post(PORTAL+'/insurance', json=insurance_body(flow, str(fid)))
        assert response.status_code == 200 and response.json()['code'] == 0, response.text
        assert school.get('/api/v1/files/download/'+str(fid)).content == data
    with get_sessionmaker()() as db:
        records = db.scalars(select(FileScanRecord).where(FileScanRecord.file_id == fid)).all()
        assert len(records) == 1 and records[0].result == 'CLEAN' and records[0].engine_version
        outbox = db.scalar(select(AuditOutbox).where(AuditOutbox.tenant_id == int(flow['tenantId']),
            AuditOutbox.event_type == 'INTERNSHIP_FILE_SCAN_RESULT'))
        assert outbox.payload_json['actorRole'] == 'SYSTEM'
        assert outbox.payload_json['tenantId'] == flow['tenantId']


def test_real_clamd_eicar_and_archive_payload_rejected(flow):
    assert os.environ.get('REAL_CLAMAV_ACCEPTANCE') == '1'
    output = BytesIO()
    with ZipFile(output, 'w') as archive: archive.writestr('eicar.txt', EICAR)
    for data, name in [(EICAR, 'eicar.txt'), (output.getvalue(), 'eicar.zip')]:
        fid = uploaded(flow, data=data, name=name, mime='application/octet-stream')
        assert scan.process_next_scan_job()['scanStatus'] == 'INFECTED'
        with login(flow, 'STUDENT') as student:
            meta = student.get('/api/v1/files/'+str(fid)).json()['data']
            assert meta['status'] == 'REJECTED' and meta['statusText'] == '已拒绝'
            assert meta['readyForBusiness'] is False
            assert student.get('/api/v1/files/download/'+str(fid)).status_code == 404
            blocked = student.post(PORTAL+'/insurance', json=insurance_body(flow, str(fid)))
            assert blocked.status_code != 200 or blocked.json()['code'] != 0
