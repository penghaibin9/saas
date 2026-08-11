"""P0 修复：审批同事务副作用、enqueue 不二次 version++、学号受控恢复。"""
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
    """作废学号不得靠二次补录隐式复活；必须走独立 restore 动作并复用原 PK。"""
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass

    db = get_sessionmaker()()
    college = College(tenant_id=MAIN, college_name="受控恢复测试学院", status="ACTIVE")
    db.add(college)
    db.flush()
    major = Major(tenant_id=MAIN, college_id=college.id, major_name="受控恢复测试专业", status="ACTIVE")
    db.add(major)
    db.flush()
    school_class = SchoolClass(
        tenant_id=MAIN,
        major_id=major.id,
        class_name="受控恢复测试班",
        grade="2026",
        status="ACTIVE",
        class_status="NORMAL",
    )
    db.add(school_class)
    db.commit()
    college_id, major_id, class_id = college.id, major.id, school_class.id
    db.close()

    no = "2099777001"
    create_body = {
        "studentNo": no,
        "realName": "复活甲",
        "phone": "13900001111",
        "collegeId": str(college_id),
        "majorId": str(major_id),
        "classId": str(class_id),
    }
    created = client.post("/api/v1/students", headers=auth_headers, json=create_body).json()
    assert created["code"] == 0
    sid = created["data"]["id"]

    voided = client.post(f"/api/v1/students/{sid}/void", headers=auth_headers, json={
        "reason": "测试作废后必须受控恢复",
    }).json()
    assert voided["code"] == 0 and voided["data"]["isDeleted"] is True

    # 已作废学号不能再次走普通补录，也不能借二次补录偷偷改姓名/联系方式。
    again = client.post("/api/v1/students", headers=auth_headers, json={
        **create_body,
        "realName": "复活乙",
        "phone": "13900002222",
    })
    assert again.status_code == 409
    assert again.json()["code"] == "VOIDED_PROFILE_EXISTS"
    assert "受控恢复" in again.json()["message"]

    restored = client.post("/api/v1/students/restore", headers=auth_headers, json={
        "studentNo": no,
        "reason": "确认同一学生，恢复原历史主档",
    }).json()
    assert restored["code"] == 0
    assert restored["data"]["id"] == sid
    assert restored["data"]["realName"] == "复活甲"
    assert restored["data"]["isDeleted"] is False
