"""13A-P2 请假销假闭环（范式样板：状态机 + workflow + 待办/消息 + 360 + 统计 + 双状态列）。

在既有 t_cs_leave 上做（加列扩展，非平行表，P0 §4.2 集成①）：
- affairs_status = 13A 14 态真相列；旧 status = 投影列（老 campus-service 读端点零改动全绿）。
- 审批走真 WorkflowInstance/Task + UnifiedTodo；终态写 StudentStageEvent 进 360。
后 5 个域（认定/处分/风险/调宿/归档）的"范式五件套"照抄本文件。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

# ── 审批层级阈值（规则中心键 affairs.leave.*_threshold_days，默认 3/7；P0 §5）──
# TODO：接平台规则中心后改读 t_platform_config；当前单一来源函数即"可配"锚点。
def _thresholds() -> tuple[float, float]:
    return 3.0, 7.0


NODE_SEQ = {
    "AFFAIRS_LEAVE": ["COUNSELOR_REVIEW"],
    "AFFAIRS_LEAVE_LONG": ["COUNSELOR_REVIEW", "COLLEGE_REVIEW"],
    "AFFAIRS_LEAVE_MAJOR": ["COUNSELOR_REVIEW", "COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW"],
}
_REVIEW_NODES = ("COUNSELOR_REVIEW", "COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW")
_TERMINAL = {"REJECTED", "CANCELLED", "CLOSED", "ARCHIVED"}

L_AFF = {
    "DRAFT": "草稿", "SUBMITTED": "已提交", "COUNSELOR_REVIEW": "辅导员审批",
    "COLLEGE_REVIEW": "学院审批", "STUDENT_AFFAIRS_REVIEW": "学工处审批", "APPROVED": "已通过",
    "REJECTED": "已驳回", "RETURNED": "已退回", "CANCELLED": "已取消",
    "EXTENSION_REVIEW": "续假审批中", "WAIT_CANCEL_LEAVE": "待销假确认", "CLOSED": "已销假",
    "OVERDUE": "已逾期", "ARCHIVED": "已归档",
}


def _project(aff: str | None) -> str:
    """affairs_status → 旧 status 投影（双状态列一致，C3 §5.3）。"""
    if aff in ("APPROVED", "CLOSED", "ARCHIVED", "OVERDUE"):
        return "APPROVED"
    if aff in ("REJECTED", "RETURNED", "CANCELLED"):
        return "RETURNED"
    return "PENDING_REVIEW"


def _wf_code(days: float) -> str:
    lo, hi = _thresholds()
    if days <= lo:
        return "AFFAIRS_LEAVE"
    if days <= hi:
        return "AFFAIRS_LEAVE_LONG"
    return "AFFAIRS_LEAVE_MAJOR"


def _days(start, end) -> float:
    if not start or not end:
        return 1.0
    return max(0.5, round((end - start).total_seconds() / 86400.0, 1))


def _parse_dt(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def _overlap(s1, e1, s2, e2) -> bool:
    if not all([s1, e1, s2, e2]):
        return False
    return s1 <= e2 and s2 <= e1


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_id, action, detail="", before="", after=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="LEAVE", biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             before_val=before, after_val=after, occurred_at=datetime.utcnow()))


# ── workflow / 待办 / 消息 helper（范式复用点）──

def _assignee_for(db, node: str, student_id) -> int:
    """节点审批人。P2 简化：COUNSELOR_REVIEW→班级 counselor_id；其余节点未建映射→0（待办池）。"""
    if node == "COUNSELOR_REVIEW" and student_id:
        from app.models import SchoolClass, StudentProfile
        s = db.get(StudentProfile, int(student_id))
        if s and s.class_id:
            c = db.get(SchoolClass, int(s.class_id))
            if c and c.counselor_id:
                return int(c.counselor_id)
    return 0


def _open_wf(db, wf_code, leave_id, applicant_id, title, first_node, assignee_id):
    from app.models import WorkflowInstance, WorkflowTask
    inst = WorkflowInstance(tenant_id=_tid(), workflow_code=wf_code, source_module="student-affairs",
                            source_biz_type="LEAVE", source_biz_id=int(leave_id),
                            applicant_id=int(applicant_id or 0), title=title, status="RUNNING",
                            current_node=first_node)
    db.add(inst)
    db.flush()
    db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=first_node,
                        assignee_id=int(assignee_id or 0), status="PENDING"))
    return inst


def _cur_task(db, inst_id, node):
    from app.models import WorkflowTask
    return db.scalars(select(WorkflowTask).where(
        WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == inst_id,
        WorkflowTask.node_code == node, WorkflowTask.status == "PENDING",
        WorkflowTask.is_deleted.is_(False))).first()


def _todo_upsert(db, leave_id, assignee_id, student_id, title, todo_type="LEAVE_APPROVAL"):
    """一张请假一条活待办；随节点推进更新受理人/标题（避免 uk_todo_dedup 冲突）。"""
    from app.models import UnifiedTodo
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_id == int(leave_id), UnifiedTodo.todo_type == todo_type,
        UnifiedTodo.assignee_id == int(assignee_id or 0),
        UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title = title
        row.status = "PENDING"
        row.version += 1
    else:
        db.add(UnifiedTodo(tenant_id=_tid(), source_module="student-affairs", source_biz_type="LEAVE",
                           source_biz_id=int(leave_id), todo_type=todo_type,
                           assignee_id=int(assignee_id or 0), student_id=student_id, title=title,
                           status="PENDING"))


def _todo_done(db, leave_id, todo_type="LEAVE_APPROVAL"):
    from app.models import UnifiedTodo
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.source_biz_id == int(leave_id), UnifiedTodo.todo_type == todo_type,
            UnifiedTodo.is_deleted.is_(False))).all():
        r.status = "DONE"
        r.version += 1


def _msg(db, receiver_id, title, content, mtype, leave_id):
    from app.models import UnifiedMessage
    db.add(UnifiedMessage(tenant_id=_tid(), receiver_id=int(receiver_id or 0),
                          source_module="student-affairs", source_biz_id=int(leave_id),
                          title=title, content=content, message_type=mtype, status="UNREAD"))


def _row(x, s=None) -> dict:
    return {
        "id": str(x.id), "studentId": str(x.student_id or ""),
        "studentName": s.real_name if s else "", "className": str(s.class_id or "") if s else "",
        "leaveType": x.leave_type, "days": float(x.days or 0),
        "startTime": _iso(x.start_time), "endTime": _iso(x.end_time), "reason": x.reason or "",
        "affairsStatus": x.affairs_status,
        "affairsStatusLabel": L_AFF.get(x.affairs_status or "", x.affairs_status or ""),
        "legacyStatus": x.status,  # 投影列（老端点读这个，双状态列一致性）
        "workflowInstanceId": str(x.workflow_instance_id or ""),
        "expectedReturnAt": _iso(x.expected_return_at), "actualReturnAt": _iso(x.actual_return_at),
    }


def _load(db, leave_id):
    from app.models import CsLeave, StudentProfile
    x = db.get(CsLeave, int(leave_id))
    if not x or x.is_deleted or x.tenant_id != _tid() or x.affairs_status is None:
        raise not_found("请假申请不存在")
    s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
    return x, s


def _scope_or_403(db, x, user):
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.models import StudentProfile
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is None:
        return
    s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
    if not s or s.class_id not in allowed:
        raise AppException("NO_DATA_SCOPE", "该请假不在您的数据范围内")


# ═══════════ 申请 ═══════════

def apply_leave(body, user) -> dict:
    student_id = int(body.studentId)
    start = _parse_dt(body.startTime)
    end = _parse_dt(body.endTime)
    days = _days(start, end)
    with session() as db:
        from app.models import CsLeave, StudentProfile
        s = db.get(StudentProfile, student_id)
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在或不在数据范围内")
        # 重复提交：同学生在途请假且时间重叠 → 409
        for a in db.scalars(select(CsLeave).where(
                CsLeave.tenant_id == _tid(), CsLeave.student_id == student_id,
                CsLeave.is_deleted.is_(False))).all():
            if a.affairs_status and a.affairs_status not in _TERMINAL \
                    and _overlap(a.start_time, a.end_time, start, end):
                raise AppException("DATA_CONFLICT", "该生存在时间重叠的在途请假，不可重复提交")
        wf = _wf_code(days)
        first = NODE_SEQ[wf][0]
        x = CsLeave(tenant_id=_tid(), cs_student_id=0, student_id=student_id,
                    leave_type=(body.leaveType or "PERSONAL"), start_time=start, end_time=end,
                    reason=body.reason, days=days, duration=f"{days}天",
                    affairs_status=first, status=_project(first), apply_time=datetime.utcnow(),
                    expected_return_at=end)
        db.add(x)
        db.flush()
        assignee = _assignee_for(db, first, student_id)
        inst = _open_wf(db, wf, x.id, student_id, f"{s.real_name} 请假 {days} 天", first, assignee)
        x.workflow_instance_id = inst.id
        _todo_upsert(db, x.id, assignee, student_id, f"请假待审批：{s.real_name} {days}天")
        _audit(db, x.id, "APPLY", f"days={days},wf={wf}")
        db.commit()
        db.refresh(x)
        return _row(x, s)


# ═══════════ 审批（多级） ═══════════

def _act_task(db, x, action, reason=""):
    from app.models import WorkflowInstance
    inst = db.get(WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
    task = _cur_task(db, inst.id, x.affairs_status) if inst else None
    if task:
        task.status = action
        task.acted_at = datetime.utcnow()
        task.action_reason = reason
        task.version += 1
    return inst


def approve(leave_id, user, comment="") -> dict:
    with session() as db:
        from app.models import WorkflowTask
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        aff = x.affairs_status
        if aff not in _REVIEW_NODES:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该请假当前状态不可审批，请刷新")
        inst = _act_task(db, x, "APPROVED", comment)
        wf = inst.workflow_code if inst else _wf_code(float(x.days or 1))
        seq = NODE_SEQ.get(wf, ["COUNSELOR_REVIEW"])
        i = seq.index(aff) if aff in seq else len(seq) - 1
        if i + 1 < len(seq):
            nxt = seq[i + 1]
            x.affairs_status, x.status = nxt, _project(nxt)
            x.version += 1
            if inst:
                inst.current_node = nxt
            assignee = _assignee_for(db, nxt, x.student_id)
            db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=nxt,
                                assignee_id=assignee, status="PENDING"))
            _todo_upsert(db, x.id, assignee, x.student_id,
                         f"请假待审批（{L_AFF.get(nxt, nxt)}）：{s.real_name if s else ''}")
            _audit(db, x.id, "APPROVE_STEP", f"{aff}->{nxt}")
        else:
            x.affairs_status, x.status = "APPROVED", "APPROVED"
            x.version += 1
            if inst:
                inst.status = "APPROVED"
            _todo_done(db, x.id)
            _msg(db, x.student_id, "请假已通过", f"你的请假（{x.days}天）已通过审批", "WORKFLOW_RESULT", x.id)
            _audit(db, x.id, "APPROVED", comment)
        db.commit()
        db.refresh(x)
        return _row(x, s)


def reject(leave_id, user, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status not in _REVIEW_NODES:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该请假当前状态不可驳回，请刷新")
        inst = _act_task(db, x, "REJECTED", reason.strip())
        x.affairs_status, x.status, x.return_reason = "REJECTED", "RETURNED", reason.strip()
        x.version += 1
        if inst:
            inst.status = "REJECTED"
        _todo_done(db, x.id)
        _msg(db, x.student_id, "请假被驳回", reason.strip(), "RETURNED_NOTICE", x.id)
        _audit(db, x.id, "REJECTED", reason.strip())
        db.commit()
        db.refresh(x)
        return _row(x, s)


def return_leave(leave_id, user, reason) -> dict:
    """退回申请人重提（区别于 reject 终态）。"""
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status not in _REVIEW_NODES:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该请假当前状态不可退回，请刷新")
        inst = _act_task(db, x, "TRANSFERRED", reason.strip())
        x.affairs_status, x.status, x.return_reason = "RETURNED", "RETURNED", reason.strip()
        x.version += 1
        if inst:
            inst.status = "RETURNED"
        _todo_done(db, x.id)
        _msg(db, x.student_id, "请假被退回", reason.strip(), "RETURNED_NOTICE", x.id)
        _audit(db, x.id, "RETURNED", reason.strip())
        db.commit()
        db.refresh(x)
        return _row(x, s)


def resubmit(leave_id, user) -> dict:
    """学生退回后重新提交 → 回到首个审批节点（新审批周期）。"""
    with session() as db:
        from app.models import WorkflowInstance, WorkflowTask
        x, s = _load(db, leave_id)
        if x.affairs_status != "RETURNED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅被退回的请假可重新提交")
        wf = _wf_code(float(x.days or 1))
        first = NODE_SEQ[wf][0]
        x.affairs_status, x.status, x.return_reason = first, _project(first), None
        x.version += 1
        inst = db.get(WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
        if inst:
            inst.status, inst.current_node = "RUNNING", first
        assignee = _assignee_for(db, first, x.student_id)
        db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id if inst else 0, node_code=first,
                            assignee_id=assignee, status="PENDING"))
        _todo_upsert(db, x.id, assignee, x.student_id, f"请假重新提交待审批：{s.real_name if s else ''}")
        _audit(db, x.id, "RESUBMIT")
        db.commit()
        db.refresh(x)
        return _row(x, s)


# ═══════════ 销假 ═══════════

def submit_cancel(leave_id, user, proof_note="") -> dict:
    with session() as db:
        from app.models import AffairsLeaveCancelRecord
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status not in ("APPROVED", "OVERDUE"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已通过/逾期的请假可发起销假")
        now = datetime.utcnow()
        rec = AffairsLeaveCancelRecord(tenant_id=_tid(), leave_id=x.id, student_id=x.student_id,
                                       actual_return_at=now, proof_note=proof_note, status="SUBMITTED",
                                       workflow_instance_id=x.workflow_instance_id)
        db.add(rec)
        x.affairs_status, x.status, x.actual_return_at = "WAIT_CANCEL_LEAVE", _project("WAIT_CANCEL_LEAVE"), now
        x.version += 1
        assignee = _assignee_for(db, "COUNSELOR_REVIEW", x.student_id)
        _todo_upsert(db, x.id, assignee, x.student_id,
                     f"销假待确认：{s.real_name if s else ''}", todo_type="LEAVE_CANCEL")
        _audit(db, x.id, "CANCEL_SUBMIT")
        db.commit()
        db.refresh(x)
        return _row(x, s)


def confirm_cancel(leave_id, user, note="") -> dict:
    with session() as db:
        from app.models import AffairsLeaveCancelRecord, StudentStageEvent
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status != "WAIT_CANCEL_LEAVE":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该请假不在待销假确认状态")
        rec = db.scalars(select(AffairsLeaveCancelRecord).where(
            AffairsLeaveCancelRecord.tenant_id == _tid(), AffairsLeaveCancelRecord.leave_id == x.id,
            AffairsLeaveCancelRecord.status == "SUBMITTED",
            AffairsLeaveCancelRecord.is_deleted.is_(False)).order_by(
            AffairsLeaveCancelRecord.id.desc())).first()
        n, _r, _u = _op()
        if rec:
            rec.status, rec.confirm_by, rec.confirm_at, rec.confirm_note = "CONFIRMED", n, datetime.utcnow(), note
            rec.version += 1
        x.affairs_status, x.status = "CLOSED", "APPROVED"
        x.version += 1
        # 进学生 360（成长时间线）
        if x.student_id:
            db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(x.student_id), from_stage=None,
                                     to_stage="LEAVE_CLOSED", reason=f"请假销假（{x.days}天）",
                                     source_module="student-affairs"))
        _todo_done(db, x.id, todo_type="LEAVE_CANCEL")
        _msg(db, x.student_id, "销假完成", "你的请假已销假归档", "STATUS_CHANGED", x.id)
        _audit(db, x.id, "CLOSED", note)
        db.commit()
        db.refresh(x)
        return _row(x, s)


# ═══════════ 续假 ═══════════

def apply_extension(leave_id, user, new_end, reason="") -> dict:
    with session() as db:
        from app.models import AffairsLeaveExtension
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status not in ("APPROVED", "OVERDUE"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已通过的请假可续假")
        ne = _parse_dt(new_end)
        if not ne or (x.end_time and ne <= x.end_time):
            raise AppException("VALIDATION_ERROR", "续假结束时间必须晚于原结束时间")
        ext_days = _days(x.end_time, ne)
        db.add(AffairsLeaveExtension(tenant_id=_tid(), leave_id=x.id, student_id=x.student_id,
                                     old_end_time=x.end_time, new_end_time=ne, extend_days=ext_days,
                                     reason=reason, status="SUBMITTED",
                                     workflow_instance_id=x.workflow_instance_id))
        x.affairs_status, x.status = "EXTENSION_REVIEW", _project("EXTENSION_REVIEW")
        x.version += 1
        assignee = _assignee_for(db, "COUNSELOR_REVIEW", x.student_id)
        _todo_upsert(db, x.id, assignee, x.student_id,
                     f"续假待审批：{s.real_name if s else ''}", todo_type="LEAVE_EXTENSION")
        _audit(db, x.id, "EXTENSION_SUBMIT", f"+{ext_days}天")
        db.commit()
        db.refresh(x)
        return _row(x, s)


def approve_extension(leave_id, user) -> dict:
    with session() as db:
        from app.models import AffairsLeaveExtension
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status != "EXTENSION_REVIEW":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该请假不在续假审批状态")
        ext = db.scalars(select(AffairsLeaveExtension).where(
            AffairsLeaveExtension.tenant_id == _tid(), AffairsLeaveExtension.leave_id == x.id,
            AffairsLeaveExtension.status == "SUBMITTED",
            AffairsLeaveExtension.is_deleted.is_(False)).order_by(
            AffairsLeaveExtension.id.desc())).first()
        if ext:
            ext.status = "APPROVED"
            ext.version += 1
            x.end_time = ext.new_end_time
            x.expected_return_at = ext.new_end_time
            x.days = _days(x.start_time, ext.new_end_time)
        x.affairs_status, x.status, x.overdue_pushed_at = "APPROVED", "APPROVED", None
        x.version += 1
        _todo_done(db, x.id, todo_type="LEAVE_EXTENSION")
        _msg(db, x.student_id, "续假已通过", f"续假已通过，新结束时间 {_iso(x.end_time)}", "WORKFLOW_RESULT", x.id)
        _audit(db, x.id, "EXTENSION_APPROVED")
        db.commit()
        db.refresh(x)
        return _row(x, s)


# ═══════════ 逾期扫描（幂等） ═══════════

def scan_overdue() -> dict:
    from app.models import CsLeave
    now = datetime.utcnow()
    with session() as db:
        rows = db.scalars(select(CsLeave).where(
            CsLeave.tenant_id == _tid(), CsLeave.affairs_status == "APPROVED",
            CsLeave.overdue_pushed_at.is_(None), CsLeave.expected_return_at.is_not(None),
            CsLeave.expected_return_at < now, CsLeave.is_deleted.is_(False))).all()
        cnt = 0
        for x in rows:
            x.affairs_status, x.status, x.overdue_pushed_at = "OVERDUE", "APPROVED", now
            x.version += 1
            assignee = _assignee_for(db, "COUNSELOR_REVIEW", x.student_id)
            _todo_upsert(db, x.id, assignee, x.student_id, "请假逾期未销假，请跟进",
                         todo_type="LEAVE_OVERDUE")
            _msg(db, x.student_id, "请假已逾期", "你的请假已到期未销假，请尽快销假", "DEADLINE_REMINDER", x.id)
            _audit(db, x.id, "OVERDUE")
            cnt += 1
        db.commit()
        return {"count": cnt}


# ═══════════ 查询 ═══════════

def get_detail(leave_id, user) -> dict:
    with session() as db:
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        return _row(x, s)


def list_pending(user, page=1, page_size=20):
    from app.models import CsLeave, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        rows = db.scalars(select(CsLeave).where(
            CsLeave.tenant_id == _tid(), CsLeave.is_deleted.is_(False),
            CsLeave.affairs_status.in_(list(_REVIEW_NODES))).order_by(CsLeave.id.desc())).all()
        out = []
        for x in rows:
            s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            out.append(_row(x, s))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total
