"""企业沟通记录（07 整改方案 §5.1）。

校内指导教师/学院负责人围绕某企业、岗位或学生形成的正式业务记录（非普通备注、非即时聊天）。
owner：教师对本人指导学生相关沟通；管理端全校；作废走状态位（status=VOIDED，不物理删）。
后续事项(follow_up_required)可标记完成。审计走 InternshipAuditTrail(target_type=COMMUNICATION)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import (EmpCompany, InternshipAuditTrail, InternshipCommunicationLog,
                        InternshipRecord, StudentProfile)
from app.services.db_service import _as_id, _iso, _tid, session

TYPE_LABEL = {"PHONE": "电话", "WECHAT": "微信", "EMAIL": "邮件", "ONSITE": "现场",
              "MEETING": "会议", "ENTERPRISE_FEEDBACK": "企业反馈"}


def _op_name(user=None):
    return (user or get_current_user_ctx() or {}).get("realName") or "系统"


def _trail(db, cid, action, detail=None, user=None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=cid, target_type="COMMUNICATION", action=action,
        operator_name=_op_name(user), detail_json=detail or {}, occurred_at=datetime.utcnow()))


def _get(db, cid):
    c = db.get(InternshipCommunicationLog, _as_id(cid))
    if not c or c.is_deleted or c.tenant_id != _tid():
        raise not_found("沟通记录不存在或不在当前数据范围内")
    return c


def _scope_ok(db, c, user):
    """SCOPED 教师：沟通关联的实习学生在本人范围内，或本人经办(advisor_name)。管理端放行。"""
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    scope = _current_scope(user)
    if scope.get("mode") != "SCOPED":
        return True
    if c.internship_id:
        rec = db.get(InternshipRecord, c.internship_id)
        stu = db.get(StudentProfile, rec.student_id) if rec else None
        if rec and stu and _rec_in_scope(scope, db, rec, stu):
            return True
    return (c.advisor_name or "") in (scope.get("advisorNames") or set())


def _row(c):
    return {
        "id": str(c.id), "enterpriseId": str(c.enterprise_id),
        "internshipId": str(c.internship_id) if c.internship_id else "",
        "studentId": str(c.student_id) if c.student_id else "",
        "communicationType": c.communication_type,
        "communicationTypeLabel": TYPE_LABEL.get(c.communication_type, c.communication_type),
        "direction": c.direction, "contactName": c.contact_name_snapshot or "",
        "advisorName": c.advisor_name or "", "occurredAt": _iso(c.occurred_at) or "",
        "summary": c.summary or "", "result": c.result or "",
        "followUpRequired": c.follow_up_required, "followUpDueAt": _iso(c.follow_up_due_at) or "",
        "followUpDone": c.follow_up_done, "fileId": c.file_id or "", "status": c.status,
        "createdAt": _iso(c.created_at) or "",
    }


def list_communications(page, page_size, enterprise_id=None, student_id=None, status=None,
                        batch_id=None, user=None):
    from app.modules.internship.services.internship_batch_context import batch_record_ids
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    scope = _current_scope(user)
    scoped = scope.get("mode") == "SCOPED"
    names = scope.get("advisorNames") or set()
    with session() as db:
        _, record_ids = batch_record_ids(db, batch_id)
        if not record_ids:
            return [], 0
        q = select(InternshipCommunicationLog).where(
            InternshipCommunicationLog.tenant_id == _tid(),
            InternshipCommunicationLog.is_deleted.is_(False),
            InternshipCommunicationLog.internship_id.in_(record_ids),
        )
        if enterprise_id:
            q = q.where(InternshipCommunicationLog.enterprise_id == int(enterprise_id))
        if student_id:
            q = q.where(InternshipCommunicationLog.student_id == int(student_id))
        if status:
            q = q.where(InternshipCommunicationLog.status == status)
        rows = db.scalars(q.order_by(InternshipCommunicationLog.id.desc())).all()
        items = []
        for c in rows:
            if scoped:
                ok = False
                if c.internship_id:
                    rec = db.get(InternshipRecord, c.internship_id)
                    stu = db.get(StudentProfile, rec.student_id) if rec else None
                    ok = bool(rec and stu and _rec_in_scope(scope, db, rec, stu))
                if not ok and (c.advisor_name or "") not in names:
                    continue
            items.append(_row(c))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_communication(cid, user=None):
    with session() as db:
        c = _get(db, cid)
        if not _scope_ok(db, c, user):
            raise no_permission("不在当前数据范围内")
        item = _row(c)
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_type == "COMMUNICATION",
            InternshipAuditTrail.target_id == c.id).order_by(InternshipAuditTrail.id)).all()
        item["auditTrail"] = [{"action": t.action, "operator": t.operator_name or "",
                               "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at) or ""}
                              for t in trail]
        return item


def create_communication(body, user=None):
    body = body or {}
    enterprise_id = body.get("enterpriseId")
    if not enterprise_id:
        raise AppException("VALIDATION_ERROR", "必须关联企业")
    if not body.get("internshipId"):
        # 列表按批次 internship_id 过滤；无关联记录会登记成功却永不进批次台账
        raise AppException("VALIDATION_ERROR", "必须关联实习学生记录 internshipId")
    summary = (body.get("summary") or "").strip()
    if len(summary) < 2:
        raise AppException("VALIDATION_ERROR", "沟通摘要不少于 2 个字符")
    ctype = (body.get("communicationType") or "PHONE").upper()
    if ctype not in TYPE_LABEL:
        raise AppException("VALIDATION_ERROR", "沟通方式不合法")
    direction = (body.get("direction") or "SCHOOL").upper()
    with session() as db:
        company = db.get(EmpCompany, _as_id(enterprise_id))
        if not company or company.is_deleted or company.tenant_id != _tid():
            raise not_found("关联企业不存在或不在当前数据范围内")
        internship_id = int(body["internshipId"])
        rec = db.get(InternshipRecord, internship_id)
        if not rec or rec.is_deleted or rec.tenant_id != _tid():
            raise not_found("关联实习记录不存在")
        if body.get("batchId") is not None and str(body.get("batchId")).strip() != "":
            from app.modules.internship.services.internship_batch_context import parse_required_batch_id
            bid = parse_required_batch_id(body.get("batchId"))
            if int(rec.batch_id or 0) != bid:
                raise AppException("DATA_CONFLICT", "实习记录不属于当前批次")
        student_id = rec.student_id
        stu = db.get(StudentProfile, student_id)
        from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            raise no_permission("关联学生不在当前数据范围内")
        c = InternshipCommunicationLog(
            tenant_id=_tid(), enterprise_id=int(enterprise_id), internship_id=internship_id,
            student_id=student_id,
            position_id=int(body["positionId"]) if body.get("positionId") else None,
            communication_type=ctype, direction=direction,
            contact_id=int(body["contactId"]) if body.get("contactId") else None,
            contact_name_snapshot=(body.get("contactName") or "").strip() or None,
            advisor_name=_op_name(user), occurred_at=datetime.utcnow(), summary=summary,
            result=(body.get("result") or "").strip() or None,
            follow_up_required=bool(body.get("followUpRequired")),
            follow_up_owner_id=None,
            file_id=(body.get("fileId") or "").strip() or None,
            created_by=None)
        db.add(c)
        db.flush()
        _trail(db, c.id, "CREATE", {"enterpriseId": str(enterprise_id), "type": ctype}, user)
        db.commit()
        return _row(c)


def void_communication(cid, reason="", user=None):
    reason = (reason or "").strip()
    if len(reason) < 2:
        raise AppException("VALIDATION_ERROR", "作废原因不少于 2 个字符")
    with session() as db:
        c = _get(db, cid)
        if not _scope_ok(db, c, user):
            raise no_permission("不在当前数据范围内")
        if c.status == "VOIDED":
            raise AppException("DATA_CONFLICT", "该沟通记录已作废")
        c.status = "VOIDED"
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, "VOID", {"reason": reason}, user)
        db.commit()
        return _row(c)


def complete_follow_up(cid, user=None):
    with session() as db:
        c = _get(db, cid)
        if not _scope_ok(db, c, user):
            raise no_permission("不在当前数据范围内")
        if not c.follow_up_required:
            raise AppException("DATA_CONFLICT", "该记录无后续事项")
        if c.follow_up_done:
            raise AppException("DATA_CONFLICT", "后续事项已完成")
        c.follow_up_done = True
        _trail(db, c.id, "FOLLOW_UP_DONE", {}, user)
        db.commit()
        return _row(c)
