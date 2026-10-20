"""SM17 student feedback on the existing complaint/case handling ledger.

Procurement contract:
- title
- two feedback levels: COLLEGE / DEPARTMENT (院 / 系)
- content
- image uploads

Student feedback is not treated as a safety incident by default. It shares the school's existing
case ledger so staff can accept, investigate, resolve and follow up without a parallel workflow.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import InternshipAuditTrail, InternshipComplaint, User
from app.modules.internship.services.internship_student_context_guard import (
    require_explicit_context,
)
from app.services import file_service
from app.services.db_service import _iso, _tid, session

FEEDBACK_LEVELS = {
    "COLLEGE": "学院级",
    "DEPARTMENT": "系部级",
}
_CATEGORY = "STUDENT_FEEDBACK"
_MAX_IMAGES = 9


def _validate_images(value) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AppException("VALIDATION_ERROR", "图片必须以列表提交")
    out: list[str] = []
    for raw in value:
        fid = str(raw or "").strip()
        if not fid or fid in out:
            continue
        meta = file_service.get_file_meta(fid)
        if not meta:
            raise AppException("VALIDATION_ERROR", "反馈图片不存在或无权访问")
        mime = str(meta.get("mimeType") or "").lower()
        ext = str(meta.get("ext") or "").lower()
        if not (mime.startswith("image/") or ext in {"jpg", "jpeg", "png", "gif", "webp", "bmp", "heic", "heif"}):
            raise AppException("VALIDATION_ERROR", "意见反馈仅支持上传图片")
        out.append(fid)
    if len(out) > _MAX_IMAGES:
        raise AppException("VALIDATION_ERROR", f"意见反馈图片最多上传{_MAX_IMAGES}张")
    return out


def _view(row: InternshipComplaint) -> dict:
    return {
        "id": str(row.id),
        "feedbackNo": row.complaint_no or "",
        "title": row.title or "",
        "feedbackLevel": row.feedback_level or "",
        "feedbackLevelLabel": FEEDBACK_LEVELS.get(row.feedback_level or "", row.feedback_level or ""),
        "content": row.content or "",
        "imageFileIds": list(row.image_file_ids or []),
        "status": row.status,
        "statusLabel": {
            "RECEIVED": "已提交",
            "ACCEPTED": "已受理",
            "INVESTIGATING": "处理中",
            "RESOLVED": "已办结",
            "REJECTED": "未采纳",
            "WITHDRAWN": "已撤回",
            "CLOSED": "已关闭",
        }.get(row.status, row.status),
        "conclusion": row.conclusion or "",
        "followupResult": row.followup_result or "",
        "createdAt": _iso(row.created_at) or "",
        "updatedAt": _iso(row.updated_at) or "",
        "version": int(row.version or 0),
    }


def _student_context(db, user: dict, payload: dict, *, for_write: bool):
    record, student, batch_id = require_explicit_context(
        db, user, payload or {}, for_write=for_write)
    return record, student, int(batch_id)


def list_my(user: dict, *, batch_id, internship_id) -> dict:
    payload = {"batchId": batch_id, "internshipId": internship_id}
    with session() as db:
        record, student, _batch_id = _student_context(db, user, payload, for_write=False)
        rows = db.scalars(select(InternshipComplaint).where(
            InternshipComplaint.tenant_id == _tid(),
            InternshipComplaint.student_id == student.id,
            InternshipComplaint.internship_id == record.id,
            InternshipComplaint.category == _CATEGORY,
            InternshipComplaint.source == "STUDENT",
            InternshipComplaint.is_deleted.is_(False),
        ).order_by(InternshipComplaint.id.desc())).all()
        return {"items": [_view(row) for row in rows], "total": len(rows)}


def create(user: dict, body: dict) -> dict:
    payload = body or {}
    title = str(payload.get("title") or "").strip()
    content = str(payload.get("content") or "").strip()
    level = str(payload.get("feedbackLevel") or "").strip().upper()
    if len(title) < 2:
        raise AppException("VALIDATION_ERROR", "反馈标题不少于2个字")
    if len(title) > 200:
        raise AppException("VALIDATION_ERROR", "反馈标题不能超过200个字")
    if level not in FEEDBACK_LEVELS:
        raise AppException("VALIDATION_ERROR", "反馈级别必须选择学院级或系部级")
    if len(content) < 5:
        raise AppException("VALIDATION_ERROR", "反馈内容不少于5个字")
    if len(content) > 4000:
        raise AppException("VALIDATION_ERROR", "反馈内容不能超过4000个字")
    image_ids = _validate_images(payload.get("imageFileIds"))

    with session() as db:
        record, student, batch_id = _student_context(db, user, payload, for_write=True)
        row = InternshipComplaint(
            tenant_id=_tid(),
            source="STUDENT",
            target_type="OTHER",
            student_id=student.id,
            internship_id=record.id,
            batch_id=batch_id,
            category=_CATEGORY,
            title=title,
            feedback_level=level,
            severity="LOW",
            content=content,
            image_file_ids=image_ids or None,
            confidential_level="NORMAL",
            status="RECEIVED",
        )
        db.add(row)
        db.flush()
        row.complaint_no = f"FDB-{datetime.utcnow():%Y%m}-{row.id:05d}"

        for fid in image_ids:
            file_service.bind_file_biz(
                fid, "INTERNSHIP_FEEDBACK", str(row.id), user=user, db=db)

        db.add(InternshipAuditTrail(
            tenant_id=_tid(),
            target_id=row.id,
            target_type="COMPLAINT",
            action="STUDENT_FEEDBACK_CREATE",
            operator_name=(student.real_name or "学生"),
            detail_json={
                "feedbackLevel": level,
                "imageCount": len(image_ids),
                "internshipId": str(record.id),
            },
            occurred_at=datetime.utcnow(),
        ))

        # The advisor receives an immediate in-platform event. The level remains on the formal
        # case record so college/department staff can filter it using their normal scoped ledger.
        try:
            if getattr(record, "advisor_user_id", None):
                from app.services.message_event_outbox_service import emit_message_event
                advisor = db.get(User, int(record.advisor_user_id))
                if advisor and not advisor.is_deleted:
                    emit_message_event(
                        db,
                        event_code="INTERNSHIP.STUDENT_FEEDBACK_CREATED",
                        source_module="internship",
                        source_biz_type="student_feedback",
                        source_biz_id=int(row.id),
                        recipient_refs=[{"userId": int(advisor.id)}],
                        title=f"学生意见反馈：{title[:40]}",
                        content=f"{FEEDBACK_LEVELS[level]} · {content[:300]}",
                        dedup_key=f"INTERNSHIP.STUDENT_FEEDBACK_CREATED:{row.id}:user:{advisor.id}",
                    )
        except Exception:  # noqa: BLE001
            pass

        db.commit()
        result = _view(row)

    try:
        from app.services.message_event_outbox_service import process_pending_outbox
        process_pending_outbox(limit=10, worker_id="internship-feedback-inline")
    except Exception:  # noqa: BLE001
        pass
    return result


def withdraw(user: dict, feedback_id, body: dict) -> dict:
    payload = body or {}
    try:
        fid = int(feedback_id)
    except (TypeError, ValueError):
        raise not_found("意见反馈不存在") from None
    with session() as db:
        record, student, _batch_id = _student_context(db, user, payload, for_write=True)
        row = db.scalar(select(InternshipComplaint).where(
            InternshipComplaint.id == fid,
            InternshipComplaint.tenant_id == _tid(),
            InternshipComplaint.student_id == student.id,
            InternshipComplaint.internship_id == record.id,
            InternshipComplaint.category == _CATEGORY,
            InternshipComplaint.source == "STUDENT",
            InternshipComplaint.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise no_permission("只能操作本人当前实习记录的意见反馈")
        if row.status not in ("RECEIVED", "ACCEPTED"):
            raise AppException("DATA_CONFLICT", "当前反馈已进入处理或办结阶段，不能撤回")
        expected = payload.get("expectedVersion")
        if expected is None:
            raise AppException("DATA_CONFLICT", "缺少反馈版本，请刷新后重试")
        try:
            expected = int(expected)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "expectedVersion 必须是整数") from None
        if expected != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "反馈已被学校更新，请刷新后重试")
        row.status = "WITHDRAWN"
        row.version = int(row.version or 0) + 1
        db.add(InternshipAuditTrail(
            tenant_id=_tid(),
            target_id=row.id,
            target_type="COMPLAINT",
            action="STUDENT_FEEDBACK_WITHDRAW",
            operator_name=(student.real_name or "学生"),
            detail_json={"internshipId": str(record.id)},
            occurred_at=datetime.utcnow(),
        ))
        db.commit()
        return _view(row)
