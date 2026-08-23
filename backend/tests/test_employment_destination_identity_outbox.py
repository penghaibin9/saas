"""W1/P0：就业去向审批结果消息必须按 User.id 投递，而不是把 User.id 当 StudentProfile.id。"""
from __future__ import annotations

TID = 1000000000000000001


def test_destination_result_outbox_uses_user_identity(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageEventOutbox
    from app.modules.employment.services.employment_destination_submission_service import _msg

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        _msg(
            db,
            9000123,
            "就业去向登记已通过",
            "你的就业去向登记已通过审核",
            "EMPLOYMENT_DESTINATION.APPROVED",
            8800123,
        )
        db.commit()
        row = db.query(MessageEventOutbox).filter_by(
            tenant_id=TID,
            event_code="EMPLOYMENT_DESTINATION.APPROVED",
            source_biz_id=8800123,
        ).one()
        assert row.recipient_refs_json == [{"userId": 9000123}]
        assert "studentId" not in row.recipient_refs_json[0]
    finally:
        db.close()
