"""Yiyang C08/G16 student emergency notice forced-popup receipts.

The persisted emergency notice is authored by the teacher/admin authority service.
This module owns only the student-facing unread/pending projection and explicit
acknowledgement. Merely fetching a notice never marks it as read.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import no_permission, not_found
from app.models.internship import (
    InternshipBatch,
    InternshipEmergencyNoticeReceipt,
)
from app.models.internship_teacher_activity import InternshipEmergencyNotice
from app.modules.internship.services.internship_audit_service import add_audit
from app.modules.internship.services.internship_record_resolver import (
    resolve_student_internship_context,
)
from app.services.db_service import _iso, _tid, session


def _student_context(db, user: dict, batch_id):
    try:
        bid = int(batch_id)
    except (TypeError, ValueError):
        raise not_found("实习批次不存在") from None
    batch = db.scalar(select(InternshipBatch).where(
        InternshipBatch.id == bid,
        InternshipBatch.tenant_id == _tid(),
        InternshipBatch.is_deleted.is_(False),
    ))
    if not batch:
        raise not_found("实习批次不存在")
    ctx = resolve_student_internship_context(
        db,
        student_no=(user or {}).get("studentNo"),
        batch_id=batch.id,
        for_write=False,
    )
    if not ctx.record or int(ctx.record.batch_id or 0) != int(batch.id):
        raise no_permission("当前学生不属于该实习批次")
    return batch, ctx.record


def _notice_view(row: InternshipEmergencyNotice, *, acknowledged_at=None) -> dict:
    return {
        "id": str(row.id),
        "batchId": str(row.batch_id),
        "title": row.title,
        "content": row.content,
        "senderName": row.sender_name_snapshot or "",
        "publishedAt": _iso(row.published_at) or "",
        "status": row.status,
        "acknowledgedAt": _iso(acknowledged_at) or "",
        "requiresPopup": acknowledged_at is None and row.status == "PUBLISHED",
    }


def pending_notices(user: dict, *, batch_id) -> list[dict]:
    """Return only notices that still require an explicit student acknowledgement."""
    with session() as db:
        batch, record = _student_context(db, user, batch_id)
        notices = db.scalars(select(InternshipEmergencyNotice).where(
            InternshipEmergencyNotice.tenant_id == _tid(),
            InternshipEmergencyNotice.batch_id == batch.id,
            InternshipEmergencyNotice.status == "PUBLISHED",
            InternshipEmergencyNotice.is_deleted.is_(False),
        ).order_by(
            InternshipEmergencyNotice.published_at.asc(),
            InternshipEmergencyNotice.id.asc(),
        ).limit(100)).all()
        if not notices:
            return []

        receipt_notice_ids = set(db.scalars(select(
            InternshipEmergencyNoticeReceipt.notice_id
        ).where(
            InternshipEmergencyNoticeReceipt.tenant_id == _tid(),
            InternshipEmergencyNoticeReceipt.student_id == record.student_id,
            InternshipEmergencyNoticeReceipt.batch_id == batch.id,
            InternshipEmergencyNoticeReceipt.notice_id.in_([int(n.id) for n in notices]),
            InternshipEmergencyNoticeReceipt.is_deleted.is_(False),
        )).all())
        return [
            _notice_view(row)
            for row in notices
            if int(row.id) not in receipt_notice_ids
        ]


def acknowledge_notice(user: dict, *, notice_id, batch_id) -> dict:
    """Persist the student's explicit "我已知悉" action; idempotent per notice/student."""
    try:
        nid = int(notice_id)
    except (TypeError, ValueError):
        raise not_found("紧急通知不存在") from None

    with session() as db:
        batch, record = _student_context(db, user, batch_id)
        notice = db.scalar(select(InternshipEmergencyNotice).where(
            InternshipEmergencyNotice.id == nid,
            InternshipEmergencyNotice.tenant_id == _tid(),
            InternshipEmergencyNotice.batch_id == batch.id,
            InternshipEmergencyNotice.status == "PUBLISHED",
            InternshipEmergencyNotice.is_deleted.is_(False),
        ))
        if not notice:
            raise not_found("紧急通知不存在、已撤回或不属于当前批次")

        receipt = db.scalar(select(InternshipEmergencyNoticeReceipt).where(
            InternshipEmergencyNoticeReceipt.tenant_id == _tid(),
            InternshipEmergencyNoticeReceipt.notice_id == notice.id,
            InternshipEmergencyNoticeReceipt.student_id == record.student_id,
            InternshipEmergencyNoticeReceipt.is_deleted.is_(False),
        ))
        if receipt:
            return {
                **_notice_view(notice, acknowledged_at=receipt.acknowledged_at),
                "receiptId": str(receipt.id),
                "alreadyAcknowledged": True,
            }

        now = datetime.utcnow()
        receipt = InternshipEmergencyNoticeReceipt(
            tenant_id=_tid(),
            notice_id=notice.id,
            batch_id=batch.id,
            student_id=record.student_id,
            acknowledged_at=now,
            acknowledged_channel="MOBILE_FORCE_POPUP",
        )
        db.add(receipt)
        db.flush()
        add_audit(
            db,
            target_type="EMERGENCY_NOTICE_RECEIPT",
            target_id=receipt.id,
            action="EMERGENCY_NOTICE_ACKNOWLEDGED",
            user=user,
            batch_id=batch.id,
            detail={
                "noticeId": str(notice.id),
                "studentId": str(record.student_id),
                "channel": "MOBILE_FORCE_POPUP",
            },
        )
        db.commit()
        return {
            **_notice_view(notice, acknowledged_at=now),
            "receiptId": str(receipt.id),
            "alreadyAcknowledged": False,
        }
