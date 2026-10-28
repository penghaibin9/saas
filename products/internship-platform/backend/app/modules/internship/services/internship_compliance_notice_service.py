from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from app.core.exceptions import not_found
from app.models import UnifiedMessage
from app.services.db_service import _as_id, _tid, session

def send_compliance_notice(receiver_user_id, title, content, consent_id=None, user=None):
    with session() as db:
        # Consent has a statutory acknowledgement requirement; do not route it through
        # templates that default `require_ack` to false.
        msg = UnifiedMessage(
            tenant_id=_tid(), receiver_id=int(receiver_user_id),
            receiver_user_id=int(receiver_user_id), receiver_context_key="GLOBAL",
            source_module="internship", source_biz_id=_as_id(consent_id) if consent_id else None,
            title=title, content=content, message_type="INTERNSHIP_COMPLIANCE",
            status="UNREAD", require_ack=bool(consent_id), delivery_status="PENDING",
        )
        db.add(msg)
        db.flush()
        db.commit()
    return {"messageId": str(msg.id), "status": "CREATED", "requireAck": bool(consent_id)}
def receipt_status(message):
    if message.ack_at:return "ACKED"
    if message.read_at:return "READ"
    if message.delivered_at:return "DELIVERED"
    if message.delivery_status in ("FAILED","FAIL"):return "FAILED"
    if message.delivery_status in ("SENT","SENDING"):return "SENT"
    if message.delivery_status in ("QUEUED","PENDING"):return "QUEUED"
    return "CREATED"
def list_receipts(message_id):
    with session() as db:
        xs=db.scalars(select(UnifiedMessage).where(UnifiedMessage.tenant_id==_tid(),UnifiedMessage.id==_as_id(message_id),UnifiedMessage.is_deleted.is_(False))).all()
        return [{"id":str(x.id),"status":receipt_status(x),"deliveredAt":x.delivered_at.isoformat() if x.delivered_at else None,"readAt":x.read_at.isoformat() if x.read_at else None,"ackedAt":x.ack_at.isoformat() if x.ack_at else None} for x in xs]
def ack_message(message_id,user=None):
    with session() as db:
        x=db.get(UnifiedMessage,_as_id(message_id))
        if not x or x.tenant_id!=_tid():raise not_found("消息不存在")
        x.ack_at=datetime.utcnow();x.status="READ";db.commit();return {"id":str(x.id),"status":"ACKED"}
