"""岗位实习 · 请假工作流（P1-Stage3）。

学生（移动端本人）发起/撤回；指导教师（PC 管理端，owner 校验 + 数据范围）审批/驳回。
状态机：PENDING →(教师) APPROVED/REJECTED；PENDING →(学生) WITHDRAWN。
证明附件走文件中心 file_id。全程审计 target_type=LEAVE。
数据范围/owner：复用 internship_service 的 _current_scope / _rec_in_scope。
病假或连续三天及以上请假必须上传证明；存在证明时审批人须先真实查看并留下审计。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAuditTrail, InternshipCheckin, InternshipLeave,
                        InternshipRecord, RiskRecord, StudentProfile)
from app.services.db_service import _as_id, _iso, _tid, session

STATUS_LABEL = {"PENDING": "待审批", "APPROVED": "已通过", "REJECTED": "已驳回", "WITHDRAWN": "已撤回"}
STATUS_LABEL.update({"RETURNED": "已销假", "OVERDUE": "超期未销假"})
TYPE_LABEL = {"SICK": "病假", "PERSONAL": "事假", "OTHER": "其他"}
LONG_LEAVE_DAYS = 3.0


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _actor_id(user) -> str:
    return str((user or {}).get("userId") or (user or {}).get("loginName") or "").strip()


def _trail(db, lid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=lid, target_type="LEAVE",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, lid) -> InternshipLeave:
    lv = db.get(InternshipLeave, _as_id(lid))
    if not lv or lv.is_deleted or lv.tenant_id != _tid():
        raise not_found("请假申请不存在")
    return lv


def _student_record(db, user, *, batch_id=None, for_write: bool = False):
    """学生本人实习记录：统一走 resolve_student_internship_context（禁止 .first()）。"""
    from app.modules.internship.services.internship_record_resolver import (
        require_active_student_record,
        resolve_optional_student_record,
    )
    sno = (user or {}).get("studentNo")
    if not sno:
        if for_write:
            raise AppException("VALIDATION_ERROR", "学生身份信息缺失")
        return None, None
    if for_write:
        return require_active_student_record(db, user, batch_id=batch_id, student_no=sno)
    rec, stu, _ctx = resolve_optional_student_record(db, user, batch_id=batch_id, student_no=sno)
    return rec, stu


def _calc_days(start: str, end: str) -> float:
    try:
        d0 = date.fromisoformat(start[:10]); d1 = date.fromisoformat(end[:10])
        return float((d1 - d0).days + 1) if d1 >= d0 else 0.0
    except ValueError:
        return 0.0


def _validate_file(file_id):
    fid = str(file_id or "").strip()
    if not fid:
        return None
    from app.services import file_service
    if not file_service.get_file_meta(fid):
        raise AppException("VALIDATION_ERROR", "证明附件不存在或无权访问，请重新上传")
    return fid


def _evidence_required(leave_type: str | None, days) -> bool:
    try:
        day_count = float(days or 0)
    except (TypeError, ValueError):
        day_count = 0.0
    return str(leave_type or "").upper() == "SICK" or day_count >= LONG_LEAVE_DAYS


def _evidence_requirement_label(leave_type: str | None, days) -> str:
    if str(leave_type or "").upper() == "SICK":
        return "病假必须上传医疗或就诊证明"
    try:
        if float(days or 0) >= LONG_LEAVE_DAYS:
            return "连续3天及以上请假必须上传证明材料"
    except (TypeError, ValueError):
        pass
    return "可选上传请假证明材料"


def _previous_rejection(db, lv: InternshipLeave):
    return db.scalars(select(InternshipLeave).where(
        InternshipLeave.tenant_id == _tid(),
        InternshipLeave.internship_id == lv.internship_id,
        InternshipLeave.leave_type == lv.leave_type,
        InternshipLeave.start_date == lv.start_date,
        InternshipLeave.end_date == lv.end_date,
        InternshipLeave.status == "REJECTED",
        InternshipLeave.id != lv.id,
        InternshipLeave.is_deleted.is_(False),
    ).order_by(InternshipLeave.id.desc())).first()


def _evidence_viewed(db, lv: InternshipLeave, user) -> bool:
    if not lv.file_id:
        return False
    actor_id = _actor_id(user)
    operator = _op_name(user)
    trails = db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_type == "LEAVE",
        InternshipAuditTrail.target_id == lv.id,
        InternshipAuditTrail.action == "EVIDENCE_VIEW",
    ).order_by(InternshipAuditTrail.id.desc())).all()
    for trail in trails:
        detail = trail.detail_json or {}
        try:
            same_version = int(detail.get("version")) == int(lv.version or 0)
        except (TypeError, ValueError):
            same_version = False
        same_file = str(detail.get("evidenceFileId") or "") == str(lv.file_id)
        same_actor = actor_id and str(detail.get("operatorUserId") or "") == actor_id
        if not actor_id:
            same_actor = (trail.operator_name or "") == operator
        if same_version and same_file and same_actor:
            return True
    return False


def _row(lv: InternshipLeave, rec, stu, *, db=None, user=None) -> dict:
    previous = _previous_rejection(db, lv) if db is not None else None
    return {
        "id": str(lv.id), "internId": str(lv.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "",
        "leaveType": lv.leave_type, "leaveTypeLabel": TYPE_LABEL.get(lv.leave_type, lv.leave_type),
        "startDate": lv.start_date, "endDate": lv.end_date, "days": lv.days,
        "reason": lv.reason, "status": lv.status, "statusLabel": STATUS_LABEL.get(lv.status, lv.status),
        "applyBy": lv.apply_by_name or "", "reviewBy": lv.review_by_name or "",
        "reviewComment": lv.review_comment or "", "reviewAt": _iso(lv.review_at) or "",
        "returnedAt": _iso(lv.returned_at) or "", "returnNote": lv.return_note or "",
        "returnFileId": lv.return_file_id or "", "overdue": lv.status == "OVERDUE",
        "version": int(lv.version or 0),
        "createdAt": _iso(lv.created_at) or "", "submittedAt": _iso(lv.created_at) or "",
        "evidenceFileId": lv.file_id or "", "hasEvidence": bool(lv.file_id),
        "evidenceRequired": _evidence_required(lv.leave_type, lv.days),
        "evidenceRequirementLabel": _evidence_requirement_label(lv.leave_type, lv.days),
        "evidenceViewed": _evidence_viewed(db, lv, user) if db is not None and user else False,
        "previousReviewComment": previous.review_comment or "" if previous else "",
        "previousReviewAt": _iso(previous.review_at) or "" if previous else "",
    }


# ═══════════ 学生本人（移动端） ═══════════

def apply(user, body) -> dict:
    b = body or {}
    start, end = str(b.get("startDate") or "").strip(), str(b.get("endDate") or "").strip()
    reason = str(b.get("reason") or "").strip()
    leave_type = str(b.get("leaveType") or "PERSONAL").upper()
    if leave_type not in TYPE_LABEL:
        raise AppException("VALIDATION_ERROR", "请假类型无效")
    if not start or not end or not reason or len(reason) < 2:
        raise AppException("VALIDATION_ERROR", "起止日期与事由必填（事由不少于 2 字）")
    days = _calc_days(start, end)
    if days <= 0:
        raise AppException("VALIDATION_ERROR", "结束日期不能早于开始日期")
    file_id = _validate_file(b.get("fileId") or b.get("evidenceFileId"))
    if _evidence_required(leave_type, days) and not file_id:
        raise AppException("VALIDATION_ERROR", _evidence_requirement_label(leave_type, days))
    with session() as db:
        if b.get("batchId") is not None or b.get("internshipId") is not None:
            from app.modules.internship.services.internship_student_context_guard import (
                require_explicit_context,
            )
            rec, stu, _batch_id = require_explicit_context(
                db, user, b, for_write=True)
        else:
            rec, stu = _student_record(db, user, for_write=True)
        if rec.status not in ("ONBOARD", "ASSESSING"):
            raise AppException("DATA_CONFLICT", "仅在岗或考核中的实习学生可以申请请假")
        dup = db.scalars(select(InternshipLeave).where(
            InternshipLeave.tenant_id == _tid(), InternshipLeave.internship_id == rec.id,
            InternshipLeave.status == "PENDING", InternshipLeave.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "你有待审批的请假申请，请先等待处理或撤回")
        lv = InternshipLeave(tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
                             leave_type=leave_type, start_date=start,
                             end_date=end, days=days, reason=reason, status="PENDING",
                             apply_by_name=(stu.real_name if stu else _op_name(user)), file_id=file_id)
        db.add(lv); db.flush()
        if file_id:
            from app.services import file_service
            file_service.bind_file_biz(file_id, "INTERNSHIP", str(lv.id), user=user, db=db)
        _trail(db, lv.id, "APPLY", {
            "range": f"{start}~{end}", "days": days,
            "leaveType": leave_type, "evidenceFileId": file_id or "",
            "evidenceRequired": _evidence_required(leave_type, days),
        }, operator=lv.apply_by_name or "学生")
        from app.modules.internship.services import internship_todo_helper as ix_todo
        ix_todo.push_leave_todo(db, lv, rec)
        db.commit()
        return {"id": str(lv.id), "status": "PENDING", "statusLabel": "待审批",
                "days": days, "version": int(lv.version or 0), "hasEvidence": bool(file_id)}


def withdraw(user, leave_id) -> dict:
    with session() as db:
        lv = _get(db, leave_id)
        rec, _ = _student_record(db, user, for_write=True)
        if not rec or lv.internship_id != rec.id:
            raise no_permission("只能撤回本人的请假申请")
        if lv.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审批申请可撤回")
        lv.status = "WITHDRAWN"
        lv.version = int(lv.version or 0) + 1
        _trail(db, lv.id, "WITHDRAW", {}, operator=_op_name(user))
        from app.modules.internship.services import internship_todo_helper as ix_todo
        ix_todo.todo_done(db, biz_id=lv.id, todo_type=ix_todo.TODO_LEAVE)
        db.commit()
        return {"id": str(lv.id), "status": "WITHDRAWN"}


def return_my(user, leave_id, body=None) -> dict:
    """Student return confirmation; an overdue leave may be returned but its risk stays auditable."""
    body = body or {}
    note = str(body.get("returnNote") or body.get("note") or "").strip()
    if len(note) < 2:
        raise AppException("VALIDATION_ERROR", "销假说明不少于 2 个字符")
    file_id = _validate_file(body.get("fileId") or body.get("returnFileId"))
    with session() as db:
        lv = _get(db, leave_id)
        rec, _ = _student_record(db, user)
        if not rec or lv.internship_id != rec.id:
            raise no_permission("只能销本人的实习请假")
        if lv.status not in ("APPROVED", "OVERDUE"):
            raise AppException("DATA_CONFLICT", "仅已通过或超期的请假可销假")
        was_overdue = lv.status == "OVERDUE"
        lv.status = "RETURNED"
        lv.returned_at = datetime.utcnow()
        lv.return_note, lv.return_file_id = note, file_id
        lv.version = int(lv.version or 0) + 1
        _trail(db, lv.id, "RETURN", {"wasOverdue": was_overdue, "hasFile": bool(file_id), "note": note},
               operator=_op_name(user))
        db.commit()
        return {"id": str(lv.id), "status": lv.status, "statusLabel": STATUS_LABEL[lv.status],
                "wasOverdue": was_overdue}


def my_leaves(user) -> list[dict]:
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            return []
        rows = db.scalars(select(InternshipLeave).where(
            InternshipLeave.tenant_id == _tid(), InternshipLeave.internship_id == rec.id,
            InternshipLeave.is_deleted.is_(False)).order_by(InternshipLeave.id.desc())).all()
        return [_row(lv, rec, stu, db=db, user=user) for lv in rows]


# ═══════════ 指导教师 / 管理员（PC 管理端，owner + 数据范围） ═══════════

def list_leaves(page, page_size, status=None, keyword=None, batch_id=None, user=None) -> tuple[list[dict], int]:
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        from app.modules.internship.services.internship_batch_context import batch_record_ids
        _, record_ids = batch_record_ids(db, batch_id)
        if not record_ids:
            return [], 0
        q = select(InternshipLeave).where(InternshipLeave.tenant_id == _tid(),
                                          InternshipLeave.is_deleted.is_(False),
                                          InternshipLeave.internship_id.in_(record_ids))
        if status:
            q = q.where(InternshipLeave.status == status)
        rows = db.scalars(q.order_by(InternshipLeave.id.desc())).all()
        scope = _current_scope(user)
        items = []
        for lv in rows:
            rec = db.get(InternshipRecord, lv.internship_id)
            stu = db.get(StudentProfile, lv.student_id)
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not _rec_in_scope(scope, db, rec, stu):
                continue
            items.append(_row(lv, rec, stu, db=db, user=user))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_leave(leave_id, user=None) -> dict:
    from app.services import file_service
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        lv = _get(db, leave_id)
        rec = db.get(InternshipRecord, lv.internship_id)
        stu = db.get(StudentProfile, lv.student_id)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            raise no_permission("该请假申请不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "LEAVE",
            InternshipAuditTrail.target_id == lv.id).order_by(InternshipAuditTrail.id)).all()
        return {**_row(lv, rec, stu, db=db, user=user), "attachment": file_service.attachment_view(lv.file_id),
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                               for t in trail]}


def mark_evidence_viewed(user, leave_id) -> dict:
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    from app.services import file_service
    with session() as db:
        lv = _get(db, leave_id)
        rec = db.get(InternshipRecord, lv.internship_id)
        stu = db.get(StudentProfile, lv.student_id)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            raise no_permission("该请假申请不在你的数据范围内")
        if not lv.file_id or not file_service.get_file_meta(lv.file_id, user=user):
            raise not_found("请假证明不存在或无权查看")
        _trail(db, lv.id, "EVIDENCE_VIEW", {
            "version": int(lv.version or 0),
            "evidenceFileId": str(lv.file_id),
            "operatorUserId": _actor_id(user),
        }, operator=_op_name(user))
        db.commit()
        return {"id": str(lv.id), "version": int(lv.version or 0),
                "evidenceViewed": True, "evidenceFileId": str(lv.file_id)}


def review(user, leave_id, action: str, comment: str = "", *, expected_version=None,
           expected_batch_id=None) -> dict:
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and (not comment or len(comment.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    ver = extract_expected_version({"expectedVersion": expected_version})
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        lv = _get(db, leave_id)
        rec = db.get(InternshipRecord, lv.internship_id)
        stu = db.get(StudentProfile, lv.student_id)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            raise no_permission("只能审批本人指导学生的请假申请")
        from app.modules.internship.services.internship_batch_context import assert_record_batch
        assert_record_batch(rec, expected_batch_id)
        if action == "APPROVE":
            if _evidence_required(lv.leave_type, lv.days) and not lv.file_id:
                raise AppException("DATA_CONFLICT", "该请假按规则必须上传证明材料，当前不能通过")
            if lv.file_id and not _evidence_viewed(db, lv, user):
                raise AppException("DATA_CONFLICT", "请先查看请假证明材料，再执行通过")
        new_status = "APPROVED" if action == "APPROVE" else "REJECTED"
        now = datetime.utcnow()
        new_ver = versioned_update(
            db, InternshipLeave, entity_id=lv.id, tenant_id=_tid(), expected_version=ver,
            values={
                "status": new_status, "review_by_name": _op_name(user),
                "review_at": now, "review_comment": (comment or "").strip() or None,
            },
            expected_status="PENDING")
        leave_days = 0
        if action == "APPROVE":
            db.refresh(lv)
            leave_days = _write_leave_checkins(db, lv)
        _trail(db, lv.id, f"REVIEW_{action}", {
            "comment": (comment or "").strip(),
            "leaveCheckins": leave_days,
            "evidenceFileId": str(lv.file_id or ""),
            "evidenceViewed": bool(lv.file_id),
        }, operator=_op_name(user))
        from app.modules.internship.services import internship_todo_helper as ix_todo
        ix_todo.todo_done(db, biz_id=lv.id, todo_type=ix_todo.TODO_LEAVE)
        db.commit()
        return {"id": str(lv.id), "status": new_status, "statusLabel": STATUS_LABEL[new_status],
                "leaveDays": leave_days, "version": new_ver}


def _write_leave_checkins(db, lv) -> int:
    """请假通过后按日期区间写 result=LEAVE 的打卡留痕（幂等：已有当日打卡则跳过）。"""
    try:
        d0 = date.fromisoformat(lv.start_date[:10]); d1 = date.fromisoformat(lv.end_date[:10])
    except ValueError:
        return 0
    written = 0
    d = d0
    while d <= d1:
        ds = d.isoformat()
        exist = db.scalars(select(InternshipCheckin).where(
            InternshipCheckin.tenant_id == _tid(), InternshipCheckin.internship_id == lv.internship_id,
            InternshipCheckin.checkin_date == ds)).first()
        if not exist:
            db.add(InternshipCheckin(tenant_id=_tid(), internship_id=lv.internship_id,
                                     checkin_date=ds, checkin_at=datetime.utcnow(), result="LEAVE",
                                     note=f"请假（{TYPE_LABEL.get(lv.leave_type, lv.leave_type)}）：{(lv.reason or '')[:80]}"))
            written += 1
        d += timedelta(days=1)
    return written


def ack_overdue_return(user, leave_id, note: str = "") -> dict:
    """教师确认超期销假办结并关闭 INT-R06 风险。"""
    note = (note or "").strip()
    if len(note) < 2:
        raise AppException("VALIDATION_ERROR", "办结说明不少于 2 字")
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        lv = _get(db, leave_id)
        rec = db.get(InternshipRecord, lv.internship_id)
        stu = db.get(StudentProfile, lv.student_id)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            raise no_permission("只能办结本人指导学生的请假")
        if lv.status not in ("RETURNED", "OVERDUE"):
            raise AppException("DATA_CONFLICT", "仅超期未归或已销假记录可办结确认")
        if lv.status == "OVERDUE":
            lv.status = "RETURNED"
            lv.returned_at = datetime.utcnow()
            lv.return_note = note[:500]
            lv.version = int(lv.version or 0) + 1
            _trail(db, lv.id, "TEACHER_PROXY_RETURN", {"note": note}, operator=_op_name(user))
        closed = 0
        risks = db.scalars(select(RiskRecord).where(
            RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == lv.internship_id,
            RiskRecord.risk_code == "INT-R06",
            RiskRecord.status.in_(("PENDING_HANDLE", "PROCESSING")),
            RiskRecord.is_deleted.is_(False))).all()
        for r in risks:
            r.status = "CLOSED"
            r.last_follow_at = datetime.utcnow()
            r.last_follow_note = f"销假办结：{note}"[:500]
            r.version = int(r.version or 0) + 1
            closed += 1
            db.add(InternshipAuditTrail(
                tenant_id=_tid(), target_id=r.id, target_type="RISK", action="CLOSE",
                operator_name=_op_name(user),
                detail_json={"result": "RESOLVED", "from": "leave_ack", "leaveId": str(lv.id)},
                occurred_at=datetime.utcnow()))
        _trail(db, lv.id, "ACK_OVERDUE_RETURN", {"note": note, "risksClosed": closed},
               operator=_op_name(user))
        db.commit()
        return {"id": str(lv.id), "status": lv.status, "statusLabel": STATUS_LABEL.get(lv.status, lv.status),
                "risksClosed": closed, "message": "已确认销假办结"}


def refresh_overdue(reference_date: date | None = None, user=None, system: bool = False) -> dict:
    """标记超期请假并创建风险；人工触发仅允许校级管理员。"""
    if not system:
        from app.modules.internship.services.internship_service import assert_admin_tenant
        assert_admin_tenant(user, "请假超期批处理")
    today = reference_date or date.today()
    marked = risks_created = 0
    with session() as db:
        rows = db.scalars(select(InternshipLeave).where(
            InternshipLeave.tenant_id == _tid(), InternshipLeave.status == "APPROVED",
            InternshipLeave.is_deleted.is_(False))).all()
        for lv in rows:
            try:
                end = date.fromisoformat((lv.end_date or "")[:10])
            except ValueError:
                continue
            if end >= today:
                continue
            lv.status = "OVERDUE"
            lv.version = int(lv.version or 0) + 1
            _trail(db, lv.id, "MARK_OVERDUE", {"endDate": lv.end_date, "referenceDate": today.isoformat()})
            marked += 1
            existing = db.scalars(select(RiskRecord).where(
                RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == lv.internship_id,
                RiskRecord.risk_code == "INT-R06", RiskRecord.status.in_(("PENDING_HANDLE", "PROCESSING")),
                RiskRecord.is_deleted.is_(False))).first()
            if not existing:
                db.add(RiskRecord(tenant_id=_tid(), internship_id=lv.internship_id, risk_code="INT-R06",
                                  risk_title="实习请假超期未销假", risk_level="MEDIUM",
                                  source_module="internship_leave", status="PENDING_HANDLE",
                                  last_follow_note=f"请假至 {lv.end_date}，截至 {today.isoformat()} 未销假"))
                risks_created += 1
        db.commit()
    return {"referenceDate": today.isoformat(), "markedOverdue": marked, "risksCreated": risks_created}


def export_leaves(status=None, keyword=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(
        list_leaves, status=status, keyword=keyword, batch_id=batch_id, user=user)
    headers = ["学号", "姓名", "校内指导教师", "请假类型", "开始", "结束", "天数", "事由",
               "证明材料", "状态", "审批人", "审批意见"]
    rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["leaveTypeLabel"],
             it["startDate"], it["endDate"], it["days"], it["reason"],
             "已上传" if it["hasEvidence"] else "未上传", it["statusLabel"],
             it["reviewBy"], it["reviewComment"]] for it in items]
    wm = f"岗位实习中心·请假审批台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("请假审批台账", headers, rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "请假审批台账.xlsx", len(items))
