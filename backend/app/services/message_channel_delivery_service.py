"""Durable SMS/WECHAT campaign delivery queue.

No plaintext phone is persisted here. Phone is decrypted from User.phone_encrypted only inside
one worker attempt, then immediately discarded from local scope.
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta

from sqlalchemy import and_, func, or_, select

from app.core.field_crypto import decrypt_field
from app.services.db_service import _tid, session

log = logging.getLogger("app.message_channel_delivery")
_MAX_ATTEMPTS = 8
_LEASE_SECONDS = 120
_CLAIM_BATCH_SIZE = 5
_PHONE_LIKE_RE = re.compile(r"(?<!\d)(?:(?:\+?86)[ -]?)?1\d{10}(?!\d)")
_LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{7,20}(?!\d)")


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
    text=_PHONE_LIKE_RE.sub('[REDACTED_PHONE]', text)
    text=_LONG_NUMBER_RE.sub('[REDACTED_NUMBER]', text)
    return text[:200] or None


def _process_one(row_id: int, worker_id: str) -> bool:
    from app.models import MessageCampaign, MessageChannelDelivery, User
    from app.services.notification import sms_service
    with session() as db:
        row=db.scalar(select(MessageChannelDelivery).where(
            MessageChannelDelivery.id==row_id, MessageChannelDelivery.tenant_id==_tid(),
            MessageChannelDelivery.is_deleted.is_(False),
        )); now=_now()
        if not row or row.status!='PROCESSING' or row.locked_by!=worker_id or not row.lease_expires_at or row.lease_expires_at<=now:
            return False
        if row.channel=='WECHAT':
            # V3 §9.3：以前这里无条件 SKIPPED/NOT_CONFIGURED，微信渠道从未真正接通。
            # 现在接到 provider adapter，并保留既有 claim lease / retry / backoff / DEAD 语义：
            # 配置缺失、未授权等不可重试原因仍是 SKIPPED（重试没有意义），
            # provider/网络错误才走可重试分支。
            from app.services.notification import wechat_subscribe_service as wechat
            # 先判渠道是否配置：学校根本没开通微信订阅时，收件人是谁并不重要，
            # 报 NOT_CONFIGURED 比报 USER_INACTIVE 更能指向真正要做的事，
            # 也省掉一次无意义的用户查询。持久化的错误码沿用历史值，不改既有契约。
            if not wechat.provider_status()['configured']:
                row.status='SKIPPED'; row.last_error_code='NOT_CONFIGURED'
                row.last_error_message_safe='WECHAT_NOT_CONFIGURED'
                from app.services import mobile_observability_service as _obs
                _obs.record_wechat_delivery(
                    scene=str(getattr(row, 'scene', '') or 'CASE_RESULT'),
                    outcome='NOT_CONFIGURED',
                )
                row.locked_by=None; row.locked_at=None; row.lease_expires_at=None; db.commit(); return True
            user=db.scalar(select(User).where(
                User.id==row.receiver_user_id, User.tenant_id==row.tenant_id,
                User.is_deleted.is_(False),
            ))
            if not user or str(user.status or '').upper()!='ACTIVE':
                row.status='SKIPPED'; row.last_error_code='USER_INACTIVE'
                row.locked_by=None; row.locked_at=None; row.lease_expires_at=None; db.commit(); return True
            result=wechat.send_subscribe_message(
                tenant_id=row.tenant_id,
                openid=getattr(user, 'wx_openid', None),
                scene=str(getattr(row, 'scene', '') or 'CASE_RESULT'),
            )
            status=str(result.get('status') or 'SKIPPED').upper()
            reason_code=str(result.get('reasonCode') or '').upper()
            # §13：微信授权/下发结果只记场景与结果码，不记 openid、正文或手机号。
            from app.services import mobile_observability_service as _obs
            _obs.record_wechat_delivery(
                scene=str(getattr(row, 'scene', '') or 'CASE_RESULT'),
                outcome=reason_code or status,
            )
            row.last_error_message_safe=_safe_message(result.get('reason'))
            if status=='SENT':
                row.status='SENT'; row.sent_at=_now(); row.last_error_code=None
            elif bool(result.get('retryable')):
                # 复用与短信完全一致的 backoff / 上限 / DEAD 语义，不另建一套。
                if int(row.attempt_count or 0)>=_MAX_ATTEMPTS:
                    row.status='DEAD'; row.last_error_code=reason_code or 'RETRY_EXHAUSTED'
                else:
                    row.status='RETRY_WAIT'; row.last_error_code=reason_code or 'TRANSIENT_PROVIDER'
                    delay=int(result.get('retryAfter') or _backoff(int(row.attempt_count or 1)))
                    row.next_retry_at=_now()+timedelta(seconds=max(delay,1))
            else:
                # 未配置 / 未授权 / 场景未登记：重试多少次都一样，不消耗重试预算。
                row.status='SKIPPED'; row.last_error_code=reason_code or 'WECHAT_NOT_CONFIGURED'
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
    attempted=0
    while attempted < max(int(limit), 0):
        batch_limit=min(_CLAIM_BATCH_SIZE, int(limit)-attempted)
        claimed=_claim(batch_limit,worker_id,lease_seconds)
        if not claimed:
            break
        attempted += len(claimed)
        for row_id in claimed:
            try:
                if _process_one(row_id,worker_id): done+=1
            except Exception as exc:  # noqa: BLE001
                log.exception('channel delivery failed id=%s',row_id)
                from app.models import MessageChannelDelivery
                with session() as db:
                    row=db.scalar(select(MessageChannelDelivery).where(
                        MessageChannelDelivery.id==row_id, MessageChannelDelivery.tenant_id==_tid(),
                        MessageChannelDelivery.is_deleted.is_(False),
                    ))
                    if not row or row.locked_by!=worker_id:
                        continue
                    attempt=int(row.attempt_count or 1); row.last_error_code=type(exc).__name__[:80]
                    row.last_error_message_safe='worker internal error'; row.locked_by=None; row.locked_at=None; row.lease_expires_at=None
                    if attempt>=_MAX_ATTEMPTS: row.status='DEAD'
                    else: row.status='RETRY_WAIT'; row.next_retry_at=_now()+timedelta(seconds=_backoff(attempt))
                    db.commit()
    return done
