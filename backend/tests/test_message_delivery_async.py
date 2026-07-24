"""万人级异步投递：租约作业 + 防重复写入。"""
from __future__ import annotations

MAIN = 1000000000000000001


def test_async_delivery_enqueue_idempotent(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageCampaign, UnifiedMessage
    from app.services import message_delivery_service as delivery_svc
    from sqlalchemy import func, select

    set_tenant({"tenantId": str(MAIN)})
    db = get_sessionmaker()()
    try:
        camp = MessageCampaign(
            tenant_id=MAIN,
            title="万人投递压测标题足够长",
            content_plain="压测正文",
            summary="压测",
            category="ANNOUNCEMENT",
            priority="NORMAL",
            status="PUBLISHING",
            source_kind="HUMAN",
            content_mode="SHARED",
            sender_user_id=1,
            publish_mode="IMMEDIATE",
            require_ack=False,
            emergency=False,
            recipient_count=1200,
            created_by=1,
        )
        db.add(camp)
        db.commit()
        db.refresh(camp)
        cid = int(camp.id)
    finally:
        db.close()

    user_ids = list(range(900001, 910001))  # 10000 ids（全校级防重压测量级）
    enq = delivery_svc.enqueue_campaign_delivery(cid, user_ids, batch_size=200)
    assert enq["ok"] is True
    assert enq["jobCount"] == 50

    processed = 0
    for _ in range(80):
        n = delivery_svc.claim_and_process_delivery_jobs(limit=10, worker_id="pytest-delivery")
        processed += n
        if n == 0:
            break
    assert processed >= 50

    db = get_sessionmaker()()
    try:
        cnt = db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            UnifiedMessage.tenant_id == MAIN,
            UnifiedMessage.campaign_id == cid,
            UnifiedMessage.is_deleted.is_(False),
        )) or 0
        assert cnt == 10000
        camp2 = db.get(MessageCampaign, cid)
        assert int(camp2.delivered_count or 0) == 10000
    finally:
        db.close()

    # 二次消费不得重复写
    again = delivery_svc.claim_and_process_delivery_jobs(limit=10, worker_id="pytest-delivery-2")
    assert again == 0
    # 再投递一批，幂等跳过
    delivery_svc.deliver_campaign_batch(cid, user_ids[:200], start=0, batch_size=200)
    db = get_sessionmaker()()
    try:
        cnt2 = db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            UnifiedMessage.tenant_id == MAIN,
            UnifiedMessage.campaign_id == cid,
            UnifiedMessage.is_deleted.is_(False),
        )) or 0
        assert cnt2 == 10000
    finally:
        db.close()


def test_html_sanitize_strips_script():
    from app.services.message_html_sanitize import sanitize_message_html, strip_to_plain
    dirty = '<p>ok</p><script>alert(1)</script><a href="javascript:alert(1)">x</a>'
    clean = sanitize_message_html(dirty)
    assert clean is not None
    assert "script" not in clean.lower()
    assert "javascript:" not in clean.lower()
    assert strip_to_plain(dirty)
