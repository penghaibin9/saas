from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest


def test_same_dead_message_can_only_be_requeued_once(db_mode):
    from sqlalchemy import select,func
    from app.core.context import set_tenant,set_current_user
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import MessageEventOutbox,SecurityAuditLog
    from app.services.message_event_outbox_service import retry_dead_outbox
    tid=1000000000000000001
    with get_sessionmaker()() as db:
        row=MessageEventOutbox(tenant_id=tid,event_code='LEAVE.APPROVED',source_module='student-affairs',
            source_biz_type='LEAVE',source_biz_id=610, dedup_key='d610-concurrent-retry',status='DEAD',attempt_count=5)
        db.add(row);db.commit();oid=row.id
    barrier=Barrier(2)
    def retry():
        set_tenant({'tenantId':str(tid)});set_current_user({'userId':'db-1','realName':'独立并发测试'})
        try:
            barrier.wait(timeout=15)
            try:
                retry_dead_outbox(oid);return 'requeued'
            except AppException as exc:
                return exc.code
        finally:
            set_current_user(None);set_tenant(None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:retry(),range(2)))
    assert sorted(results)==['DATA_CONFLICT','requeued']
    with get_sessionmaker()() as db:
        row=db.get(MessageEventOutbox,oid)
        assert row.status=='PENDING' and row.dedup_key=='d610-concurrent-retry'
        count=db.scalar(select(func.count()).select_from(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id==tid,SecurityAuditLog.action=='MESSAGE_OUTBOX_RETRY',SecurityAuditLog.resource_id==str(oid)))
        assert count==1
