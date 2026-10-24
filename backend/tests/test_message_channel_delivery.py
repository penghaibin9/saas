from __future__ import annotations

from datetime import timedelta
import inspect

import pytest


def _actor(tid, uid, role, ctx='ctx-1'):
    return {'tenantId':str(tid),'userId':str(uid),'activeContextId':ctx,'currentRoleCode':role,'realName':'发布人','userType':'TEACHER'}


def test_plain_staff_cannot_send_external_channel():
    from app.services import message_campaign_service as svc
    class Camp: status='PUBLISHED'; sender_user_id=1; sender_context_id=None
    with pytest.raises(Exception): svc.assert_campaign_channel_send_allowed(None,_actor(1,1,'TEACHER'),Camp(),'SMS')


def test_campaign_owner_with_publish_scope_can_send():
    from app.services import message_campaign_service as svc
    class Camp: status='PUBLISHED'; sender_user_id=7; sender_context_id=None
    svc.assert_campaign_channel_send_allowed(None,_actor(1,7,'COLLEGE_ADMIN'),Camp(),'SMS')


def test_other_sender_cannot_send_without_scope():
    from app.services import message_campaign_service as svc
    from app.core.exceptions import AppException
    class Camp: status='PUBLISHED'; sender_user_id=7; sender_context_id=None
    with pytest.raises(AppException) as exc: svc.assert_campaign_channel_send_allowed(None,_actor(1,8,'COLLEGE_ADMIN'),Camp(),'SMS')
    assert exc.value.http_status==404


def test_school_message_admin_can_send_authorized_school_campaign():
    from app.services import message_campaign_service as svc
    class Camp: status='PUBLISHED'; sender_user_id=7; sender_context_id=None
    svc.assert_campaign_channel_send_allowed(None,_actor(1,8,'SCHOOL_ADMIN'),Camp(),'SMS')


def test_draft_and_unknown_channel_are_rejected():
    from app.services import message_campaign_service as svc
    from app.core.exceptions import AppException
    class Draft: status='DRAFT'; sender_user_id=7; sender_context_id=None
    with pytest.raises(AppException) as exc: svc.assert_campaign_channel_send_allowed(None,_actor(1,7,'COLLEGE_ADMIN'),Draft(),'SMS')
    assert exc.value.http_status==409
    class Published: status='PUBLISHED'; sender_user_id=7; sender_context_id=None
    with pytest.raises(AppException) as exc: svc.assert_campaign_channel_send_allowed(None,_actor(1,7,'COLLEGE_ADMIN'),Published(),'EMAIL')
    assert exc.value.http_status==422


def test_channel_delivery_model_has_no_plain_phone_fields():
    from app.models import MessageChannelDelivery
    names={c.name for c in MessageChannelDelivery.__table__.columns}
    assert 'phone' not in names and 'mobile' not in names and 'phone_plain' not in names and 'payload_json' not in names


def test_worker_source_decrypts_phone_only_at_send_time():
    from app.services import message_channel_delivery_service as svc
    source=inspect.getsource(svc._process_one)
    assert 'decrypt_field(user.phone_encrypted' in source
    assert 'allow_legacy_plaintext=False' in source
    assert 'getattr(user, "phone"' not in source and 'getattr(user, "mobile"' not in source


def test_2000_recipients_enqueue_is_complete_and_idempotent(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageCampaign, MessageChannelDelivery, Tenant, UnifiedMessage
    from app.services.message_channel_delivery_service import enqueue_campaign_channel_deliveries_in_db
    tid=1000000000000011011; set_tenant({'tenantId':str(tid)}); db=get_sessionmaker()()
    try:
        if not db.get(Tenant,tid): db.add(Tenant(id=tid,tenant_code='channel-2k',school_name='channel-2k',short_name='2k',deploy_mode='SAAS',db_mode='SHARED',status='ACTIVE'))
        camp=MessageCampaign(tenant_id=tid,title='2k channel',content_plain='x',category='ANNOUNCEMENT',priority='NORMAL',status='PUBLISHED',source_kind='HUMAN',content_mode='SHARED',sender_user_id=1,publish_mode='IMMEDIATE',created_by=1)
        db.add(camp); db.flush()
        db.add_all([UnifiedMessage(tenant_id=tid,receiver_id=i,receiver_user_id=i,receiver_context_key='GLOBAL',campaign_id=camp.id,title='x',status='UNREAD',created_by=1) for i in range(1,2001)])
        db.flush(); first=enqueue_campaign_channel_deliveries_in_db(db,camp,channel='SMS',created_by=1); db.commit()
        assert first['recipientCount']==2000 and first['newQueuedCount']==2000
        second=enqueue_campaign_channel_deliveries_in_db(db,camp,channel='SMS',created_by=1); db.commit()
        assert second['newQueuedCount']==0 and second['existingCount']==2000
        assert db.query(MessageChannelDelivery).filter_by(tenant_id=tid,campaign_id=camp.id,channel='SMS').count()==2000
    finally: db.close(); set_tenant(None)


def test_missing_and_inactive_user_are_skipped(db_mode):
    from app.core.context import set_tenant
    from app.core.field_crypto import encrypt_field
    from app.db.session import get_sessionmaker
    from app.models import MessageCampaign, MessageChannelDelivery, Tenant, User
    from app.services import message_channel_delivery_service as svc
    tid=1000000000000011012; set_tenant({'tenantId':str(tid)}); db=get_sessionmaker()()
    try:
        if not db.get(Tenant,tid): db.add(Tenant(id=tid,tenant_code='channel-skip',school_name='skip',short_name='skip',deploy_mode='SAAS',db_mode='SHARED',status='ACTIVE'))
        camp=MessageCampaign(tenant_id=tid,title='skip',content_plain='x',category='ANNOUNCEMENT',priority='NORMAL',status='PUBLISHED',source_kind='HUMAN',content_mode='SHARED',sender_user_id=1,publish_mode='IMMEDIATE',created_by=1); db.add(camp); db.flush()
        u=User(tenant_id=tid,login_name='inactive',real_name='inactive',password_hash='x',user_type='STUDENT',phone_encrypted=encrypt_field('13800138000'),status='DISABLED'); db.add(u); db.flush()
        r1=MessageChannelDelivery(tenant_id=tid,campaign_id=camp.id,channel='SMS',receiver_user_id=u.id,status='PENDING',created_by=1)
        r2=MessageChannelDelivery(tenant_id=tid,campaign_id=camp.id,channel='SMS',receiver_user_id=999999,status='PENDING',created_by=1); db.add_all([r1,r2]); db.commit()
        assert svc.claim_and_process_channel_deliveries(limit=10,worker_id='skip-worker')==2
        db.expire_all(); assert db.get(MessageChannelDelivery,r1.id).status=='SKIPPED'; assert db.get(MessageChannelDelivery,r2.id).status=='SKIPPED'
    finally: db.close(); set_tenant(None)


def test_provider_success_marks_sent_and_rate_limit_waits(db_mode, monkeypatch):
    from app.core.context import set_tenant
    from app.core.field_crypto import encrypt_field
    from app.db.session import get_sessionmaker
    from app.models import MessageCampaign, MessageChannelDelivery, Tenant, User
    from app.services import message_channel_delivery_service as svc
    from app.services.notification import sms_service
    tid=1000000000000011013; set_tenant({'tenantId':str(tid)}); db=get_sessionmaker()()
    try:
        if not db.get(Tenant,tid): db.add(Tenant(id=tid,tenant_code='channel-send',school_name='send',short_name='send',deploy_mode='SAAS',db_mode='SHARED',status='ACTIVE'))
        camp=MessageCampaign(tenant_id=tid,title='send',content_plain='x',summary='safe',category='ANNOUNCEMENT',priority='NORMAL',status='PUBLISHED',source_kind='HUMAN',content_mode='SHARED',sender_user_id=1,publish_mode='IMMEDIATE',created_by=1); db.add(camp); db.flush()
        u1=User(tenant_id=tid,login_name='s1',real_name='s1',password_hash='x',user_type='STUDENT',phone_encrypted=encrypt_field('13800138000'),status='ACTIVE'); u2=User(tenant_id=tid,login_name='s2',real_name='s2',password_hash='x',user_type='STUDENT',phone_encrypted=encrypt_field('13900139000'),status='ACTIVE'); db.add_all([u1,u2]); db.flush()
        d1=MessageChannelDelivery(tenant_id=tid,campaign_id=camp.id,channel='SMS',receiver_user_id=u1.id,status='PENDING',created_by=1); d2=MessageChannelDelivery(tenant_id=tid,campaign_id=camp.id,channel='SMS',receiver_user_id=u2.id,status='PENDING',created_by=1); db.add_all([d1,d2]); db.commit()
        calls=[]
        def fake_send(*args,**kwargs):
            calls.append(args[1]); return {'status':'SENT','requestId':'req-1','reasonCode':'SENT','retryable':False} if len(calls)==1 else {'status':'SKIPPED','reason':'rate','reasonCode':'RATE_LIMITED','retryable':True,'retryAfter':60}
        monkeypatch.setattr(sms_service,'send_sms',fake_send)
        assert svc.claim_and_process_channel_deliveries(limit=10,worker_id='provider-worker')==2
        db.expire_all(); assert db.get(MessageChannelDelivery,d1.id).status=='SENT'; wait=db.get(MessageChannelDelivery,d2.id); assert wait.status=='RETRY_WAIT' and wait.next_retry_at is not None
    finally: db.close(); set_tenant(None)


def test_expired_processing_channel_delivery_is_reclaimed(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageCampaign, MessageChannelDelivery, Tenant
    from app.services import message_channel_delivery_service as svc
    tid=1000000000000011014; set_tenant({'tenantId':str(tid)}); db=get_sessionmaker()()
    try:
        if not db.get(Tenant,tid): db.add(Tenant(id=tid,tenant_code='channel-lease',school_name='lease',short_name='lease',deploy_mode='SAAS',db_mode='SHARED',status='ACTIVE'))
        camp=MessageCampaign(tenant_id=tid,title='lease',content_plain='x',category='ANNOUNCEMENT',priority='NORMAL',status='PUBLISHED',source_kind='HUMAN',content_mode='SHARED',sender_user_id=1,publish_mode='IMMEDIATE',created_by=1); db.add(camp); db.flush()
        row=MessageChannelDelivery(tenant_id=tid,campaign_id=camp.id,channel='WECHAT',receiver_user_id=123,status='PROCESSING',attempt_count=1,locked_by='dead',locked_at=svc._now()-timedelta(minutes=5),lease_expires_at=svc._now()-timedelta(seconds=1),created_by=1); db.add(row); db.commit(); rid=row.id
        assert svc.claim_and_process_channel_deliveries(limit=1,worker_id='reclaimer')==1
        db.expire_all(); row=db.get(MessageChannelDelivery,rid); assert row.status=='SKIPPED' and row.last_error_code=='NOT_CONFIGURED' and row.attempt_count==2
    finally: db.close(); set_tenant(None)



def test_concurrent_campaign_channel_enqueue_is_idempotent(db_mode):
    from concurrent.futures import ThreadPoolExecutor
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageCampaign, MessageChannelDelivery, Tenant, UnifiedMessage
    from app.services import message_ops_service
    tid=1000000000000011015; set_tenant({'tenantId':str(tid)}); db=get_sessionmaker()()
    try:
        if not db.get(Tenant,tid): db.add(Tenant(id=tid,tenant_code='channel-race',school_name='channel-race',short_name='race',deploy_mode='SAAS',db_mode='SHARED',status='ACTIVE'))
        camp=MessageCampaign(tenant_id=tid,title='race',content_plain='x',category='ANNOUNCEMENT',priority='NORMAL',status='PUBLISHED',source_kind='HUMAN',content_mode='SHARED',sender_user_id=7,publish_mode='IMMEDIATE',created_by=7); db.add(camp); db.flush(); campaign_id=int(camp.id)
        db.add_all([UnifiedMessage(tenant_id=tid,receiver_id=i,receiver_user_id=i,receiver_context_key='GLOBAL',campaign_id=campaign_id,title='x',status='UNREAD',created_by=7) for i in range(1,101)]); db.commit()
    finally: db.close(); set_tenant(None)
    actor=_actor(tid,8,'SCHOOL_ADMIN')
    def run_once():
        set_tenant({'tenantId':str(tid)})
        try: return message_ops_service.enqueue_channel_delivery(actor,str(campaign_id),channel='SMS')
        finally: set_tenant(None)
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:run_once(),range(2)))
    assert sorted(item['newQueuedCount'] for item in results)==[0,100]
    assert sorted(item['existingCount'] for item in results)==[0,100]
    set_tenant({'tenantId':str(tid)}); db=get_sessionmaker()()
    try: assert db.query(MessageChannelDelivery).filter_by(tenant_id=tid,campaign_id=campaign_id,channel='SMS').count()==100
    finally: db.close(); set_tenant(None)


def test_channel_delivery_has_retry_and_lease_claim_indexes():
    from app.models import MessageChannelDelivery
    names={idx.name for idx in MessageChannelDelivery.__table__.indexes}
    assert 'ix_msg_channel_delivery_claim' in names and 'ix_msg_channel_delivery_lease' in names


def test_safe_provider_error_redacts_phone_and_long_numbers():
    from app.services import message_channel_delivery_service as svc
    value=svc._safe_message('provider rejected +86 13800138000 request 123456789012345')
    assert '13800138000' not in value and '123456789012345' not in value
    assert '[REDACTED_PHONE]' in value and '[REDACTED_NUMBER]' in value


def test_channel_worker_claims_fresh_small_batches(monkeypatch):
    from app.services import message_channel_delivery_service as svc
    calls=[]; batches=[[1,2,3,4,5],[6]]
    def fake_claim(limit,worker_id,lease_seconds):
        calls.append(limit); return batches.pop(0) if batches else []
    monkeypatch.setattr(svc,'_claim',fake_claim)
    monkeypatch.setattr(svc,'_process_one',lambda row_id,worker_id: True)
    assert svc.claim_and_process_channel_deliveries(limit=6,worker_id='batch-review')==6
    assert calls==[5,1]
