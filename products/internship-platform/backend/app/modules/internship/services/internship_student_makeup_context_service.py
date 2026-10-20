"""学生本人批次化补卡权威入口。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import InternshipCheckin, InternshipMakeup
from app.modules.internship.services import internship_makeup_service as legacy
from app.modules.internship.services.internship_student_context_guard import (
    require_explicit_context,
)
from app.services.db_service import _as_id, _tid, session

_ALLOWED_TYPES = {"MISSING", "OUT_OF_RANGE"}


def _parse_date(raw: str) -> date:
    try:
        value = date.fromisoformat(str(raw or "").strip()[:10])
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "补卡日期格式无效")
    if value > date.today():
        raise AppException("VALIDATION_ERROR", "不能申请未来日期补卡")
    return value


def _expected(raw, current: int) -> None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise AppException("DATA_CONFLICT", "缺少有效补卡记录版本，请刷新后重试")
    if value != int(current or 0):
        raise AppException("DATA_CONFLICT", "补卡申请已被其他用户处理，请刷新后重试")


def _locked(db, makeup_id) -> InternshipMakeup:
    row = db.scalar(select(InternshipMakeup).where(
        InternshipMakeup.id == _as_id(makeup_id),
        InternshipMakeup.tenant_id == _tid(),
        InternshipMakeup.is_deleted.is_(False),
    ).with_for_update())
    if not row:
        raise not_found("补卡申请不存在")
    return row


def list_my(user: dict, *, batch_id=None, internship_id=None) -> dict:
    if batch_id is None and internship_id is None:
        return legacy.my_makeups(user)
    with session() as db:
        record, student, _batch_id = require_explicit_context(
            db,
            user,
            {"batchId": batch_id, "internshipId": internship_id},
            for_write=False,
        )
        rows = db.scalars(select(InternshipMakeup).where(
            InternshipMakeup.tenant_id == _tid(),
            InternshipMakeup.internship_id == record.id,
            InternshipMakeup.is_deleted.is_(False),
        ).order_by(InternshipMakeup.id.desc())).all()
        return {
            "items": [
                legacy._row(row, record, student, db=db, user=user)
                for row in rows
            ],
            "total": len(rows),
        }


def apply(user: dict, body: dict) -> dict:
    payload = body or {}
    checkin_day = _parse_date(payload.get("checkinDate"))
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "补卡事由不少于5个字")
    makeup_type = str(payload.get("makeupType") or "MISSING").upper()
    if makeup_type not in _ALLOWED_TYPES:
        raise AppException("VALIDATION_ERROR", "补卡类型无效")
    evidence_file_id = legacy._validate_evidence_file(
        payload.get("evidenceFileId") or payload.get("fileId"))
    if legacy._evidence_required(makeup_type) and not evidence_file_id:
        raise AppException("VALIDATION_ERROR", legacy._evidence_requirement_label(makeup_type))
    with session() as db:
        record, student, _batch_id = require_explicit_context(
            db, user, payload, for_write=True)
        if record.status not in ("ONBOARD", "ASSESSING"):
            raise AppException("DATA_CONFLICT", "仅在岗或考核中的学生可以申请补卡")
        start = getattr(record, "intern_start_date", None)
        end = getattr(record, "intern_end_date", None)
        start_day = start.date() if hasattr(start, "date") else (date.fromisoformat(str(start)[:10]) if start else None)
        end_day = end.date() if hasattr(end, "date") else (date.fromisoformat(str(end)[:10]) if end else None)
        if start_day and checkin_day < start_day:
            raise AppException("VALIDATION_ERROR", "补卡日期早于本次实习开始日期")
        if end_day and checkin_day > end_day:
            raise AppException("VALIDATION_ERROR", "补卡日期晚于本次实习结束日期")
        date_text = checkin_day.isoformat()
        existing_checkin = db.scalar(select(InternshipCheckin).where(
            InternshipCheckin.tenant_id == _tid(),
            InternshipCheckin.internship_id == record.id,
            InternshipCheckin.checkin_date == date_text,
        ).with_for_update())
        if existing_checkin:
            label = "请假留痕" if existing_checkin.result == "LEAVE" else "打卡记录"
            raise AppException("DATA_CONFLICT", f"该日期已有{label}，不能重复申请补卡")
        existing_makeup = db.scalar(select(InternshipMakeup).where(
            InternshipMakeup.tenant_id == _tid(),
            InternshipMakeup.internship_id == record.id,
            InternshipMakeup.checkin_date == date_text,
            InternshipMakeup.status.in_(("PENDING", "APPROVED")),
            InternshipMakeup.is_deleted.is_(False),
        ).with_for_update())
        if existing_makeup:
            raise AppException("DATA_CONFLICT", "该日期已有办理中或已通过的补卡记录")
        row = InternshipMakeup(
            tenant_id=_tid(), internship_id=record.id, student_id=record.student_id,
            checkin_date=date_text, makeup_type=makeup_type, reason=reason,
            status="PENDING", apply_by_name=student.real_name if student else legacy._op_name(user),
        )
        db.add(row)
        db.flush()
        if evidence_file_id:
            from app.services import file_service
            file_service.bind_file_biz(
                evidence_file_id, "INTERNSHIP", str(row.id), user=user, db=db)
        legacy._trail(db, row.id, "APPLY_CONTEXT", {
            "date": date_text,
            "makeupType": makeup_type,
            "evidenceFileId": evidence_file_id or "",
            "evidenceRequired": legacy._evidence_required(makeup_type),
            "newVersion": int(row.version or 0),
        }, operator=row.apply_by_name or "学生")
        db.commit()
        return {
            "id": str(row.id), "status": row.status,
            "statusLabel": legacy.STATUS_LABEL[row.status],
            "version": int(row.version or 0),
            "hasEvidence": bool(evidence_file_id),
        }


def withdraw(user: dict, makeup_id, body: dict) -> dict:
    payload = body or {}
    with session() as db:
        row = _locked(db, makeup_id)
        record, _student, _batch_id = require_explicit_context(
            db, user, payload, for_write=True)
        if not record or row.internship_id != record.id:
            raise no_permission("只能撤回本人的补卡申请")
        _expected(payload.get("expectedVersion"), row.version)
        if row.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核补卡申请可撤回")
        row.status = "WITHDRAWN"
        row.version = int(row.version or 0) + 1
        legacy._trail(db, row.id, "WITHDRAW_CONTEXT", {
            "newVersion": int(row.version or 0),
        }, operator=legacy._op_name(user))
        db.commit()
        return {
            "id": str(row.id), "status": row.status,
            "statusLabel": legacy.STATUS_LABEL[row.status],
            "version": int(row.version or 0),
        }
