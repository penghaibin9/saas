"""岗位实习 · 请假工作流（P1-Stage3）。

学生（移动端本人）发起/撤回；指导教师（PC 管理端，owner 校验 + 数据范围）审批/驳回。
状态机：PENDING →(教师) APPROVED/REJECTED；PENDING →(学生) WITHDRAWN。
证明附件走文件中心 file_id。全程审计 target_type=LEAVE。
数据范围/owner：复用 internship_service 的 _current_scope / _rec_in_scope。
病假或连续三天及以上请假必须上传证明；存在证明时审批人须先真实查看并留下审计。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.core.timeutil import UTC, tenant_tz
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.core.tenant_scoped import tenant_get
from app.models import (InternshipAuditTrail, InternshipCheckin, InternshipLeave,
                        InternshipRecord, RiskRecord, StudentProfile)
from app.services.db_service import _as_id, _iso, _tid, session
from app.models.file import FileBinding, FileObject

STATUS_LABEL = {"PENDING": "待审批", "APPROVED": "已通过", "REJECTED": "已驳回", "WITHDRAWN": "已撤回"}
STATUS_LABEL.update({"RETURNED": "已销假", "OVERDUE": "超期未销假"})
STATUS_LABEL['NEEDS_REVISION'] = '已退回，请补正'
TYPE_LABEL = {"SICK": "病假", "PERSONAL": "事假", "OTHER": "其他"}
LONG_LEAVE_DAYS = 3.0


def effective_period(leave):
    """原申请日期保留；即时销假按学校当地日期结束免签，返岗当天恢复出勤。"""
    try:
        start, end = date.fromisoformat(leave.start_date[:10]), date.fromisoformat(leave.end_date[:10])
    except (TypeError, ValueError):
        return None, None
    if leave.status == 'RETURNED' and leave.returned_at:
        returned = leave.returned_at
        if returned.tzinfo is None:
            returned = returned.replace(tzinfo=UTC)
        end = min(end, returned.astimezone(tenant_tz()).date() - timedelta(days=1))
    return start, end


def _release_leave_checkins(db, leave):
    """只释放本单返岗后的请假占位，保留其他有效请假及真实签到。"""
    start, end = effective_period(leave)
    if start is None or leave.status != 'RETURNED' or not leave.returned_at:
        return 0
    first = max(start, end + timedelta(days=1))
    others = db.scalars(select(InternshipLeave).where(
        InternshipLeave.tenant_id == _tid(), InternshipLeave.internship_id == leave.internship_id,
        InternshipLeave.id != leave.id, InternshipLeave.status.in_(('APPROVED', 'OVERDUE', 'RETURNED')),
        InternshipLeave.start_date <= leave.end_date, InternshipLeave.end_date >= first.isoformat(),
        InternshipLeave.is_deleted.is_(False)).with_for_update().execution_options(populate_existing=True)).all()
    periods = [effective_period(row) for row in others]
    rows = db.scalars(select(InternshipCheckin).where(
        InternshipCheckin.tenant_id == _tid(), InternshipCheckin.internship_id == leave.internship_id,
        InternshipCheckin.checkin_date >= first.isoformat(), InternshipCheckin.checkin_date <= leave.end_date,
        InternshipCheckin.result == 'LEAVE', InternshipCheckin.is_deleted.is_(False)).with_for_update()).all()
    released = 0
    for row in rows:
        day = date.fromisoformat(row.checkin_date)
        if not any(left and right and left <= day <= right for left, right in periods):
            row.is_deleted = True
            released += 1
    return released


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _actor_id(user) -> str:
    return str((user or {}).get("userId") or (user or {}).get("loginName") or "").strip()


def _trail(db, lid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=lid, target_type="LEAVE",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def lock_attendance_record(db, record_id):
    record = db.scalar(select(InternshipRecord).where(
        InternshipRecord.id == _as_id(record_id), InternshipRecord.tenant_id == _tid(),
        InternshipRecord.is_deleted.is_(False)).with_for_update().execution_options(populate_existing=True))
    if not record:
        raise not_found('实习记录不存在')
    return record


def _get(db, lid, *, for_write=False, expected_record_id=None) -> InternshipLeave:
    lv = tenant_get(db, InternshipLeave, _as_id(lid))
    if not lv or lv.is_deleted:
        raise not_found("请假申请不存在")
    if expected_record_id is not None and lv.internship_id != _as_id(expected_record_id):
        raise no_permission('只能办理当前实习记录的请假')
    if for_write:
        lock_attendance_record(db, lv.internship_id)
        lv = db.scalar(select(InternshipLeave).where(
            InternshipLeave.id == _as_id(lid), InternshipLeave.tenant_id == _tid(),
            InternshipLeave.is_deleted.is_(False)).with_for_update().execution_options(populate_existing=True))
        if not lv:
            raise not_found('请假申请不存在')
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


def _validate_file(file_id, user=None):
    fid = str(file_id or "").strip()
    if not fid:
        return None
    from app.services.file_access_service import require_file_access
    require_file_access(fid, user=user, action="bind")
    return fid


def _version(raw):
    if not (type(raw) is int or isinstance(raw, str) and raw.isascii() and raw.isdecimal()):
        raise AppException("VALIDATION_ERROR", "请提供有效的非负整数记录版本")
    value = int(raw)
    if value < 0:
        raise AppException("VALIDATION_ERROR", "记录版本不能为负数")
    return value


def _application_values(body):
    start, end = str(body.get("startDate") or "").strip(), str(body.get("endDate") or "").strip()
    reason = str(body.get("reason") or "").strip()
    leave_type = str(body.get("leaveType") or "PERSONAL").upper()
    if leave_type not in TYPE_LABEL:
        raise AppException("VALIDATION_ERROR", "请选择有效的请假类型")
    if not 2 <= len(reason) <= 500:
        raise AppException("VALIDATION_ERROR", "请假事由须填写2至500字")
    try:
        if len(start) != 10 or len(end) != 10:
            raise ValueError
        d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        raise AppException("VALIDATION_ERROR", "请填写有效的起止日期") from None
    if d1 < d0:
        raise AppException("VALIDATION_ERROR", "结束日期不能早于开始日期")
    return {"leave_type": leave_type, "start_date": start, "end_date": end,
            "days": float((d1 - d0).days + 1), "reason": reason}


def _assert_leave_period(record, values):
    if record.status not in ("ONBOARD", "ASSESSING"):
        raise AppException("DATA_CONFLICT", "仅在岗或考核中的实习学生可以申请请假", http_status=409)
    start, end = date.fromisoformat(values['start_date']), date.fromisoformat(values['end_date'])
    if (record.intern_start_date and start < record.intern_start_date.date()
            or record.intern_end_date and end > record.intern_end_date.date()):
        raise AppException("VALIDATION_ERROR", "请假日期须在当前实习起止日期内")


def _bind_evidence(db, leave, record, student, file_id, user):
    if not file_id:
        return
    from app.services.file_business_binding_service import bind_file_to_business
    bind_file_to_business(
        db, file_id=file_id, biz_type="INTERNSHIP_LEAVE", biz_id=str(leave.id),
        actor=user, subject_type="STUDENT", subject_id=str(student.id),
        module_code="INTERNSHIP", student_id=student.id, batch_id=str(record.batch_id),
        college_id=student.college_id, class_id=student.class_id,
        scope={"internshipId": str(record.id), "studentId": str(student.id),
               "studentNo": student.student_no, "batchId": str(record.batch_id),
               "advisorUserId": str(record.advisor_user_id or ""),
               "businessType": "INTERNSHIP_LEAVE", "businessId": str(leave.id)},
        legacy_target_values={str(leave.id), str(record.id), str(student.id), student.student_no},
    )


def authorize_leave_file(db, file_obj, bindings, user, action):
    """当前与历史证明共用原请假及实习范围，不能由上传者权限兜底。"""
    if db is None:
        return False
    student_actor = str(user.get('userType') or '').upper() == 'STUDENT'
    if student_actor:
        from app.services.mobile_student_service import resolve_student
        actor_student = resolve_student(db, user)
        if not actor_student:
            return False
    elif not has_permission(user, 'internship.leave.view'):
        return False
    from app.modules.internship.services.internship_scope import assert_internship_record_scope
    for binding in bindings:
        if (binding.tenant_id != _tid() or binding.is_deleted or binding.status != 'ACTIVE'
                or binding.biz_type != 'INTERNSHIP_LEAVE' or str(binding.file_id) != str(file_obj.id)
                or not str(binding.biz_id or '').isascii() or not str(binding.biz_id or '').isdigit()):
            continue
        leave = tenant_get(db, InternshipLeave, int(binding.biz_id))
        record = tenant_get(db, InternshipRecord, leave.internship_id) if leave and not leave.is_deleted else None
        student = tenant_get(db, StudentProfile, leave.student_id) if record else None
        if (not record or record.is_deleted or not student or student.is_deleted
                or record.student_id != leave.student_id
                or binding.student_id and binding.student_id != student.id
                or binding.batch_id and str(binding.batch_id) != str(record.batch_id)):
            continue
        if student_actor:
            return actor_student.id == student.id
        assert_internship_record_scope(db, record.id, user, '访问请假证明')
        return True
    return False


def _snapshot(leave):
    return {"version": int(leave.version or 0), "leaveType": leave.leave_type,
            "startDate": leave.start_date, "endDate": leave.end_date, "days": leave.days,
            "reason": leave.reason, "evidenceFileId": str(leave.file_id or ""),
            "reviewComment": leave.review_comment or "", "reviewAt": _iso(leave.review_at)}


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
        InternshipLeave.status.in_(("REJECTED", "NEEDS_REVISION")),
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


def _enterprise_names(db, records):
    """当前落岗快照优先；仅无快照指针的旧记录使用冗余名称。"""
    from app.models.internship_placement_snapshot import InternshipPlacementSnapshot as Snapshot
    names = {r.id: (r.enterprise_name or '') if not r.current_placement_snapshot_id else '' for r in records}
    if records:
        names.update(db.execute(select(InternshipRecord.id, Snapshot.company_name).join(
            Snapshot, Snapshot.id == InternshipRecord.current_placement_snapshot_id).where(
            InternshipRecord.id.in_(names), InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False), Snapshot.tenant_id == _tid(),
            Snapshot.record_id == InternshipRecord.id, Snapshot.batch_id == InternshipRecord.batch_id,
            Snapshot.company_id == InternshipRecord.enterprise_id, Snapshot.position_id == InternshipRecord.position_id)).all())
    return names


def _row(lv: InternshipLeave, rec, stu, *, db=None, user=None,
         previous=None, evidence_viewed=None, evidence_file_name='', enterprise_name=None, preloaded: bool = False) -> dict:
    from app.modules.internship.services.internship_leave_policy_service import progress
    if not preloaded:
        previous = _previous_rejection(db, lv) if db is not None else None
        evidence_viewed = _evidence_viewed(db, lv, user) if db is not None and user else False
    return {
        "id": str(lv.id), "internId": str(lv.internship_id),
        "approvalProgress": progress(db, lv, user) if db is not None and not preloaded else None,
        "internshipId": str(lv.internship_id), "batchId": str(rec.batch_id) if rec else "",
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "enterpriseName": (enterprise_name if enterprise_name is not None else
                           _enterprise_names(db, [rec]).get(rec.id, '') if db is not None and rec else ''),
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
        "evidenceFileName": evidence_file_name,
        "evidenceRequired": _evidence_required(lv.leave_type, lv.days),
        "evidenceRequirementLabel": _evidence_requirement_label(lv.leave_type, lv.days),
        "evidenceViewed": bool(evidence_viewed),
        "previousReviewComment": previous.review_comment or "" if previous else "",
        "previousReviewAt": _iso(previous.review_at) or "" if previous else "",
    }


def apply(user, body) -> dict:
    b = body or {}
    values = _application_values(b)
    start, end, days, leave_type = values['start_date'], values['end_date'], values['days'], values['leave_type']
    file_id = _validate_file(b.get("fileId") or b.get("evidenceFileId"), user)
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
        _assert_leave_period(rec, values)
        dup = db.scalars(select(InternshipLeave).where(
            InternshipLeave.tenant_id == _tid(), InternshipLeave.internship_id == rec.id,
            InternshipLeave.status == "PENDING", InternshipLeave.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "你有待审批的请假申请，请先等待处理或撤回", http_status=409)
        lv = InternshipLeave(tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
                             **values, status="PENDING",
                             apply_by_name=(stu.real_name if stu else _op_name(user)), file_id=file_id)
        db.add(lv)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise AppException(
                "DATA_CONFLICT", "你有待审批的请假申请，请先等待处理或撤回") from exc
        _bind_evidence(db, lv, rec, stu, file_id, user)
        _trail(db, lv.id, "APPLY", {
            "range": f"{start}~{end}", "days": days,
            "leaveType": leave_type, "evidenceFileId": file_id or "",
            "evidenceRequired": _evidence_required(leave_type, days),
            "snapshot": _snapshot(lv),
        }, operator=lv.apply_by_name or "学生")
        from app.modules.internship.services import internship_todo_helper as ix_todo
        ix_todo.push_leave_todo(db, lv, rec)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise AppException(
                "DATA_CONFLICT", "你有待审批的请假申请，请先等待处理或撤回") from exc
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
        from app.modules.internship.services.internship_leave_policy_service import cancel
        cancel(db, lv.tenant_id, lv.id)
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
        lv = _get(db, leave_id, for_write=True)
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
        released = _release_leave_checkins(db, lv)
        _trail(db, lv.id, "RETURN", {"wasOverdue": was_overdue, "hasFile": bool(file_id), "note": note,
                                    "attendanceReleased": released},
               operator=_op_name(user))
        db.commit()
        return {"id": str(lv.id), "status": lv.status, "statusLabel": STATUS_LABEL[lv.status],
                "wasOverdue": was_overdue}


def _acknowledged_returns(db, leaves):
    ids = [row.id for row in leaves if row.status == 'RETURNED']
    if not ids:
        return set()
    return set(db.scalars(select(InternshipAuditTrail.target_id).where(
        InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_type == 'LEAVE',
        InternshipAuditTrail.target_id.in_(ids),
        InternshipAuditTrail.action == 'ACK_OVERDUE_RETURN_VERSIONED')))


def my_leaves(user) -> list[dict]:
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            return []
        rows = db.scalars(select(InternshipLeave).where(
            InternshipLeave.tenant_id == _tid(), InternshipLeave.internship_id == rec.id,
            InternshipLeave.is_deleted.is_(False)).order_by(InternshipLeave.id.desc())).all()
        name = _enterprise_names(db, [rec]).get(rec.id, '')
        acknowledged = _acknowledged_returns(db, rows)
        return [{**_row(lv, rec, stu, db=db, user=user, enterprise_name=name),
                 'returnAcknowledged': lv.id in acknowledged} for lv in rows]


# ═══════════ 指导教师 / 管理员（PC 管理端，owner + 数据范围） ═══════════

def list_leaves(page, page_size, status=None, keyword=None, batch_id=None, user=None,
                return_pending=False) -> tuple[list[dict], int]:
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False)), user).subquery()
        query = select(InternshipLeave, InternshipRecord, StudentProfile).join(
            InternshipRecord, InternshipRecord.id == InternshipLeave.internship_id
        ).join(
            StudentProfile, StudentProfile.id == InternshipLeave.student_id
        ).where(
            InternshipLeave.tenant_id == _tid(),
            InternshipLeave.is_deleted.is_(False),
            InternshipLeave.internship_id.in_(select(scoped.c.id)),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            InternshipRecord.student_id == InternshipLeave.student_id,
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        if status:
            if status not in STATUS_LABEL:
                raise AppException('VALIDATION_ERROR', '请选择有效的请假状态')
            query = query.where(InternshipLeave.status == status)
            if status == 'PENDING' and user:
                from app.modules.internship.services.internship_leave_policy_service import pending_for_actor
                query = query.where(pending_for_actor(user))
        if return_pending:
            acknowledged = select(InternshipAuditTrail.id).where(
                InternshipAuditTrail.tenant_id == _tid(),
                InternshipAuditTrail.target_type == 'LEAVE',
                InternshipAuditTrail.target_id == InternshipLeave.id,
                InternshipAuditTrail.action == 'ACK_OVERDUE_RETURN_VERSIONED').exists()
            query = query.where(InternshipLeave.status.in_(('RETURNED', 'OVERDUE')), ~acknowledged)
        term = str(keyword or "").strip()
        if term:
            like = f"%{term}%"
            query = query.where(or_(
                StudentProfile.real_name.like(like),
                StudentProfile.student_no.like(like),
            ))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        size = max(0, int(page_size or 0))
        if size == 0:
            return [], total
        rows = db.execute(
            query.order_by(InternshipLeave.id.desc())
            .offset((max(1, int(page or 1)) - 1) * size).limit(size)
        ).all()
        enterprise_names = _enterprise_names(db, list({item[1].id: item[1] for item in rows}.values()))
        leaves = [item[0] for item in rows]
        ids = [item.id for item in leaves]
        evidence_names = {}
        file_ids = [int(item.file_id) for item in leaves if str(item.file_id or '').isascii() and str(item.file_id or '').isdigit()]
        if file_ids:
            files = db.execute(select(FileObject.id, FileObject.file_name, FileBinding.biz_id).join(
                FileBinding, FileBinding.file_id == FileObject.id).where(
                FileObject.tenant_id == _tid(), FileObject.is_deleted.is_(False), FileObject.id.in_(file_ids),
                FileBinding.tenant_id == _tid(), FileBinding.is_deleted.is_(False), FileBinding.status == 'ACTIVE',
                FileBinding.biz_type == 'INTERNSHIP_LEAVE', FileBinding.biz_id.in_([str(value) for value in ids]))).all()
            evidence_names = {(str(fid), str(lid)): name for fid, name, lid in files}
        previous_map = {}
        if leaves:
            internship_ids = {item.internship_id for item in leaves}
            rejected = db.scalars(select(InternshipLeave).where(
                InternshipLeave.tenant_id == _tid(),
                InternshipLeave.internship_id.in_(internship_ids),
                InternshipLeave.status.in_(("REJECTED", "NEEDS_REVISION")),
                InternshipLeave.is_deleted.is_(False),
            ).order_by(InternshipLeave.id.desc())).all()
            for item in rejected:
                key = (item.internship_id, item.leave_type, item.start_date, item.end_date)
                previous_map.setdefault(key, item)
        viewed_ids = set()
        if ids and user:
            actor_id = _actor_id(user)
            operator = _op_name(user)
            trails = db.scalars(select(InternshipAuditTrail).where(
                InternshipAuditTrail.tenant_id == _tid(),
                InternshipAuditTrail.target_type == "LEAVE",
                InternshipAuditTrail.target_id.in_(ids),
                InternshipAuditTrail.action == "EVIDENCE_VIEW",
            ).order_by(InternshipAuditTrail.id.desc())).all()
            by_id = {item.id: item for item in leaves}
            for trail in trails:
                leave = by_id.get(trail.target_id)
                if not leave or not leave.file_id:
                    continue
                detail = trail.detail_json or {}
                try:
                    same_version = int(detail.get("version")) == int(leave.version or 0)
                except (TypeError, ValueError):
                    same_version = False
                same_file = str(detail.get("evidenceFileId") or "") == str(leave.file_id)
                same_actor = (
                    str(detail.get("operatorUserId") or "") == actor_id
                    if actor_id else (trail.operator_name or "") == operator
                )
                if same_version and same_file and same_actor:
                    viewed_ids.add(leave.id)
        from app.modules.internship.services.internship_leave_policy_service import progress_many
        progress_rows = progress_many(db, leaves, user)
        acknowledged = _acknowledged_returns(db, leaves)
        result = []
        for leave, record, student in rows:
            key = (leave.internship_id, leave.leave_type, leave.start_date, leave.end_date)
            previous = previous_map.get(key)
            if previous and previous.id == leave.id:
                previous = None
            result.append(_row(
                leave, record, student, db=db, user=user,
                previous=previous, evidence_viewed=leave.id in viewed_ids,
                evidence_file_name=evidence_names.get((str(leave.file_id), str(leave.id)), ''),
                enterprise_name=enterprise_names.get(record.id, ''),
                preloaded=True,
            ))
        for item in result:
            item['approvalProgress'] = progress_rows.get(int(item['id']))
            item['returnAcknowledged'] = int(item['id']) in acknowledged
        return result, total


def get_leave(leave_id, user=None, *, batch_id=None) -> dict:
    from app.services import file_service
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        lv = _get(db, leave_id)
        rec = tenant_get(db, InternshipRecord, lv.internship_id)
        stu = tenant_get(db, StudentProfile, lv.student_id)
        if not rec or rec.is_deleted or not stu or stu.is_deleted or rec.student_id != lv.student_id:
            raise not_found('请假关联的实习与学生不存在或不一致')
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            raise no_permission("该请假申请不在你的数据范围内")
        from app.modules.internship.services.internship_batch_context import assert_record_batch
        assert_record_batch(rec, batch_id)
        return _detail(db, lv, rec, stu, user)


def _detail(db, lv, rec, stu, user):
    from app.services import file_service
    trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "LEAVE",
            InternshipAuditTrail.target_id == lv.id).order_by(InternshipAuditTrail.id)).all()
    history = []
    for item in trail:
        detail = item.detail_json or {}
        if item.action == "RESUBMIT_VERSIONED" and detail.get("previous"):
            previous = detail['previous']
            if history:
                history[-1].update({"reviewComment": previous.get("reviewComment") or "",
                                    "reviewAt": previous.get("reviewAt"), "reviewedVersion": previous.get("version")})
            else:
                history.append(previous)
        if item.action in ("APPLY", "RESUBMIT_VERSIONED") and detail.get("snapshot"):
            history.append({**detail['snapshot'], "submittedAt": _iso(item.occurred_at)})
    attachment = file_service.attachment_view(lv.file_id)
    return {**_row(lv, rec, stu, db=db, user=user, evidence_file_name=(attachment or {}).get('fileName', '')), "attachment": attachment,
                "submissionHistory": history,
                "returnAcknowledged": any(t.action == "ACK_OVERDUE_RETURN_VERSIONED" for t in trail),
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                               for t in trail]}


def mark_evidence_viewed(user, leave_id, body) -> dict:
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    from app.services import file_service
    from app.modules.internship.services.internship_student_leave_context_service import _locked, _expected
    from app.modules.internship.services.internship_batch_context import assert_record_batch, parse_required_batch_id
    payload = body or {}
    batch_id = parse_required_batch_id(payload.get('batchId'))
    with session() as db:
        lv = _locked(db, leave_id)
        rec = tenant_get(db, InternshipRecord, lv.internship_id)
        stu = tenant_get(db, StudentProfile, lv.student_id)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            raise no_permission("该请假申请不在你的数据范围内")
        assert_record_batch(rec, batch_id)
        _expected(payload.get('expectedVersion'), lv.version)
        if str(payload.get('evidenceFileId') or '') != str(lv.file_id or ''):
            raise AppException("DATA_CONFLICT", "证明材料已变化，请重新查看当前材料", http_status=409)
        if not lv.file_id or not file_service.get_file_meta(lv.file_id, user=user):
            raise not_found("请假证明不存在或无权查看")
        from app.services.file_access_service import require_file_access
        require_file_access(lv.file_id, user=user, action='preview')
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
    if action not in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
        raise AppException("VALIDATION_ERROR", "请选择通过、退回补正或驳回")
    if not isinstance(comment, str):
        raise AppException("VALIDATION_ERROR", "审批意见须填写文字")
    comment = comment.strip()
    if action != "APPROVE" and len(comment) < 5:
        raise AppException("VALIDATION_ERROR", "退回或驳回原因必填且不少于 5 字")
    ver = _version(expected_version)
    if len(comment) > 500:
        raise AppException("VALIDATION_ERROR", "审批意见不能超过500字")
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        lv = _get(db, leave_id, for_write=True)
        rec = tenant_get(db, InternshipRecord, lv.internship_id)
        stu = tenant_get(db, StudentProfile, lv.student_id)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            raise no_permission("只能审批本人指导学生的请假申请")
        from app.modules.internship.services.internship_batch_context import assert_record_batch
        assert_record_batch(rec, expected_batch_id)
        if action == "APPROVE":
            if _evidence_required(lv.leave_type, lv.days) and not lv.file_id:
                raise AppException("DATA_CONFLICT", "该请假按规则必须上传证明材料，当前不能通过")
            if lv.file_id and not _evidence_viewed(db, lv, user):
                raise AppException("DATA_CONFLICT", "请先查看请假证明材料，再执行通过")
        from app.modules.internship.services.internship_leave_policy_service import advance
        final_step = advance(db, user, lv, action, comment)
        new_status = {'APPROVE': 'APPROVED', 'REJECT': 'REJECTED', 'REQUEST_CHANGES': 'NEEDS_REVISION'}[action] if final_step else 'PENDING'
        now = datetime.utcnow()
        new_ver = versioned_update(
            db, InternshipLeave, entity_id=lv.id, tenant_id=_tid(), expected_version=ver,
            values={
                "status": new_status, "review_by_name": _op_name(user),
                "review_at": now, "review_comment": (comment or "").strip() or None,
            },
            expected_status="PENDING")
        leave_days = 0
        if action == "APPROVE" and final_step:
            db.refresh(lv)
            leave_days = _write_leave_checkins(db, lv)
        _trail(db, lv.id, f"REVIEW_{action}", {
            "comment": (comment or "").strip(),
            "leaveCheckins": leave_days,
            "evidenceFileId": str(lv.file_id or ""),
            "evidenceViewed": bool(lv.file_id),
        }, operator=_op_name(user))
        from app.modules.internship.services import internship_todo_helper as ix_todo
        if final_step:
            ix_todo.todo_done(db, biz_id=lv.id, todo_type=ix_todo.TODO_LEAVE)
        db.commit()
        return {"id": str(lv.id), "status": new_status, "statusLabel": STATUS_LABEL[new_status],
                "leaveDays": leave_days, "version": new_ver,
                "message": '本级已通过，已交下一责任人；全部节点通过后请假才生效' if not final_step else '审批已完成'}


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
            InternshipCheckin.checkin_date == ds).with_for_update()).first()
        if exist and exist.is_deleted and exist.result == 'LEAVE':
            exist.is_deleted = False
            exist.note = f"请假（{TYPE_LABEL.get(lv.leave_type, '其他')}）：{(lv.reason or '')[:80]}"
            written += 1
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
        lv = _get(db, leave_id, for_write=True)
        rec = tenant_get(db, InternshipRecord, lv.internship_id)
        stu = tenant_get(db, StudentProfile, lv.student_id)
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
        released = _release_leave_checkins(db, lv)
        closed = 0
        risks = db.scalars(select(RiskRecord).where(
            RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == lv.internship_id,
            RiskRecord.source_type == "LEAVE", RiskRecord.source_id == lv.id,
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
        _trail(db, lv.id, "ACK_OVERDUE_RETURN", {"note": note, "risksClosed": closed, "attendanceReleased": released},
               operator=_op_name(user))
        db.commit()
        return {"id": str(lv.id), "status": lv.status, "statusLabel": STATUS_LABEL.get(lv.status, lv.status),
                "risksClosed": closed, "message": "已确认销假办结"}


def refresh_overdue(reference_date: date | None = None, user=None, system: bool = False, *, batch_id=None) -> dict:
    """标记超期请假并创建风险；人工触发仅允许校级管理员。"""
    if not system:
        from app.modules.internship.services.internship_service import assert_admin_tenant
        assert_admin_tenant(user, "请假超期批处理")
    today = reference_date or date.today()
    marked = risks_created = 0
    with session() as db:
        query = select(InternshipLeave).where(
            InternshipLeave.tenant_id == _tid(), InternshipLeave.status == "APPROVED",
            InternshipLeave.is_deleted.is_(False))
        if batch_id is not None:
            query = query.join(InternshipRecord, InternshipRecord.id == InternshipLeave.internship_id).where(
                InternshipRecord.tenant_id == _tid(), InternshipRecord.batch_id == int(batch_id),
                InternshipRecord.student_id == InternshipLeave.student_id, InternshipRecord.is_deleted.is_(False))
        rows = db.scalars(query).all()
        for lv in rows:
            try:
                end = date.fromisoformat((lv.end_date or "")[:10])
            except ValueError:
                continue
            if end >= today:
                continue
            changed = db.execute(update(InternshipLeave).where(
                InternshipLeave.id == lv.id, InternshipLeave.tenant_id == _tid(),
                InternshipLeave.status == 'APPROVED', InternshipLeave.version == int(lv.version or 0),
                InternshipLeave.is_deleted.is_(False),
            ).values(status='OVERDUE', version=InternshipLeave.version + 1),
                execution_options={'synchronize_session': False})
            if changed.rowcount != 1:
                continue
            db.refresh(lv)
            _trail(db, lv.id, "MARK_OVERDUE", {"endDate": lv.end_date, "referenceDate": today.isoformat()})
            marked += 1
            existing = db.scalars(select(RiskRecord).where(
                RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == lv.internship_id,
                RiskRecord.source_type == "LEAVE", RiskRecord.source_id == lv.id,
                RiskRecord.risk_code == "INT-R06", RiskRecord.status.in_(("PENDING_HANDLE", "PROCESSING")),
                RiskRecord.is_deleted.is_(False))).first()
            if not existing:
                db.add(RiskRecord(tenant_id=_tid(), internship_id=lv.internship_id, risk_code="INT-R06",
                                  risk_title="实习请假超期未销假", risk_level="MEDIUM",
                                  source_module="internship_leave", source_type="LEAVE", source_id=lv.id,
                                  source_version=int(lv.version or 0), status="PENDING_HANDLE",
                                  last_follow_note=f"请假至 {lv.end_date}，截至 {today.isoformat()} 未销假"))
                risks_created += 1
        db.commit()
    return {"referenceDate": today.isoformat(), "markedOverdue": marked, "risksCreated": risks_created}


def export_leaves(status=None, keyword=None, batch_id=None, user=None, return_pending=False) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows, pack_export_meta, write_export_audit
    items, total = load_export_rows(
        list_leaves, status=status, keyword=keyword, batch_id=batch_id, user=user, return_pending=return_pending)
    headers = ["学号", "姓名", "实习企业", "校内指导教师", "请假类型", "开始日期", "结束日期", "天数", "请假原因",
               "证明文件", "当前状态", "审批人", "老师意见", "原请假单号"]
    rows = [[it["studentNo"], it["studentName"], it["enterpriseName"], it["advisorName"], it["leaveTypeLabel"],
             it["startDate"], it["endDate"], it["days"], it["reason"],
             it["evidenceFileName"] or ("证明记录待核对" if it["hasEvidence"] else "未上传"), it["statusLabel"],
             it["reviewBy"], it["reviewComment"], it["id"]] for it in items]
    wm = f"岗位实习中心·请假审批台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("请假审批台账", headers, rows, watermark=wm,
        column_widths={1: 26, 2: 18, 3: 30, 4: 18, 5: 14, 6: 16, 7: 16, 8: 10,
                       9: 58, 10: 34, 11: 18, 12: 18, 13: 52, 14: 20})
    with session() as db:
        write_export_audit(db, '请假审批台账', total, user=user,
            filters={'batchId': str(batch_id or ''), 'status': status or '', 'keyword': str(keyword or '').strip(), 'returnPending': bool(return_pending)},
            sensitive_fields=['请假原因', '证明文件', '老师意见'])
        db.commit()
    return {**xlsx_util.pack_xlsx_result(content, "请假审批台账.xlsx", len(items)), **pack_export_meta(total, len(items))}
