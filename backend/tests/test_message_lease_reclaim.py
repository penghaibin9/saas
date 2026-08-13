from __future__ import annotations

from datetime import timedelta
import inspect


def test_delivery_selector_contains_stale_processing_branch():
    from app.services import message_delivery_service as svc
    source=inspect.getsource(svc.claim_and_process_delivery_jobs)
    assert "status='PROCESSING'" in source
    assert 'lease_expires_at IS NULL OR lease_expires_at<=:now' in source
    assert 'job.locked_by != worker_id' in source
    assert '.with_for_update' not in source or 'SKIP LOCKED' in source


def test_outbox_selector_contains_stale_processing_branch():
    from app.services import message_event_outbox_service as svc
    source=inspect.getsource(svc.process_pending_outbox)
    assert 'MessageEventOutbox.status == "PROCESSING"' in source
    assert 'MessageEventOutbox.lease_expires_at <= now' in source
    assert '.with_for_update(skip_locked=True)' in source


def test_expired_processing_delivery_job_is_reclaimed(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageCampaign, MessageDeliveryJob, Tenant, UnifiedMessage
    from app.services import message_delivery_service as svc
    tid=1000000000000000808
    set_tenant({'tenantId':str(tid)})
    db=get_sessionmaker()()
    try:
        if not db.get(Tenant,tid):
            db.add(Tenant(id=tid,tenant_code='lease-e8',school_name='lease-e8',short_name='e8',deploy_mode='SAAS',db_mode='SHARED',status='ACTIVE'))
        camp=MessageCampaign(tenant_id=tid,title='lease reclaim',content_plain='x',category='ANNOUNCEMENT',priority='NORMAL',status='PUBLISHING',source_kind='HUMAN',content_mode='SHARED',sender_user_id=1,publish_mode='IMMEDIATE',recipient_count=1,delivered_count=0,created_by=1)
        db.add(camp); db.flush()
        job=MessageDeliveryJob(tenant_id=tid,campaign_id=camp.id,cursor_start=0,batch_size=200,status='PROCESSING',attempt_count=1,locked_by='dead-worker',locked_at=svc._utc_now()-timedelta(minutes=5),lease_expires_at=svc._utc_now()-timedelta(seconds=1),recipient_slice_json=[12345],created_by=0)
        db.add(job); db.commit(); jid=job.id
        assert svc.claim_and_process_delivery_jobs(limit=1,worker_id='reclaimer')==1
        db.expire_all(); row=db.get(MessageDeliveryJob,jid)
        assert row.status=='SUCCEEDED' and row.attempt_count==2
        assert db.query(UnifiedMessage).filter_by(tenant_id=tid,campaign_id=camp.id,receiver_user_id=12345).count()==1
    finally:
        db.close(); set_tenant(None)


def test_live_processing_delivery_job_is_not_stolen(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageCampaign, MessageDeliveryJob, Tenant
    from app.services import message_delivery_service as svc
    tid=1000000000000000809; set_tenant({'tenantId':str(tid)}); db=get_sessionmaker()()
    try:
        if not db.get(Tenant,tid): db.add(Tenant(id=tid,tenant_code='lease-e8-live',school_name='lease',short_name='e8l',deploy_mode='SAAS',db_mode='SHARED',status='ACTIVE'))
        camp=MessageCampaign(tenant_id=tid,title='live lease',content_plain='x',category='ANNOUNCEMENT',priority='NORMAL',status='PUBLISHING',source_kind='HUMAN',content_mode='SHARED',sender_user_id=1,publish_mode='IMMEDIATE',created_by=1)
        db.add(camp); db.flush(); job=MessageDeliveryJob(tenant_id=tid,campaign_id=camp.id,cursor_start=0,batch_size=200,status='PROCESSING',attempt_count=2,locked_by='live-worker',locked_at=svc._utc_now(),lease_expires_at=svc._utc_now()+timedelta(minutes=5),recipient_slice_json=[99],created_by=0); db.add(job); db.commit(); jid=job.id
        assert svc.claim_and_process_delivery_jobs(limit=5,worker_id='thief')==0
        db.expire_all(); row=db.get(MessageDeliveryJob,jid); assert row.status=='PROCESSING' and row.locked_by=='live-worker' and row.attempt_count==2
    finally: db.close(); set_tenant(None)


def test_expired_processing_outbox_is_reclaimed(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageEventOutbox, Tenant
    from app.services import message_event_outbox_service as svc
    tid=1000000000000000909; set_tenant({'tenantId':str(tid)}); db=get_sessionmaker()()
    try:
        if not db.get(Tenant,tid): db.add(Tenant(id=tid,tenant_code='lease-e9',school_name='lease-e9',short_name='e9',deploy_mode='SAAS',db_mode='SHARED',status='ACTIVE'))
        row=MessageEventOutbox(tenant_id=tid,event_code='LEAVE.APPROVED',source_module='student-affairs',source_biz_type='LEAVE',source_biz_id=1,payload_json={'title':'done','content':'done'},recipient_refs_json=[{'userId':777}],dedup_key='lease-e9:1',status='PROCESSING',attempt_count=1,locked_by='dead-worker',locked_at=svc._utc_now()-timedelta(minutes=5),lease_expires_at=svc._utc_now()-timedelta(seconds=1),created_by=0)
        db.add(row); db.commit(); rid=row.id
        assert svc.process_pending_outbox(limit=1,worker_id='reclaimer')==1
        db.expire_all(); row=db.get(MessageEventOutbox,rid); assert row.status=='SUCCEEDED' and row.attempt_count==2
    finally: db.close(); set_tenant(None)


def test_live_processing_outbox_is_not_stolen(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageEventOutbox, Tenant
    from app.services import message_event_outbox_service as svc
    tid=1000000000000000910; set_tenant({'tenantId':str(tid)}); db=get_sessionmaker()()
    try:
        if not db.get(Tenant,tid): db.add(Tenant(id=tid,tenant_code='lease-e9-live',school_name='lease',short_name='e9l',deploy_mode='SAAS',db_mode='SHARED',status='ACTIVE'))
        row=MessageEventOutbox(tenant_id=tid,event_code='LEAVE.APPROVED',source_module='student-affairs',source_biz_type='LEAVE',source_biz_id=2,payload_json={},recipient_refs_json=[{'userId':1}],dedup_key='lease-e9:live',status='PROCESSING',attempt_count=3,locked_by='live-worker',locked_at=svc._utc_now(),lease_expires_at=svc._utc_now()+timedelta(minutes=5),created_by=0); db.add(row); db.commit(); rid=row.id
        assert svc.process_pending_outbox(limit=5,worker_id='thief')==0
        db.expire_all(); row=db.get(MessageEventOutbox,rid); assert row.status=='PROCESSING' and row.locked_by=='live-worker' and row.attempt_count==3
    finally: db.close(); set_tenant(None)
