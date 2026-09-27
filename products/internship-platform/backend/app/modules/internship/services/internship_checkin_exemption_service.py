"""Yiyang C02 attendance exemption workflow."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, no_permission
from app.models import (
    InternshipAuditTrail,
    InternshipCheckinExemption,
    InternshipRecord,
    StudentProfile,
)
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.modules.internship.services.internship_student_context_guard import (
    require_explicit_context,
)
from app.services import file_service
from app.services.db_service import _as_id, _iso, _tid, session


def _row(item, student=None):
    return {
        "id": str(item.id),
        "internshipId": str(item.internship_id),
        "studentId": str(item.student_id),
        "studentName": student.real_name if student else "",
        "studentNo": student.student_no if student else "",
        "batchId": str(item.batch_id or ""),
        "startDate": item.start_date,
        "endDate": item.end_date,
        "reason": item.reason,
        "evidenceFileId": item.evidence_file_id or "",
        "status": item.status,
        "statusLabel": {
            "PENDING": "待审核", "APPROVED": "已通过",
            "REJECTED": "已驳回", "WITHDRAWN": "已撤回",
        }.get(item.status, item.status),
        "applyByName": item.apply_by_name or "",
        "reviewByName": item.review_by_name or "",
        "reviewComment": item.review_comment or "",
        "reviewedAt": _iso(item.reviewed_at) or "",
        "version": int(item.version or 0),
    }


def _date(raw, label):
    value = str(raw or "").strip()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise AppException("VALIDATION_ERROR", f"{label}格式必须为 YYYY-MM-DD") from None


def _trail(db, item, action, user, detail=None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(),
        target_id=item.id,
        target_type="CHECKIN_EXEMPTION",
        action=action,
        operator_name=str((user or {}).get("realName") or "系统"),
        detail_json=detail or {},
        occurred_at=datetime.utcnow(),
    ))


def list_my(user: dict, *, batch_id=None, internship_id=None):
    from app.modules.internship.services.internship_student_context_guard import require_context_fields
    payload = {"batchId": batch_id, "internshipId": internship_id}
    require_context_fields(payload)
    with session() as db:
        record, student, _batch = require_explicit_context(db, user, payload, for_write=False)
        rows = db.scalars(select(InternshipCheckinExemption).where(
            InternshipCheckinExemption.tenant_id == _tid(),
            InternshipCheckinExemption.internship_id == record.id,
            InternshipCheckinExemption.student_id == student.id,
            InternshipCheckinExemption.is_deleted.is_(False),
        ).order_by(InternshipCheckinExemption.id.desc())).all()
        return [_row(item, student) for item in rows]


def apply(user: dict, body: dict):
    payload = body or {}
    with session() as db:
        record, student, batch = require_explicit_context(db, user, payload, for_write=True)
        start = _date(payload.get("startDate"), "免签开始日期")
        end = _date(payload.get("endDate"), "免签结束日期")
        if start > end:
            raise AppException("VALIDATION_ERROR", "免签结束日期不能早于开始日期")
        reason = str(payload.get("reason") or "").strip()
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "免签理由不少于5个字")
        lower = record.intern_start_date.date() if record.intern_start_date else (
            batch.start_date.date() if batch and batch.start_date else None)
        upper = record.intern_end_date.date() if record.intern_end_date else (
            batch.end_date.date() if batch and batch.end_date else None)
        if lower and start < lower or upper and end > upper:
            raise AppException("VALIDATION_ERROR", "免签日期必须在当前实习起止日期内")

        file_id = str(payload.get("evidenceFileId") or "").strip() or None
        if file_id and not file_service.get_file_meta(file_id, user):
            raise AppException("VALIDATION_ERROR", "免签佐证材料不存在或尚未安全就绪")

        exists = db.scalar(select(InternshipCheckinExemption).where(
            InternshipCheckinExemption.tenant_id == _tid(),
            InternshipCheckinExemption.internship_id == record.id,
            InternshipCheckinExemption.status == "PENDING",
            InternshipCheckinExemption.is_deleted.is_(False),
        ).with_for_update())
        if exists:
            raise AppException("DATA_CONFLICT", "当前已有待审核免签申请，请先等待处理")

        item = InternshipCheckinExemption(
            tenant_id=_tid(),
            internship_id=record.id,
            student_id=student.id,
            batch_id=record.batch_id,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            reason=reason,
            evidence_file_id=file_id,
            status="PENDING",
            apply_by_name=student.real_name or str((user or {}).get("realName") or "学生"),
        )
        db.add(item)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise AppException("DATA_CONFLICT", "当前已有待审核免签申请，请刷新后重试") from None
        if file_id:
            file_service.bind_file_biz(
                file_id, "INTERNSHIP_CHECKIN_EXEMPTION", item.id, user=user, db=db
            )
        _trail(db, item, "EXEMPTION_APPLY", user, {
            "batchId": str(record.batch_id or ""),
            "internshipId": str(record.id),
            "startDate": item.start_date,
            "endDate": item.end_date,
            "fileIds": [file_id] if file_id else [],
        })
        db.commit()
        return _row(item, student)


def withdraw(user: dict, exemption_id, body: dict):
    payload = body or {}
    with session() as db:
        record, student, _batch = require_explicit_context(db, user, payload, for_write=True)
        item = db.scalar(select(InternshipCheckinExemption).where(
            InternshipCheckinExemption.id == _as_id(exemption_id),
            InternshipCheckinExemption.tenant_id == _tid(),
            InternshipCheckinExemption.is_deleted.is_(False),
        ).with_for_update())
        if not item or item.internship_id != record.id or item.student_id != student.id:
            raise no_permission("只能撤回本人的免签申请")
        expected = payload.get("expectedVersion")
        if expected is None or int(expected) != int(item.version or 0):
            raise AppException("DATA_CONFLICT", "免签申请已变化，请刷新后重试")
        if item.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核免签申请可撤回")
        item.status = "WITHDRAWN"
        item.version = int(item.version or 0) + 1
        _trail(db, item, "EXEMPTION_WITHDRAW", user)
        db.commit()
        return _row(item, student)


def list_for_teacher(page: int, page_size: int, *, batch_id, status=None, user=None):
    with session() as db:
        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == int(batch_id),
                InternshipRecord.is_deleted.is_(False),
            ),
            user,
        ).subquery()
        query = select(InternshipCheckinExemption, StudentProfile).join(
            InternshipRecord,
            InternshipRecord.id == InternshipCheckinExemption.internship_id,
        ).join(
            StudentProfile,
            StudentProfile.id == InternshipCheckinExemption.student_id,
        ).where(
            InternshipCheckinExemption.tenant_id == _tid(),
            InternshipCheckinExemption.batch_id == int(batch_id),
            InternshipCheckinExemption.internship_id.in_(select(scoped.c.id)),
            InternshipCheckinExemption.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        status_value = str(status or "").strip().upper()
        if status_value and status_value != "ALL":
            if status_value not in {"PENDING", "APPROVED", "REJECTED", "WITHDRAWN"}:
                raise AppException("VALIDATION_ERROR", "免签状态不合法")
            query = query.where(InternshipCheckinExemption.status == status_value)
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = db.execute(
            query.order_by(InternshipCheckinExemption.id.desc())
            .offset((max(1, int(page)) - 1) * int(page_size))
            .limit(int(page_size))
        ).all()
        return [_row(item, student) for item, student in rows], total


def review(exemption_id, body: dict, user: dict):
    from app.modules.internship.services.internship_scope import assert_internship_record_scope
    payload = body or {}
    action = str(payload.get("action") or "").strip().upper()
    if action not in {"APPROVE", "REJECT"}:
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE 或 REJECT")
    comment = str(payload.get("comment") or "").strip()
    if action == "REJECT" and len(comment) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因不少于5个字")
    with session() as db:
        item = db.scalar(select(InternshipCheckinExemption).where(
            InternshipCheckinExemption.id == _as_id(exemption_id),
            InternshipCheckinExemption.tenant_id == _tid(),
            InternshipCheckinExemption.is_deleted.is_(False),
        ).with_for_update())
        if not item:
            raise AppException("NOT_FOUND", "免签申请不存在", http_status=404)
        record = assert_internship_record_scope(
            db, item.internship_id, user, "审核免签申请", lock=True)
        expected = payload.get("expectedVersion")
        if expected is None or int(expected) != int(item.version or 0):
            raise AppException("DATA_CONFLICT", "免签申请已变化，请刷新后重试")
        if item.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核免签申请可处理")
        item.status = "APPROVED" if action == "APPROVE" else "REJECTED"
        item.review_by_name = str((user or {}).get("realName") or "教师")
        item.review_comment = comment or None
        item.reviewed_at = datetime.utcnow()
        item.version = int(item.version or 0) + 1
        _trail(db, item, f"EXEMPTION_{action}", user, {
            "batchId": str(record.batch_id or ""),
            "internshipId": str(record.id),
            "reason": comment,
        })
        student = db.get(StudentProfile, item.student_id)
        db.commit()
        return _row(item, student)
