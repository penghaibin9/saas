"""Exercise the canonical audit sink, existing consumer and rollback on isolated MySQL."""
import uuid
from sqlalchemy import select, func
from app.db.session import get_sessionmaker
from app.models.audit import SecurityAuditLog
from app.models.audit_outbox import AuditOutbox
from app.modules.internship.services.internship_audit_service import process_pending
from app.services.db_service import audit_insert_in_session
from test_yiyang_gap09_minimum_age_mysql import admin
from test_standalone_browser_auth_mysql import TENANT_ID


def test_pending_event_is_persisted_once_with_tenant_identity(admin):
    process_pending(limit=1000)
    marker='IX_TEST_'+uuid.uuid4().hex
    with get_sessionmaker()() as db:
        row=AuditOutbox(tenant_id=TENANT_ID,event_id=uuid.uuid4().hex,event_type=marker,
            payload_json={'tenantId':str(TENANT_ID),'targetType':'TEST','targetId':'77'},status='PENDING')
        db.add(row); db.commit(); row_id=row.id
    assert process_pending(limit=1000)['failed']==0
    assert process_pending(limit=1000)['failed']==0
    with get_sessionmaker()() as db:
        logs=db.scalars(select(SecurityAuditLog).where(SecurityAuditLog.action==marker)).all()
        assert len(logs)==1 and logs[0].tenant_id==TENANT_ID
        assert logs[0].resource_id=='77'
        assert db.get(AuditOutbox,row_id).status=='PROCESSED'


def test_sink_uses_callers_transaction_not_an_independent_commit(admin):
    marker='IX_ROLLBACK_'+uuid.uuid4().hex
    with get_sessionmaker()() as db:
        audit_insert_in_session(db,marker,'TEST',{'safe':'value'},'SUCCESS',tenant_id=TENANT_ID)
        db.flush()
        db.rollback()
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(SecurityAuditLog).where(SecurityAuditLog.action==marker))==0
