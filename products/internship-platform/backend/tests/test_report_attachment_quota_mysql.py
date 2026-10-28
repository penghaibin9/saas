"""Real competing quota reservations in one new synthetic school; retain all existing data."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
import os
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url

from app.config import settings
from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.db.session import get_engine, get_sessionmaker
from app.models import Tenant, User
from app.models.file import FileUploadSession
from app.services import internship_file_transfer_service as transfer


def require_authorized_test_database(app_env, url):
    targets = {
        ('127.0.0.1', 3318, 'internship_pr275_test_20261003'),
        ('127.0.0.1', 3306, 'internship_employment_test_ci'),
    }
    if (app_env != 'test' or url.get_backend_name() != 'mysql'
            or (url.host, url.port, url.database) not in targets):
        raise RuntimeError('report quota test requires an explicitly authorized MySQL test target')


@pytest.mark.skipif(os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1', reason='requires isolated MySQL opt-in')
def test_two_connections_compete_for_last_legal_report_attachment_slot(record_property, monkeypatch):
    url = make_url(settings.DATABASE_URL)
    require_authorized_test_database(settings.APP_ENV, url)
    assert transfer.MAX_TEMP_FILES == 49
    with get_engine().connect() as db:
        assert db.scalar(text('SELECT DATABASE()')) == url.database
        engines = dict(db.execute(text('SELECT table_name,engine FROM information_schema.tables '
            'WHERE table_schema=DATABASE() AND table_name IN '
            "('t_tenant','t_user','t_file_object','t_file_upload_session','t_tenant_storage_quota')")).all())
        assert len(engines) == 5 and set(engines.values()) == {'InnoDB'}
    tag = 'REPORT-QUOTA-' + uuid4().hex[:12]
    with get_sessionmaker()() as db:
        tenant = Tenant(tenant_code=tag, school_name='合成报告附件配额竞争学校', status='ACTIVE')
        db.add(tenant); db.flush()
        actor = User(tenant_id=tenant.id, login_name='quota_actor', real_name='合成配额前置账号',
                     password_hash='disabled-quota-fixture-no-login', user_type='STUDENT', status='DISABLED')
        db.add(actor); db.flush()
        tid, uid = int(tenant.id), int(actor.id)
        for _ in range(transfer.MAX_TEMP_FILES - 1):
            db.add(FileUploadSession(tenant_id=tid, session_key=uuid4().hex,
                source=transfer.UPLOAD_RESERVATION_SOURCE, status='CREATED', expected_size=1,
                received_size=0, created_by=uid, expires_at=datetime.utcnow() + timedelta(hours=1),
                metadata_json={'fileKey': f'{tid}/quota-fixture-{uuid4().hex}.bin'}))
        db.commit()
    record_property('syntheticTenantId', str(tid))
    record_property('syntheticTenantCode', tag)
    barrier = Barrier(2)
    connections = []

    @contextmanager
    def simultaneous_sessions():
        with get_sessionmaker()() as db:
            connections.append(db.scalar(text('SELECT CONNECTION_ID()')))
            barrier.wait(timeout=10)
            yield db

    monkeypatch.setattr(transfer, 'session', simultaneous_sessions)

    def reserve(index):
        set_tenant(tid)
        try:
            reservation_id = transfer._reserve_upload(f'{tid}/quota-race-{index}', 1, uid)
            return ('RESERVED', reservation_id)
        except AppException as exc:
            return (exc.code, None)
        finally:
            set_tenant(None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, (1, 2)))
    assert len(set(connections)) == 2
    assert sorted(result[0] for result in results) == ['FILE_TEMP_QUOTA_EXCEEDED', 'RESERVED']
    with get_sessionmaker()() as db:
        count, size = db.execute(select(func.count(), func.sum(FileUploadSession.expected_size)).where(
            FileUploadSession.tenant_id == tid, FileUploadSession.created_by == uid,
            FileUploadSession.source == transfer.UPLOAD_RESERVATION_SOURCE,
            FileUploadSession.status == 'CREATED', FileUploadSession.is_deleted.is_(False))).one()
        assert count == transfer.MAX_TEMP_FILES and size == 49
        winner = db.get(FileUploadSession, next(rid for state, rid in results if state == 'RESERVED'))
        assert winner.tenant_id == tid and winner.created_by == uid and winner.expected_size == 1
    record_property('pendingReservationsAfter', str(count))
    record_property('winnerCount', '1')
    record_property('rejectedCount', '1')
    record_property('independentMysqlConnections', str(len(set(connections))))
