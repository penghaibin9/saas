from pathlib import Path
import ast


def read(p): return Path(p).read_text(encoding='utf-8')
def write(p,t): Path(p).write_text(t,encoding='utf-8')
def rep(t,o,n,label):
    c=t.count(o)
    if c!=1: raise SystemExit(f'{label}: expected 1 anchor, found {c}')
    return t.replace(o,n,1)

# E3 canonical external-channel mutation policy.
p='backend/app/services/message_campaign_service.py'; t=read(p)
marker='\ndef _campaign_dict(row, *, attachments: list | None = None) -> dict:\n'
helper=r'''
def assert_campaign_channel_send_allowed(db, user: dict, camp, channel: str) -> None:
    """Canonical channel-send authorization: same publish capability + existing campaign ownership scope."""
    ch = str(channel or "").upper()
    if ch not in ("SMS", "WECHAT"):
        raise AppException("VALIDATION_ERROR", "仅支持 SMS/WECHAT", http_status=422)
    if not _can_publish(user):
        raise no_permission("无消息发布权限")
    if camp.status not in ("PUBLISHED", "PUBLISHING", "PARTIAL_FAILED"):
        raise AppException("DATA_CONFLICT", "仅已发布消息可外发渠道", http_status=409)
    if has_permission(user, "workbench.message.schoolAll.publish"):
        return
    uid = _uid(user)
    if int(camp.sender_user_id or 0) == int(uid or 0) and uid:
        return
    ctx = str(user.get("activeContextId") or "").strip()
    if int(camp.sender_user_id or 0) == 0 and ctx and str(camp.sender_context_id or "") == ctx:
        return
    # Existing product scope for non-school publishers is owner-only (same as list/get campaign).
    raise not_found("发布单不存在")

'''
if marker not in t: raise SystemExit('campaign helper marker missing')
t=t.replace(marker,'\n'+helper+marker.lstrip('\n'),1); write(p,t)

p='backend/app/services/message_ops_service.py'; t=read(p)
start=t.index('def enqueue_channel_delivery('); end=t.index('\ndef reconcile_message_stats',start)
new_enqueue=r'''def enqueue_channel_delivery(user: dict, campaign_id: str, *, channel: str) -> dict:
    """Authorize and durably enqueue every stable campaign receiver; HTTP never loops provider calls."""
    from app.models import MessageCampaign
    from app.services import message_campaign_service as campaign_svc
    from app.services import message_channel_delivery_service as channel_svc

    ch = str(channel or "").upper()
    if ch not in ("SMS", "WECHAT"):
        raise AppException("VALIDATION_ERROR", "仅支持 SMS/WECHAT", http_status=422)
    with session() as db:
        camp = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == int(campaign_id),
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
        ))
        if not camp:
            raise not_found("发布单不存在")
        campaign_svc.assert_campaign_channel_send_allowed(db, user, camp, ch)
        result = channel_svc.enqueue_campaign_channel_deliveries_in_db(
            db, camp, channel=ch, created_by=_uid(user),
        )
        db.commit()
        return result

'''
t=t[:start]+new_enqueue+t[end:]; write(p,t)

# E4 model.
p='backend/app/models/message.py'; t=read(p)
insert='''\n\nclass MessageAudience(PKMixin, TenantMixin, CommonMixin, Base):\n'''
model=r'''

class MessageChannelDelivery(PKMixin, TenantMixin, CommonMixin, Base):
    """Durable per-recipient external-channel delivery fact.

    DB enqueue is exactly-once by unique key. Worker execution is at-least-once; provider
    duplicates are minimized but not mathematically eliminated without provider idempotency.
    """
    __tablename__ = "t_message_channel_delivery"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "campaign_id", "channel", "receiver_user_id",
            name="uk_msg_channel_delivery_receiver",
        ),
        Index("ix_msg_channel_delivery_claim", "tenant_id", "status", "next_retry_at", "id"),
        Index("ix_msg_channel_delivery_campaign", "tenant_id", "campaign_id", "channel", "status"),
    )

    campaign_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    receiver_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING",
        comment="PENDING/PROCESSING/RETRY_WAIT/SENT/SKIPPED/DEAD")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_by: Mapped[str | None] = mapped_column(String(80))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_message_safe: Mapped[str | None] = mapped_column(String(200))
    provider_request_id: Mapped[str | None] = mapped_column(String(120))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
'''
if insert not in t: raise SystemExit('message model insertion marker missing')
t=t.replace(insert,model+insert,1); write(p,t)

p='backend/app/models/__init__.py'; t=read(p)
t=rep(t,'    MessageCampaign,\n    MessageDeliveryJob,\n','    MessageCampaign,\n    MessageChannelDelivery,\n    MessageDeliveryJob,\n','models export'); write(p,t)

# Durable worker service.
write('backend/app/services/message_channel_delivery_service.py', r'''"""Durable SMS/WECHAT campaign delivery queue.

No plaintext phone is persisted here. Phone is decrypted from User.phone_encrypted only inside
one worker attempt, then immediately discarded from local scope.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import and_, func, or_, select

from app.core.field_crypto import decrypt_field
from app.services.db_service import _tid, session

log = logging.getLogger("app.message_channel_delivery")
_MAX_ATTEMPTS = 8
_LEASE_SECONDS = 120


def _now():
    from app.core.timeutil import utc_now_naive
    return utc_now_naive()


def _backoff(attempt: int) -> int:
    return min(3600, 30 * (2 ** max(0, attempt - 1)))


def enqueue_campaign_channel_deliveries_in_db(db, camp, *, channel: str, created_by: int) -> dict:
    from app.models import MessageChannelDelivery, UnifiedMessage
    ch = str(channel or "").upper()
    rows = db.execute(select(
        UnifiedMessage.receiver_user_id,
    ).where(
        UnifiedMessage.tenant_id == int(camp.tenant_id),
        UnifiedMessage.campaign_id == int(camp.id),
        UnifiedMessage.is_deleted.is_(False),
    ).order_by(UnifiedMessage.id.asc())).all()
    receiver_ids = []
    legacy_unmapped = 0
    seen = set()
    for (uid,) in rows:
        if uid is None:
            legacy_unmapped += 1
            continue
        value = int(uid)
        if value <= 0 or value in seen:
            continue
        seen.add(value); receiver_ids.append(value)
    existing_ids = set(db.scalars(select(MessageChannelDelivery.receiver_user_id).where(
        MessageChannelDelivery.tenant_id == int(camp.tenant_id),
        MessageChannelDelivery.campaign_id == int(camp.id),
        MessageChannelDelivery.channel == ch,
        MessageChannelDelivery.is_deleted.is_(False),
    )).all())
    new_count = 0
    for uid in receiver_ids:
        if uid in existing_ids:
            continue
        db.add(MessageChannelDelivery(
            tenant_id=int(camp.tenant_id), campaign_id=int(camp.id), channel=ch,
            receiver_user_id=uid, status="PENDING", attempt_count=0,
            created_by=int(created_by or 0),
        ))
        new_count += 1
    db.flush()
    return {
        "channel": ch,
        "accepted": True,
        "recipientCount": len(receiver_ids),
        "newQueuedCount": new_count,
        "existingCount": len(receiver_ids) - new_count,
        "legacyUnmappedCount": legacy_unmapped,
    }


def _claim(limit: int, worker_id: str, lease_seconds: int):
    from app.models import MessageChannelDelivery
    now = _now()
    with session() as db:
        rows = db.scalars(select(MessageChannelDelivery).where(
            MessageChannelDelivery.tenant_id == _tid(),
            MessageChannelDelivery.is_deleted.is_(False),
            or_(
                and_(
                    MessageChannelDelivery.status.in_(("PENDING", "RETRY_WAIT")),
                    or_(MessageChannelDelivery.next_retry_at.is_(None), MessageChannelDelivery.next_retry_at <= now),
                ),
                and_(
                    MessageChannelDelivery.status == "PROCESSING",
                    or_(MessageChannelDelivery.lease_expires_at.is_(None), MessageChannelDelivery.lease_expires_at <= now),
                ),
            ),
        ).order_by(MessageChannelDelivery.id.asc()).with_for_update(skip_locked=True).limit(limit)).all()
        ids=[]
        for row in rows:
            row.status="PROCESSING"; row.locked_by=worker_id; row.locked_at=now
            row.lease_expires_at=now+timedelta(seconds=lease_seconds)
            row.attempt_count=int(row.attempt_count or 0)+1; ids.append(int(row.id))
        if ids: db.commit()
        return ids


def _safe_message(value) -> str | None:
    text=str(value or '').strip()
    return text[:200] or None


def _process_one(row_id: int, worker_id: str) -> bool:
    from app.models import MessageCampaign, MessageChannelDelivery, User
    from app.services.notification import sms_service
    with session() as db:
        row=db.get(MessageChannelDelivery,row_id); now=_now()
        if not row or row.status!='PROCESSING' or row.locked_by!=worker_id or not row.lease_expires_at or row.lease_expires_at<=now:
            return False
        if row.channel=='WECHAT':
            row.status='SKIPPED'; row.last_error_code='NOT_CONFIGURED'; row.last_error_message_safe='WECHAT_NOT_CONFIGURED'
            row.locked_by=None; row.locked_at=None; row.lease_expires_at=None; db.commit(); return True
        user=db.scalar(select(User).where(
            User.id==row.receiver_user_id, User.tenant_id==row.tenant_id,
            User.is_deleted.is_(False),
        ))
        if not user or str(user.status or '').upper()!='ACTIVE':
            row.status='SKIPPED'; row.last_error_code='USER_INACTIVE'
            row.locked_by=None; row.locked_at=None; row.lease_expires_at=None; db.commit(); return True
        try:
            phone=decrypt_field(user.phone_encrypted, allow_legacy_plaintext=False)
        except Exception:
            phone=None
        if not phone or len(str(phone).strip())<7:
            row.status='SKIPPED'; row.last_error_code='PHONE_UNAVAILABLE'
            row.locked_by=None; row.locked_at=None; row.lease_expires_at=None; db.commit(); return True
        camp=db.scalar(select(MessageCampaign).where(
            MessageCampaign.id==row.campaign_id, MessageCampaign.tenant_id==row.tenant_id,
            MessageCampaign.is_deleted.is_(False),
        ))
        if not camp:
            row.status='DEAD'; row.last_error_code='CAMPAIGN_NOT_FOUND'
            row.locked_by=None; row.locked_at=None; row.lease_expires_at=None; db.commit(); return True
        result=sms_service.send_sms(
            int(row.tenant_id), str(phone), 'MESSAGE_CAMPAIGN',
            {'title': camp.title, 'summary': (camp.summary or '')[:40]},
            biz_type='MESSAGE_CAMPAIGN', receiver_name=user.real_name,
        )
        # Drop plaintext reference before any DB/log formatting below.
        phone=None
        status=str(result.get('status') or 'FAILED').upper()
        reason_code=str(result.get('reasonCode') or '').upper()
        row.provider_request_id=(str(result.get('requestId') or '')[:120] or None)
        row.last_error_message_safe=_safe_message(result.get('reason'))
        if status=='SENT':
            row.status='SENT'; row.sent_at=_now(); row.last_error_code=None
        elif status=='SKIPPED' and not bool(result.get('retryable')):
            row.status='SKIPPED'; row.last_error_code=reason_code or 'PROVIDER_SKIPPED'
        elif bool(result.get('retryable')):
            if int(row.attempt_count or 0)>=_MAX_ATTEMPTS:
                row.status='DEAD'; row.last_error_code=reason_code or 'RETRY_EXHAUSTED'
            else:
                row.status='RETRY_WAIT'; row.last_error_code=reason_code or 'TRANSIENT_PROVIDER'
                delay=int(result.get('retryAfter') or _backoff(int(row.attempt_count or 1)))
                row.next_retry_at=_now()+timedelta(seconds=max(delay,1))
        else:
            if int(row.attempt_count or 0)>=_MAX_ATTEMPTS:
                row.status='DEAD'; row.last_error_code=reason_code or 'PERMANENT_PROVIDER'
            else:
                # Provider failures are finite retries; permanent failures eventually DEAD.
                row.status='RETRY_WAIT'; row.last_error_code=reason_code or 'PERMANENT_PROVIDER'
                row.next_retry_at=_now()+timedelta(seconds=_backoff(int(row.attempt_count or 1)))
        row.locked_by=None; row.locked_at=None; row.lease_expires_at=None; db.commit(); return True


def claim_and_process_channel_deliveries(*, limit: int=100, worker_id: str='scheduler-channel', lease_seconds: int=_LEASE_SECONDS) -> int:
    done=0
    for row_id in _claim(limit,worker_id,lease_seconds):
        try:
            if _process_one(row_id,worker_id): done+=1
        except Exception as exc:  # noqa: BLE001
            log.exception('channel delivery failed id=%s',row_id)
            from app.models import MessageChannelDelivery
            with session() as db:
                row=db.get(MessageChannelDelivery,row_id)
                if not row or row.locked_by!=worker_id: continue
                attempt=int(row.attempt_count or 1); row.last_error_code=type(exc).__name__[:80]
                row.last_error_message_safe='worker internal error'; row.locked_by=None; row.locked_at=None; row.lease_expires_at=None
                if attempt>=_MAX_ATTEMPTS: row.status='DEAD'
                else: row.status='RETRY_WAIT'; row.next_retry_at=_now()+timedelta(seconds=_backoff(attempt))
                db.commit()
    return done
''')

# SMS structured durable-queue semantics, preserving old status values.
p='backend/app/services/notification/sms_service.py'; t=read(p)
t=t.replace('return {"status": "SKIPPED", "reason": "SMS_ENABLED=false"}','return {"status": "SKIPPED", "reason": "SMS_ENABLED=false", "reasonCode": "SMS_DISABLED", "retryable": False}',1)
t=t.replace('return {"status": "SKIPPED", "reason": "缺手机号"}','return {"status": "SKIPPED", "reason": "缺手机号", "reasonCode": "PHONE_UNAVAILABLE", "retryable": False}',1)
t=t.replace('return {"status": "SKIPPED", "reason": "超出发送频率"}','return {"status": "SKIPPED", "reason": "超出发送频率", "reasonCode": "RATE_LIMITED", "retryable": True, "retryAfter": 60}',1)
t=t.replace('''                return {
                    "status": "SENT", "requestId": response.request_id,
                    "retries": attempt,
                }
''','''                return {
                    "status": "SENT", "requestId": response.request_id,
                    "retries": attempt, "reasonCode": "SENT", "retryable": False,
                }
''',1)
t=t.replace('''        return {
            "status": "FAILED", "reason": last_error,
            "retries": attempt,
        }
''','''        retryable = bool(getattr(response, "retryable", False)) if 'response' in locals() else True
        return {
            "status": "FAILED", "reason": last_error,
            "retries": attempt,
            "reasonCode": "TRANSIENT_PROVIDER" if retryable else "PERMANENT_PROVIDER",
            "retryable": retryable,
        }
''',1)
t=t.replace('return {"status": "FAILED", "reason": "内部异常"}','return {"status": "FAILED", "reason": "内部异常", "reasonCode": "TRANSIENT_PROVIDER", "retryable": True}',1)
write(p,t)

# Scheduler worker hook only; tenant effective-state policy belongs to F.
p='backend/scripts/run_scheduled_jobs.py'; t=read(p)
t=rep(t,
'''    from app.services import message_event_outbox_service as msg_outbox
    from app.services import message_campaign_service as camp_svc
''',
'''    from app.services import message_event_outbox_service as msg_outbox
    from app.services import message_campaign_service as camp_svc
    from app.services import message_channel_delivery_service as channel_svc
''','scheduler channel import')
t=rep(t,
'''            _run_isolated(
                f"outbox:{tenant_id}",
                lambda: msg_outbox.process_pending_outbox(
                    limit=80, worker_id="scheduler-outbox"))
''',
'''            _run_isolated(
                f"outbox:{tenant_id}",
                lambda: msg_outbox.process_pending_outbox(
                    limit=80, worker_id="scheduler-outbox"))
            _run_isolated(
                f"channel_delivery:{tenant_id}",
                lambda: channel_svc.claim_and_process_channel_deliveries(
                    limit=100, worker_id="scheduler-channel"))
''','scheduler channel hook'); write(p,t)

# Generate additive migration on current unique head.
versions=Path('backend/alembic/versions')
revs={}; parents=set()
for f in versions.glob('*.py'):
    try: tree=ast.parse(f.read_text(encoding='utf-8'))
    except Exception: continue
    rev=down=None
    for node in tree.body:
        if isinstance(node,(ast.Assign,ast.AnnAssign)):
            names=[]
            if isinstance(node,ast.Assign): names=[x.id for x in node.targets if isinstance(x,ast.Name)]; val=node.value
            else: names=[node.target.id] if isinstance(node.target,ast.Name) else []; val=node.value
            if 'revision' in names:
                try: rev=ast.literal_eval(val)
                except Exception: pass
            if 'down_revision' in names:
                try: down=ast.literal_eval(val)
                except Exception: pass
    if rev: revs[str(rev)]=f
    if down:
        if isinstance(down,(tuple,list)): parents.update(map(str,down))
        else: parents.add(str(down))
heads=[r for r in revs if r not in parents]
if len(heads)!=1: raise SystemExit(f'expected one alembic head, got {heads}')
head=heads[0]; revision='msg_channel_delivery_20260813'
if revision in revs: raise SystemExit('migration revision already exists')
write(versions/'msg_channel_delivery_20260813.py', f'''"""add durable message channel delivery queue\n\nRevision ID: {revision}\nRevises: {head}\n"""\nfrom alembic import op\nimport sqlalchemy as sa\n\nrevision = "{revision}"\ndown_revision = "{head}"\nbranch_labels = None\ndepends_on = None\n\ndef upgrade():\n    op.create_table(\n        "t_message_channel_delivery",\n        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),\n        sa.Column("tenant_id", sa.BigInteger(), nullable=False),\n        sa.Column("campaign_id", sa.BigInteger(), nullable=False),\n        sa.Column("channel", sa.String(20), nullable=False),\n        sa.Column("receiver_user_id", sa.BigInteger(), nullable=False),\n        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),\n        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),\n        sa.Column("next_retry_at", sa.DateTime(), nullable=True),\n        sa.Column("locked_by", sa.String(80), nullable=True),\n        sa.Column("locked_at", sa.DateTime(), nullable=True),\n        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),\n        sa.Column("last_error_code", sa.String(80), nullable=True),\n        sa.Column("last_error_message_safe", sa.String(200), nullable=True),\n        sa.Column("provider_request_id", sa.String(120), nullable=True),\n        sa.Column("sent_at", sa.DateTime(), nullable=True),\n        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),\n        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),\n        sa.Column("created_by", sa.BigInteger(), nullable=True),\n        sa.Column("updated_by", sa.BigInteger(), nullable=True),\n        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),\n        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),\n        sa.UniqueConstraint("tenant_id","campaign_id","channel","receiver_user_id",name="uk_msg_channel_delivery_receiver"),\n    )\n    op.create_index("ix_msg_channel_delivery_claim","t_message_channel_delivery",["tenant_id","status","next_retry_at","id"])\n    op.create_index("ix_msg_channel_delivery_campaign","t_message_channel_delivery",["tenant_id","campaign_id","channel","status"])\n    op.create_index(op.f("ix_t_message_channel_delivery_campaign_id"),"t_message_channel_delivery",["campaign_id"])\n    op.create_index(op.f("ix_t_message_channel_delivery_receiver_user_id"),"t_message_channel_delivery",["receiver_user_id"])\n    op.create_index(op.f("ix_t_message_channel_delivery_tenant_id"),"t_message_channel_delivery",["tenant_id"])\n\ndef downgrade():\n    op.drop_table("t_message_channel_delivery")\n''')

# Contracts: authorization, durable all-recipient queue, encrypted-phone-only worker.
write('backend/tests/test_message_channel_delivery.py', r'''from __future__ import annotations

from datetime import timedelta
import inspect

import pytest


def _actor(tid, uid, perms, ctx='ctx-1'):
    return {'tenantId':str(tid),'userId':str(uid),'activeContextId':ctx,'permissions':list(perms),'realName':'发布人','userType':'TEACHER'}


def test_plain_staff_cannot_send_external_channel():
    from app.services import message_campaign_service as svc
    class Camp: status='PUBLISHED'; sender_user_id=1; sender_context_id=None
    with pytest.raises(Exception): svc.assert_campaign_channel_send_allowed(None,_actor(1,1,[]),Camp(),'SMS')


def test_campaign_owner_with_publish_scope_can_send():
    from app.services import message_campaign_service as svc
    class Camp: status='PUBLISHED'; sender_user_id=7; sender_context_id=None
    svc.assert_campaign_channel_send_allowed(None,_actor(1,7,['workbench.message.publish']),Camp(),'SMS')


def test_other_sender_cannot_send_without_scope():
    from app.services import message_campaign_service as svc
    from app.core.exceptions import AppException
    class Camp: status='PUBLISHED'; sender_user_id=7; sender_context_id=None
    with pytest.raises(AppException) as exc: svc.assert_campaign_channel_send_allowed(None,_actor(1,8,['workbench.message.publish']),Camp(),'SMS')
    assert exc.value.http_status==404


def test_school_message_admin_can_send_authorized_school_campaign():
    from app.services import message_campaign_service as svc
    class Camp: status='PUBLISHED'; sender_user_id=7; sender_context_id=None
    svc.assert_campaign_channel_send_allowed(None,_actor(1,8,['workbench.message.schoolAll.publish']),Camp(),'SMS')


def test_draft_and_unknown_channel_are_rejected():
    from app.services import message_campaign_service as svc
    from app.core.exceptions import AppException
    class Draft: status='DRAFT'; sender_user_id=7; sender_context_id=None
    with pytest.raises(AppException) as exc: svc.assert_campaign_channel_send_allowed(None,_actor(1,7,['workbench.message.publish']),Draft(),'SMS')
    assert exc.value.http_status==409
    class Published: status='PUBLISHED'; sender_user_id=7; sender_context_id=None
    with pytest.raises(AppException) as exc: svc.assert_campaign_channel_send_allowed(None,_actor(1,7,['workbench.message.publish']),Published(),'EMAIL')
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
''')

# Migration/model safety: exact unique key and no phone material.
