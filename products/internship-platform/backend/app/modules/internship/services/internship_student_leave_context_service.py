"""实习请假批次化权威写入口。

学生撤回、销假与教师超期办结均强制行锁和 expectedVersion，避免审批、定时扫描、
风险关闭与旧页面并发覆盖。新建沿用既有日期、附件、状态和待办校验。
"""
from __future__ import annotations

from app.core.tenant_scoped import tenant_get
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import InternshipAuditTrail, InternshipLeave, InternshipRecord, RiskRecord, StudentProfile
from app.modules.internship.services import internship_leave_service as legacy
from app.modules.internship.services.internship_student_context_guard import (
    require_context_fields,
    require_explicit_context,
)
from app.services.db_service import _as_id, _tid, session


def _expected(raw, current: int) -> None:
    value = legacy._version(raw)
    if value != int(current or 0):
        raise AppException("DATA_CONFLICT", "请假记录已被其他用户处理，请刷新后重试", http_status=409)


def _locked(db, leave_id, *, record_id=None) -> InternshipLeave:
    return legacy._get(db, leave_id, for_write=True, expected_record_id=record_id)


def list_my(user: dict, *, batch_id=None, internship_id=None) -> list[dict]:
    if batch_id is None and internship_id is None:
        return legacy.my_leaves(user)
    with session() as db:
        record, student, _batch_id = require_explicit_context(
            db,
            user,
            {"batchId": batch_id, "internshipId": internship_id},
            for_write=False,
        )
        rows = db.scalars(select(InternshipLeave).where(
            InternshipLeave.tenant_id == _tid(),
            InternshipLeave.internship_id == record.id,
            InternshipLeave.is_deleted.is_(False),
        ).order_by(InternshipLeave.id.desc())).all()
        name = legacy._enterprise_names(db, [record]).get(record.id, '')
        acknowledged = legacy._acknowledged_returns(db, rows)
        return [{**legacy._row(row, record, student, db=db, user=user, enterprise_name=name),
                 'returnAcknowledged': row.id in acknowledged} for row in rows]


def apply(user: dict, body: dict) -> dict:
    require_context_fields(body or {})
    return legacy.apply(user, body or {})


def get_my(user: dict, leave_id, *, batch_id, internship_id) -> dict:
    with session() as db:
        record, student, _ = require_explicit_context(db, user,
            {'batchId': batch_id, 'internshipId': internship_id}, for_write=False)
        row = db.scalar(select(InternshipLeave).where(
            InternshipLeave.id == _as_id(leave_id), InternshipLeave.tenant_id == _tid(),
            InternshipLeave.internship_id == record.id, InternshipLeave.student_id == student.id,
            InternshipLeave.is_deleted.is_(False)))
        if not row:
            raise not_found('本人请假申请不存在')
        return legacy._detail(db, row, record, student, user)


def resubmit(user: dict, leave_id, body: dict) -> dict:
    payload = body or {}
    values = legacy._application_values(payload)
    with session() as db:
        record, student, _ = require_explicit_context(db, user, payload, for_write=True)
        row = _locked(db, leave_id, record_id=record.id)
        if row.internship_id != record.id or row.student_id != student.id:
            raise not_found('本人请假申请不存在')
        _expected(payload.get('expectedVersion'), row.version)
        if row.status not in ('REJECTED', 'NEEDS_REVISION'):
            raise AppException('DATA_CONFLICT', '仅已退回或驳回的请假可在原单补正重交', http_status=409)
        if db.scalar(select(InternshipLeave.id).where(
                InternshipLeave.tenant_id == _tid(), InternshipLeave.internship_id == record.id,
                InternshipLeave.status == 'PENDING', InternshipLeave.is_deleted.is_(False),
                InternshipLeave.id != row.id).with_for_update().limit(1)):
            raise AppException('DATA_CONFLICT', '已有待审批的请假，请先等待处理或撤回', http_status=409)
        legacy._assert_leave_period(record, values)
        file_id = legacy._validate_file(payload.get('fileId') or payload.get('evidenceFileId'), user)
        if legacy._evidence_required(values['leave_type'], values['days']) and not file_id:
            raise AppException('VALIDATION_ERROR', legacy._evidence_requirement_label(values['leave_type'], values['days']))
        previous = legacy._snapshot(row)
        for key, value in values.items():
            setattr(row, key, value)
        row.file_id, row.status = file_id, 'PENDING'
        row.review_at = row.review_by_name = row.review_comment = None
        row.version = int(row.version or 0) + 1
        legacy._bind_evidence(db, row, record, student, file_id, user)
        legacy._trail(db, row.id, 'RESUBMIT_VERSIONED', {
            'previous': previous, 'snapshot': legacy._snapshot(row),
        }, operator=legacy._op_name(user))
        from app.modules.internship.services import internship_todo_helper as todo
        todo.push_leave_todo(db, row, record)
        from sqlalchemy.exc import IntegrityError
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if 'uk_ix_leave_active_pending' not in str(exc.orig):
                raise
            raise AppException('DATA_CONFLICT', '已有待审批的请假，请先等待处理或撤回', http_status=409) from exc
        return {**legacy._row(row, record, student, db=db, preloaded=True), 'id': str(row.id)}


def withdraw(user: dict, leave_id, body: dict) -> dict:
    payload = body or {}
    with session() as db:
        record, _student, _batch_id = require_explicit_context(
            db, user, payload, for_write=True)
        row = _locked(db, leave_id, record_id=record.id)
        if not record or row.internship_id != record.id:
            raise no_permission("只能撤回本人的请假申请")
        _expected(payload.get("expectedVersion"), row.version)
        if row.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审批请假可撤回")
        row.status = "WITHDRAWN"
        row.version = int(row.version or 0) + 1
        legacy._trail(db, row.id, "WITHDRAW_VERSIONED", {
            "newVersion": int(row.version or 0),
        }, operator=legacy._op_name(user))
        from app.services.system_leave_policy import cancel
        cancel(db, row.tenant_id, row.id)
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
    if not 2 <= len(note) <= 500:
        raise AppException("VALIDATION_ERROR", "销假说明须填写2至500字")
    with session() as db:
        record, student, _batch_id = require_explicit_context(
            db, user, payload, for_write=True)
        row = _locked(db, leave_id, record_id=record.id)
        if not record or row.internship_id != record.id:
            raise no_permission("只能办理本人的实习销假")
        _expected(payload.get("expectedVersion"), row.version)
        if row.status not in ("APPROVED", "OVERDUE"):
            raise AppException("DATA_CONFLICT", "仅已通过或超期请假可销假")
        file_id = legacy._validate_file(payload.get("fileId") or payload.get("returnFileId"), user)
        was_overdue = row.status == "OVERDUE"
        row.status = "RETURNED"
        row.returned_at = datetime.utcnow()
        row.return_note = note
        row.return_file_id = file_id
        row.version = int(row.version or 0) + 1
        legacy._bind_evidence(db, row, record, student, file_id, user)
        released = legacy._release_leave_checkins(db, row)
        legacy._trail(db, row.id, "RETURN_VERSIONED", {
            "wasOverdue": was_overdue,
            "hasFile": bool(file_id),
            "note": note[:500],
            "newVersion": int(row.version or 0),
            "attendanceReleased": released,
        }, operator=legacy._op_name(user))
        from app.modules.internship.services import internship_todo_helper as todo
        todo.push_leave_return_todo(db, row, record)
        db.commit()
        return {
            "id": str(row.id), "status": row.status,
            "statusLabel": legacy.STATUS_LABEL[row.status],
            "wasOverdue": was_overdue,
            "version": int(row.version or 0),
        }


def list_teacher_overdue(batch_id, user: dict, page=1, page_size=20, keyword=None) -> dict:
    """教师本人数据范围内，待确认销假或仍超期的记录。"""
    items, total = legacy.list_leaves(page, page_size, batch_id=batch_id, keyword=keyword,
                                     user=user, return_pending=True)
    return {"list": items, "total": total, "batchId": str(batch_id or ""),
            "page": page, "pageSize": page_size, "hasMore": page * page_size < total}


def ack_overdue_return(user: dict, leave_id, body: dict) -> dict:
    payload = body or {}
    note = str(payload.get("note") or payload.get("comment") or "").strip()
    if not 2 <= len(note) <= 500:
        raise AppException("VALIDATION_ERROR", "办结说明须填写2至500字")
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        row = _locked(db, leave_id)
        record = tenant_get(db, InternshipRecord, row.internship_id)
        student = tenant_get(db, StudentProfile, row.student_id)
        if not record or not student or record.student_id != row.student_id:
            raise no_permission("请假关联的实习与学生不属于当前学校或不一致")
        if not _rec_in_scope(_current_scope(user), db, record, student):
            raise no_permission("只能办结本人指导学生的请假")
        from app.modules.internship.services.internship_batch_context import assert_record_batch, parse_required_batch_id
        assert_record_batch(record, parse_required_batch_id(payload.get('batchId')))
        _expected(payload.get("expectedVersion"), row.version)
        if db.scalar(select(InternshipAuditTrail.id).where(
                InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == 'LEAVE',
                InternshipAuditTrail.target_id == row.id, InternshipAuditTrail.action == 'ACK_OVERDUE_RETURN_VERSIONED').limit(1)):
            raise AppException('DATA_CONFLICT', '本次销假已经办结，请刷新查看结果', http_status=409)
        if row.status not in ("RETURNED", "OVERDUE"):
            raise AppException("DATA_CONFLICT", "仅超期未归或已销假记录可办结确认")
        if row.status == "OVERDUE":
            row.status = "RETURNED"
            row.returned_at = datetime.utcnow()
            row.return_note = note[:500]
        row.version = int(row.version or 0) + 1
        released = legacy._release_leave_checkins(db, row)
        closed = 0
        risks = db.scalars(select(RiskRecord).where(
            RiskRecord.tenant_id == _tid(),
            RiskRecord.internship_id == row.internship_id,
            RiskRecord.source_type == "LEAVE",
            RiskRecord.source_id == row.id,
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
            "attendanceReleased": released,
        }, operator=legacy._op_name(user))
        from app.modules.internship.services import internship_todo_helper as todo
        todo.todo_done(db, biz_id=row.id, todo_type=todo.TODO_LEAVE_RETURN)
        db.commit()
        return {
            "id": str(row.id), "status": row.status,
            "statusLabel": legacy.STATUS_LABEL.get(row.status, row.status),
            "risksClosed": closed, "version": int(row.version or 0),
        }
