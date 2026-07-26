"""实习请假批次化权威写入口。

学生撤回、销假与教师超期办结均强制行锁和 expectedVersion，避免审批、定时扫描、
风险关闭与旧页面并发覆盖。新建沿用既有日期、附件、状态和待办校验。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import InternshipAuditTrail, InternshipLeave, InternshipRecord, RiskRecord, StudentProfile
from app.modules.internship.services import internship_leave_service as legacy
from app.services.db_service import _as_id, _tid, session


def _expected(raw, current: int) -> None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise AppException("DATA_CONFLICT", "缺少有效请假记录版本，请刷新后重试")
    if value != int(current or 0):
        raise AppException("DATA_CONFLICT", "请假记录已被其他用户处理，请刷新后重试")


def _locked(db, leave_id) -> InternshipLeave:
    row = db.scalar(select(InternshipLeave).where(
        InternshipLeave.id == _as_id(leave_id),
        InternshipLeave.tenant_id == _tid(),
        InternshipLeave.is_deleted.is_(False),
    ).with_for_update())
    if not row:
        raise not_found("请假申请不存在")
    return row


def list_my(user: dict) -> list[dict]:
    return legacy.my_leaves(user)


def apply(user: dict, body: dict) -> dict:
    return legacy.apply(user, body or {})


def withdraw(user: dict, leave_id, expected_version) -> dict:
    with session() as db:
        row = _locked(db, leave_id)
        record, _student = legacy._student_record(db, user, for_write=True)
        if not record or row.internship_id != record.id:
            raise no_permission("只能撤回本人的请假申请")
        _expected(expected_version, row.version)
        if row.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审批请假可撤回")
        row.status = "WITHDRAWN"
        row.version = int(row.version or 0) + 1
        legacy._trail(db, row.id, "WITHDRAW_VERSIONED", {
            "newVersion": int(row.version or 0),
        }, operator=legacy._op_name(user))
        from app.modules.internship.services import internship_todo_helper as todo
        todo.todo_done(db, biz_id=row.id, todo_type=todo.TODO_LEAVE)
        db.commit()
        return {
            "id": str(row.id), "status": row.status,
            "statusLabel": legacy.STATUS_LABEL[row.status],
            "version": int(row.version or 0),
        }


def return_my(user: dict, leave_id, body: dict) -> dict:
    payload = body or {}
    note = str(payload.get("returnNote") or payload.get("note") or "").strip()
    if len(note) < 2:
        raise AppException("VALIDATION_ERROR", "销假说明不少于2个字")
    file_id = legacy._validate_file(payload.get("fileId") or payload.get("returnFileId"))
    with session() as db:
        row = _locked(db, leave_id)
        record, _student = legacy._student_record(db, user, for_write=True)
        if not record or row.internship_id != record.id:
            raise no_permission("只能办理本人的实习销假")
        _expected(payload.get("expectedVersion"), row.version)
        if row.status not in ("APPROVED", "OVERDUE"):
            raise AppException("DATA_CONFLICT", "仅已通过或超期请假可销假")
        was_overdue = row.status == "OVERDUE"
        row.status = "RETURNED"
        row.returned_at = datetime.utcnow()
        row.return_note = note
        row.return_file_id = file_id
        row.version = int(row.version or 0) + 1
        legacy._trail(db, row.id, "RETURN_VERSIONED", {
            "wasOverdue": was_overdue,
            "hasFile": bool(file_id),
            "note": note[:500],
            "newVersion": int(row.version or 0),
        }, operator=legacy._op_name(user))
        db.commit()
        return {
            "id": str(row.id), "status": row.status,
            "statusLabel": legacy.STATUS_LABEL[row.status],
            "wasOverdue": was_overdue,
            "version": int(row.version or 0),
        }


def list_teacher_overdue(batch_id, user: dict) -> dict:
    """教师本人数据范围内，待确认销假或仍超期的记录。"""
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        rows = db.scalars(select(InternshipLeave).where(
            InternshipLeave.tenant_id == _tid(),
            InternshipLeave.status.in_(("RETURNED", "OVERDUE")),
            InternshipLeave.is_deleted.is_(False),
        ).order_by(InternshipLeave.id.desc())).all()
        items = []
        scope = _current_scope(user)
        for row in rows:
            record = db.get(InternshipRecord, row.internship_id)
            student = db.get(StudentProfile, row.student_id)
            if not record or str(record.batch_id or "") != str(batch_id or ""):
                continue
            if not _rec_in_scope(scope, db, record, student):
                continue
            items.append(legacy._row(db, row, record, student))
        return {"list": items, "total": len(items), "batchId": str(batch_id or "")}


def ack_overdue_return(user: dict, leave_id, body: dict) -> dict:
    payload = body or {}
    note = str(payload.get("note") or payload.get("comment") or "").strip()
    if len(note) < 2:
        raise AppException("VALIDATION_ERROR", "办结说明不少于2个字")
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        row = _locked(db, leave_id)
        record = db.get(InternshipRecord, row.internship_id)
        student = db.get(StudentProfile, row.student_id)
        if not _rec_in_scope(_current_scope(user), db, record, student):
            raise no_permission("只能办结本人指导学生的请假")
        _expected(payload.get("expectedVersion"), row.version)
        if row.status not in ("RETURNED", "OVERDUE"):
            raise AppException("DATA_CONFLICT", "仅超期未归或已销假记录可办结确认")
        if row.status == "OVERDUE":
            row.status = "RETURNED"
            row.returned_at = datetime.utcnow()
            row.return_note = note[:500]
        row.version = int(row.version or 0) + 1
        closed = 0
        risks = db.scalars(select(RiskRecord).where(
            RiskRecord.tenant_id == _tid(),
            RiskRecord.internship_id == row.internship_id,
            RiskRecord.risk_code == "INT-R06",
            RiskRecord.status.in_(("PENDING_HANDLE", "PROCESSING")),
            RiskRecord.is_deleted.is_(False),
        ).with_for_update()).all()
        for risk in risks:
            risk.status = "CLOSED"
            risk.last_follow_at = datetime.utcnow()
            risk.last_follow_note = f"销假办结：{note}"[:500]
            risk.version = int(risk.version or 0) + 1
            closed += 1
            db.add(InternshipAuditTrail(
                tenant_id=_tid(), target_id=risk.id, target_type="RISK", action="CLOSE",
                operator_name=legacy._op_name(user),
                detail_json={"result": "RESOLVED", "from": "leave_ack_versioned", "leaveId": str(row.id)},
                occurred_at=datetime.utcnow()))
        legacy._trail(db, row.id, "ACK_OVERDUE_RETURN_VERSIONED", {
            "note": note[:500], "risksClosed": closed,
            "newVersion": int(row.version or 0),
        }, operator=legacy._op_name(user))
        db.commit()
        return {
            "id": str(row.id), "status": row.status,
            "statusLabel": legacy.STATUS_LABEL.get(row.status, row.status),
            "risksClosed": closed, "version": int(row.version or 0),
        }
