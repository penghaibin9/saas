"""P0 修复：审批同事务副作用、enqueue 不二次 version++、学号复活。"""
from __future__ import annotations

MAIN = 1000000000000000001


def test_enqueue_in_db_does_not_bump_version(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageCampaign, MessageDeliveryJob
    from app.services import message_delivery_service as delivery_svc
    from sqlalchemy import func, select

    set_tenant({"tenantId": str(MAIN)})
    db = get_sessionmaker()()
    try:
        camp = MessageCampaign(
            tenant_id=MAIN,
            title="enqueue 不二次版本标题足够长",
            content_plain="正文",
            summary="摘要",
            category="ANNOUNCEMENT",
            priority="NORMAL",
            status="PUBLISHING",
            source_kind="HUMAN",
            content_mode="SHARED",
            sender_user_id=1,
            publish_mode="IMMEDIATE",
            require_ack=False,
            emergency=False,
            recipient_count=3,
            version=7,
            created_by=1,
        )
        db.add(camp)
        db.commit()
        db.refresh(camp)
        before = int(camp.version or 0)
        enq = delivery_svc.enqueue_campaign_delivery_in_db(db, camp, [1, 2, 3], batch_size=2)
        db.commit()
        db.refresh(camp)
        assert int(camp.version or 0) == before
        assert enq["jobCount"] == 2
        cnt = db.scalar(select(func.count()).select_from(MessageDeliveryJob).where(
            MessageDeliveryJob.campaign_id == camp.id,
            MessageDeliveryJob.is_deleted.is_(False),
        ))
        assert int(cnt or 0) == 2
    finally:
        db.close()


def test_student_void_then_create_restores_same_id(db_mode, client, auth_headers):
    no = "2099777001"
    created = client.post("/api/v1/students", headers=auth_headers, json={
        "studentNo": no, "realName": "复活甲", "phone": "13900001111",
    }).json()
    assert created["code"] == 0
    sid = created["data"]["id"]
    voided = client.post(f"/api/v1/students/{sid}/void", headers=auth_headers, json={
        "reason": "测试作废后复活原档",
    }).json()
    assert voided["code"] == 0 and voided["data"]["isDeleted"] is True

    again = client.post("/api/v1/students", headers=auth_headers, json={
        "studentNo": no, "realName": "复活乙", "phone": "13900002222",
    }).json()
    assert again["code"] == 0
    assert again["data"]["id"] == sid
    assert again["data"].get("restored") is True
    assert again["data"]["realName"] == "复活乙"
