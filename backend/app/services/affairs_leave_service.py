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

# 请假类型标签（表单字段与校验规则 §3.1 枚举）
L_TYPE = {"SICK": "病假", "PERSONAL": "事假", "HOME": "探亲假", "HOSPITAL": "住院假",
          "GOOUT": "外出", "OTHER": "其他"}

# 台账/延期销假页可处理的"后续处理"活动态（请假审批终态后进入本模块）
FOLLOWUP_STATES = ("APPROVED", "EXTENSION_REVIEW", "WAIT_CANCEL_LEAVE", "OVERDUE")
OVERDUE_HANDLE_TYPES = {"CONTACT": "联系学生", "TO_HOME_SCHOOL": "转家校联系", "CLOSE": "处置完毕关闭"}


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
    from app.services.runtime_preset_install_service import ensure_workflow_enabled
    ensure_workflow_enabled(db, _tid(), wf_code)
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
        "studentNo": (s.student_no if s else "") or "",
        "studentName": s.real_name if s else "", "className": str(s.class_id or "") if s else "",
        "leaveType": x.leave_type, "leaveTypeLabel": L_TYPE.get(x.leave_type or "", x.leave_type or ""),
        "days": float(x.days or 0),
        "startTime": _iso(x.start_time), "endTime": _iso(x.end_time), "reason": x.reason or "",
        "affairsStatus": x.affairs_status,
        "affairsStatusLabel": L_AFF.get(x.affairs_status or "", x.affairs_status or ""),
        "legacyStatus": x.status,  # 投影列（老端点读这个，双状态列一致性）
        "workflowInstanceId": str(x.workflow_instance_id or ""),
        "expectedReturnAt": _iso(x.expected_return_at), "actualReturnAt": _iso(x.actual_return_at),
    }


def _resolve_class_names(db, rows: list[dict]) -> list[dict]:
    """把 _row 里的 className（当前为 class_id 字符串）解析成真实班级名（台账/列表可读性）。"""
    from app.models import SchoolClass
    ids = {r.get("className") for r in rows if r.get("className")}
    if not ids:
        return rows
    cmap = {str(c.id): c.class_name for c in db.scalars(
        select(SchoolClass).where(SchoolClass.tenant_id == _tid())).all()}
    for r in rows:
        cid = r.get("className")
        if cid and cid in cmap:
            r["className"] = cmap[cid]
    return rows


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


def _node_visible(ctx, node: str) -> bool:
    """按管理层级判断某审批节点是否对当前身份可见/可操作：
    TENANT_ALL（学工处/校级管理员）→ 任意节点；COLLEGE（学院管理员）→ 除学工处终审外任意节点
    （本院范围已由 _scope_or_403 的班级收敛保证）；其余（含辅导员）仅 COUNSELOR_REVIEW。"""
    if ctx.scope_type == "TENANT_ALL":
        return True
    if node == "STUDENT_AFFAIRS_REVIEW":
        return False
    if ctx.scope_type == "COLLEGE":
        return True
    return node == "COUNSELOR_REVIEW"


def _check_review_node(db, x, user):
    """审批节点身份校验（修复越权缺口）：既有 _scope_or_403 只校验学生是否在调用者的数据范围内，
    不校验当前 affairs_status 对应的审批节点是否轮到调用者审批。COUNSELOR 角色被授予
    studentAffairs.leave.* 通配权限，若无此校验，只要学生在其班级范围内，辅导员即可越级审批
    COLLEGE_REVIEW/STUDENT_AFFAIRS_REVIEW 环节，跳过学院/学工处审批。"""
    from app.core.affairs_security import build_affairs_context
    ctx = build_affairs_context(user, db)
    if not _node_visible(ctx, x.affairs_status):
        raise AppException("NO_PERMISSION",
                           f"无权审批当前节点（{L_AFF.get(x.affairs_status, x.affairs_status)}）")


# ═══════════ 申请 ═══════════

def apply_leave(body, user, *, skip_scope_check: bool = False) -> dict:
    # studentId 为字符串且无数字校验（campus_service schema），非数字直接 int() → 未捕获
    # ValueError → HTTP 500；改为显式校验返回 400 VALIDATION_ERROR（历史欠账收口）。
    raw_sid = str(getattr(body, "studentId", "") or "").strip()
    if not raw_sid.isdigit():
        raise AppException("VALIDATION_ERROR", "请选择有效学生")
    student_id = int(raw_sid)
    start = _parse_dt(body.startTime)
    end = _parse_dt(body.endTime)
    days = _days(start, end)
    with session() as db:
        from app.models import CsLeave, StudentProfile
        s = db.get(StudentProfile, student_id)
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在或不在数据范围内")
        # 数据范围：非全域角色只能为本范围学生代发起请假（与 approve/reject 等一致）。
        # skip_scope_check=True 仅供学生本人自助请假入口使用（studentId 已由服务端按登录身份解析，
        # 不接受客户端指定），不适用于辅导员等"代发起"场景。
        if not skip_scope_check:
            from app.services.affairs_dashboard_service import _allowed_class_ids
            _allowed, _ = _allowed_class_ids(db, user)
            if _allowed is not None and s.class_id not in _allowed:
                raise AppException("NO_DATA_SCOPE", "该学生不在您的数据范围内")
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
        return _resolve_class_names(db, [_row(x, s)])[0]


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
        _check_review_node(db, x, user)
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
        return _resolve_class_names(db, [_row(x, s)])[0]


def reject(leave_id, user, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status not in _REVIEW_NODES:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该请假当前状态不可驳回，请刷新")
        _check_review_node(db, x, user)
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
        return _resolve_class_names(db, [_row(x, s)])[0]


def return_leave(leave_id, user, reason) -> dict:
    """退回申请人重提（区别于 reject 终态）。"""
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status not in _REVIEW_NODES:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该请假当前状态不可退回，请刷新")
        _check_review_node(db, x, user)
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
        return _resolve_class_names(db, [_row(x, s)])[0]


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
        return _resolve_class_names(db, [_row(x, s)])[0]


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
        return _resolve_class_names(db, [_row(x, s)])[0]


def confirm_cancel(leave_id, user, action="CONFIRM", actual_return_at=None, reason="", note="") -> dict:
    """销假确认(CONFIRM→CLOSED进360) / 销假退回(RETURN→APPROVED，证明不符重新销假)。契约 #23。"""
    action = (action or "CONFIRM").upper()
    if action not in ("CONFIRM", "RETURN"):
        raise AppException("VALIDATION_ERROR", "action 仅支持 CONFIRM / RETURN")
    if action == "RETURN" and (not reason or len(reason.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "销假退回原因必填且不少于 5 字")
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
        if action == "RETURN":
            if rec:
                rec.status, rec.confirm_by, rec.confirm_at, rec.confirm_note = (
                    "RETURNED", n, datetime.utcnow(), reason.strip())
                rec.version += 1
            # 退回：回到 APPROVED 允许重新销假；若已过期则清逾期标记待重新扫描
            x.affairs_status, x.status = "APPROVED", "APPROVED"
            if x.expected_return_at and x.expected_return_at < datetime.utcnow():
                x.overdue_pushed_at = None
            x.version += 1
            _todo_done(db, x.id, todo_type="LEAVE_CANCEL")
            _msg(db, x.student_id, "销假被退回", reason.strip(), "RETURNED_NOTICE", x.id)
            _audit(db, x.id, "CANCEL_RETURN", reason.strip())
            db.commit()
            db.refresh(x)
            return _resolve_class_names(db, [_row(x, s)])[0]
        # CONFIRM：辅导员可校对/更正实际返校时间
        ret = _parse_dt(actual_return_at) if actual_return_at else None
        if ret:
            if x.start_time and ret < x.start_time:
                raise AppException("VALIDATION_ERROR", "实际返校时间不能早于请假开始时间")
            if ret > datetime.utcnow():
                raise AppException("VALIDATION_ERROR", "实际返校时间不能晚于当前时间")
        if rec:
            if ret:
                rec.actual_return_at = ret
            rec.status, rec.confirm_by, rec.confirm_at, rec.confirm_note = (
                "CONFIRMED", n, datetime.utcnow(), note)
            rec.version += 1
        if ret:
            x.actual_return_at = ret
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
        return _resolve_class_names(db, [_row(x, s)])[0]


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
        return _resolve_class_names(db, [_row(x, s)])[0]


def approve_extension(leave_id, user, action="APPROVE", reason="") -> dict:
    """续假审批：APPROVE（更新结束时间→APPROVED）/ REJECT（维持原假期与原到期日）。契约 #24。"""
    action = (action or "APPROVE").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 仅支持 APPROVE / REJECT")
    if action == "REJECT" and (not reason or len(reason.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "续假驳回原因必填且不少于 5 字")
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
        if action == "REJECT":
            if ext:
                ext.status = "REJECTED"
                ext.version += 1
            # 维持原假期与原到期日，仅回到 APPROVED
            x.affairs_status, x.status = "APPROVED", "APPROVED"
            x.version += 1
            _todo_done(db, x.id, todo_type="LEAVE_EXTENSION")
            _msg(db, x.student_id, "续假被驳回", reason.strip(), "WORKFLOW_RESULT", x.id)
            _audit(db, x.id, "EXTENSION_REJECTED", reason.strip())
            db.commit()
            db.refresh(x)
            return _resolve_class_names(db, [_row(x, s)])[0]
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
        return _resolve_class_names(db, [_row(x, s)])[0]


# ═══════════ 代登记销假 + 逾期处置 ═══════════

def proxy_cancel(leave_id, user, actual_return_at, note="") -> dict:
    """辅导员代登记销假（学生无法操作时）→ WAIT_CANCEL_LEAVE。契约 #26。"""
    with session() as db:
        from app.models import AffairsLeaveCancelRecord
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status not in ("APPROVED", "OVERDUE"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已通过/逾期的请假可代登记销假")
        ret = _parse_dt(actual_return_at)
        if not ret:
            raise AppException("VALIDATION_ERROR", "实际返校时间必填")
        if x.start_time and ret < x.start_time:
            raise AppException("VALIDATION_ERROR", "实际返校时间不能早于请假开始时间")
        if ret > datetime.utcnow():
            raise AppException("VALIDATION_ERROR", "实际返校时间不能晚于当前时间")
        exist = db.scalars(select(AffairsLeaveCancelRecord).where(
            AffairsLeaveCancelRecord.tenant_id == _tid(), AffairsLeaveCancelRecord.leave_id == x.id,
            AffairsLeaveCancelRecord.status == "SUBMITTED",
            AffairsLeaveCancelRecord.is_deleted.is_(False))).first()
        if exist:
            raise AppException("DATA_CONFLICT", "该请假已有进行中的销假记录")
        rec = AffairsLeaveCancelRecord(tenant_id=_tid(), leave_id=x.id, student_id=x.student_id,
                                       actual_return_at=ret, proof_note=note, status="SUBMITTED",
                                       workflow_instance_id=x.workflow_instance_id)
        db.add(rec)
        x.affairs_status, x.status, x.actual_return_at = "WAIT_CANCEL_LEAVE", _project("WAIT_CANCEL_LEAVE"), ret
        x.version += 1
        assignee = _assignee_for(db, "COUNSELOR_REVIEW", x.student_id)
        _todo_upsert(db, x.id, assignee, x.student_id,
                     f"销假待确认（代登记）：{s.real_name if s else ''}", todo_type="LEAVE_CANCEL")
        _audit(db, x.id, "CANCEL_PROXY", f"actual_return={_iso(ret)}")
        db.commit()
        db.refresh(x)
        return _resolve_class_names(db, [_row(x, s)])[0]


def handle_overdue(leave_id, user, handle_type, note="") -> dict:
    """逾期处置登记：CONTACT/TO_HOME_SCHOOL 留痕不改状态；CLOSE→CLOSED 进360。契约 #25 / 状态机 §1 OVERDUE 分支。"""
    handle_type = (handle_type or "").upper()
    if handle_type not in OVERDUE_HANDLE_TYPES:
        raise AppException("VALIDATION_ERROR", "handleType 仅支持 CONTACT / TO_HOME_SCHOOL / CLOSE")
    if not note or len(note.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处置说明必填且不少于 5 字")
    with session() as db:
        from app.models import StudentStageEvent
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status != "OVERDUE":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅逾期未销假的请假可登记逾期处置")
        if handle_type == "CLOSE":
            x.affairs_status, x.status = "CLOSED", "APPROVED"
            x.version += 1
            if x.student_id:
                db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(x.student_id), from_stage=None,
                                         to_stage="LEAVE_CLOSED", reason=f"逾期请假处置关闭（{x.days}天）",
                                         source_module="student-affairs"))
            _todo_done(db, x.id, todo_type="LEAVE_OVERDUE")
            _msg(db, x.student_id, "逾期请假已处置关闭", note.strip(), "STATUS_CHANGED", x.id)
            _audit(db, x.id, "OVERDUE_CLOSED", note.strip())
        else:
            _audit(db, x.id, f"OVERDUE_{handle_type}", note.strip())
        db.commit()
        db.refresh(x)
        return _resolve_class_names(db, [_row(x, s)])[0]


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
        from app.models import (AffairsAuditTrail, AffairsLeaveCancelRecord, AffairsLeaveExtension)
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        row = _resolve_class_names(db, [_row(x, s)])[0]
        cancels = db.scalars(select(AffairsLeaveCancelRecord).where(
            AffairsLeaveCancelRecord.tenant_id == _tid(), AffairsLeaveCancelRecord.leave_id == x.id,
            AffairsLeaveCancelRecord.is_deleted.is_(False)).order_by(
            AffairsLeaveCancelRecord.id.desc())).all()
        exts = db.scalars(select(AffairsLeaveExtension).where(
            AffairsLeaveExtension.tenant_id == _tid(), AffairsLeaveExtension.leave_id == x.id,
            AffairsLeaveExtension.is_deleted.is_(False)).order_by(
            AffairsLeaveExtension.id.desc())).all()
        trail = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == _tid(), AffairsAuditTrail.biz_type == "LEAVE",
            AffairsAuditTrail.biz_id == x.id).order_by(AffairsAuditTrail.id.asc())).all()
        row["cancelRecords"] = [{
            "id": str(c.id), "actualReturnAt": _iso(c.actual_return_at), "proofNote": c.proof_note or "",
            "status": c.status, "confirmBy": c.confirm_by or "", "confirmAt": _iso(c.confirm_at),
            "confirmNote": c.confirm_note or "",
        } for c in cancels]
        row["extensions"] = [{
            "id": str(e.id), "oldEndTime": _iso(e.old_end_time), "newEndTime": _iso(e.new_end_time),
            "extendDays": float(e.extend_days or 0), "reason": e.reason or "", "status": e.status,
        } for e in exts]
        row["auditTrail"] = [{
            "action": t.action, "operator": t.operator or "", "roleName": t.role_name or "",
            "detail": t.detail or "", "occurredAt": _iso(t.occurred_at),
        } for t in trail]
        return row


# ═══════════ 请假台账 / 统计 / 导出（本模块新增：13A-05 台账 + 统计口径）═══════════

def list_leaves(user, status=None, leave_type=None, class_id=None, keyword=None,
                date_start=None, date_end=None, followup_only=False, page=1, page_size=20):
    """请假台账/后续处理列表：全状态可筛，数据范围裁剪。followup_only=只取延期销假可处理的活动态。"""
    from app.models import CsLeave, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        q_rows = db.scalars(select(CsLeave).where(
            CsLeave.tenant_id == _tid(), CsLeave.is_deleted.is_(False),
            CsLeave.affairs_status.is_not(None)).order_by(CsLeave.id.desc())).all()
        ds, de = _parse_dt(date_start), _parse_dt(date_end)
        out = []
        for x in q_rows:
            s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            if followup_only and x.affairs_status not in FOLLOWUP_STATES:
                continue
            if status and x.affairs_status != status:
                continue
            if leave_type and x.leave_type != leave_type:
                continue
            if class_id and (not s or str(s.class_id or "") != str(class_id)):
                continue
            if keyword:
                k = str(keyword)
                if not (s and (k in (s.real_name or "") or k in (s.student_no or ""))):
                    continue
            if ds and x.start_time and x.start_time < ds:
                continue
            if de and x.start_time and x.start_time > de:
                continue
            out.append(_row(x, s))
        _resolve_class_names(db, out)
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def leave_stats(user, group_by="CLASS", date_start=None, date_end=None) -> dict:
    """请假统计：人数/天数/在假/待审/待销假/逾期/已销假 + 按班级/类型/状态下钻。契约 #27。"""
    from app.models import CsLeave, SchoolClass, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    gb = (group_by or "CLASS").upper()
    if gb not in ("CLASS", "TYPE", "STATUS"):
        gb = "CLASS"
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        rows = db.scalars(select(CsLeave).where(
            CsLeave.tenant_id == _tid(), CsLeave.is_deleted.is_(False),
            CsLeave.affairs_status.is_not(None))).all()
        ds, de = _parse_dt(date_start), _parse_dt(date_end)
        now = datetime.utcnow()
        stu_cache: dict = {}

        def _stu(sid):
            if sid not in stu_cache:
                stu_cache[sid] = db.get(StudentProfile, int(sid)) if sid else None
            return stu_cache[sid]

        students, total_days = set(), 0.0
        m = {"pendingReview": 0, "waitCancel": 0, "overdue": 0, "closed": 0, "onLeave": 0}
        buckets: dict = {}
        for x in rows:
            s = _stu(x.student_id)
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            if ds and x.start_time and x.start_time < ds:
                continue
            if de and x.start_time and x.start_time > de:
                continue
            aff = x.affairs_status
            if x.student_id:
                students.add(x.student_id)
            if aff in ("APPROVED", "CLOSED", "ARCHIVED", "OVERDUE", "WAIT_CANCEL_LEAVE", "EXTENSION_REVIEW"):
                total_days += float(x.days or 0)
            if aff in _REVIEW_NODES:
                m["pendingReview"] += 1
            elif aff == "WAIT_CANCEL_LEAVE":
                m["waitCancel"] += 1
            elif aff == "OVERDUE":
                m["overdue"] += 1
            elif aff == "CLOSED":
                m["closed"] += 1
            if aff == "APPROVED" and x.start_time and x.end_time and x.start_time <= now <= x.end_time:
                m["onLeave"] += 1
            key = (str(s.class_id or "") if s else "") if gb == "CLASS" else (
                (x.leave_type or "OTHER") if gb == "TYPE" else (aff or ""))
            b = buckets.setdefault(key, {"count": 0, "days": 0.0, "students": set()})
            b["count"] += 1
            b["days"] += float(x.days or 0)
            if x.student_id:
                b["students"].add(x.student_id)
        cls_names = {}
        if gb == "CLASS":
            cls_names = {str(c.id): c.class_name for c in db.scalars(
                select(SchoolClass).where(SchoolClass.tenant_id == _tid())).all()}

        def _label(key):
            if gb == "CLASS":
                return cls_names.get(key, f"班级{key}" if key else "未分班")
            if gb == "TYPE":
                return L_TYPE.get(key, key or "其他")
            return L_AFF.get(key, key)

        breakdown = [{
            "key": k, "label": _label(k), "count": v["count"],
            "days": round(v["days"], 1), "studentCount": len(v["students"]),
        } for k, v in sorted(buckets.items(), key=lambda kv: -kv[1]["count"])]
        return {
            "groupBy": gb,
            "metrics": [
                {"key": "leaveStudentCount", "label": "请假人数", "value": len(students), "unit": "人"},
                {"key": "totalDays", "label": "请假总天数", "value": round(total_days, 1), "unit": "天"},
                {"key": "onLeave", "label": "当前在假", "value": m["onLeave"], "unit": "人次"},
                {"key": "pendingReview", "label": "待审批", "value": m["pendingReview"], "unit": "件"},
                {"key": "waitCancel", "label": "待销假", "value": m["waitCancel"], "unit": "件"},
                {"key": "overdue", "label": "逾期未销", "value": m["overdue"], "unit": "件"},
                {"key": "closed", "label": "已销假", "value": m["closed"], "unit": "件"},
            ],
            "breakdown": breakdown,
        }


def export_leaves(user, status=None, leave_type=None, class_id=None, keyword=None,
                  date_start=None, date_end=None) -> dict:
    """请假台账导出（xlsx，水印 + 导出留痕）。契约 §16.2 affairs_leave 导出。"""
    from app.services import excel
    items_all, _ = list_leaves(user, status, leave_type, class_id, keyword,
                               date_start, date_end, page=1, page_size=1_000_000)
    export_items = [{
        "studentNo": it.get("studentNo", ""),
        "studentName": it.get("studentName", ""),
        "className": it.get("className", ""),
        "leaveType": it.get("leaveTypeLabel", ""),
        "days": it.get("days", 0),
        "startTime": it.get("startTime", ""),
        "endTime": it.get("endTime", ""),
        "expectedReturnAt": it.get("expectedReturnAt", ""),
        "actualReturnAt": it.get("actualReturnAt", ""),
        "statusLabel": it.get("affairsStatusLabel", ""),
        "reason": it.get("reason", ""),
    } for it in items_all]
    spec = excel.ExportSpec(
        module_key="student-affairs", biz_type="leave", sheet_title="请假台账",
        columns=[
            excel.ColumnSpec("studentNo", "学号"),
            excel.ColumnSpec("studentName", "姓名"),
            excel.ColumnSpec("className", "班级"),
            excel.ColumnSpec("leaveType", "请假类型"),
            excel.ColumnSpec("days", "天数"),
            excel.ColumnSpec("startTime", "开始时间"),
            excel.ColumnSpec("endTime", "结束时间"),
            excel.ColumnSpec("expectedReturnAt", "应返校时间"),
            excel.ColumnSpec("actualReturnAt", "实际返校时间"),
            excel.ColumnSpec("statusLabel", "状态"),
            excel.ColumnSpec("reason", "事由"),
        ],
        file_name="请假台账.xlsx",
    )
    n, _r, _u = _op()
    packed = excel.build_export(spec, export_items, operator_name=n, tenant_label=str(_tid()))
    with session() as db:
        _audit(db, None, "EXPORT", f"rows={packed.get('rowCount', len(export_items))}")
        db.commit()
    # 敏感导出安全审计（t_security_audit_log）：导出含学号/事由等个人信息，落 SENSITIVE_EXPORT。
    from app.services.db_service import audit_insert
    audit_insert("SENSITIVE_EXPORT", "leave_ledger",
                 {"rows": packed.get("rowCount", len(export_items)),
                  "filters": {"status": status, "leaveType": leave_type, "classId": class_id,
                              "keyword": keyword}}, "SUCCESS")
    return packed


def list_pending(user, page=1, page_size=20):
    """待审批队列：仅返回调用者数据范围内、且当前节点确实轮到其身份审批的请假
    （修复越权配套：避免辅导员在列表里看到无权处理的学院/学工处环节数据）。"""
    from app.models import CsLeave, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.core.affairs_security import build_affairs_context
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        ctx = build_affairs_context(user, db)
        rows = db.scalars(select(CsLeave).where(
            CsLeave.tenant_id == _tid(), CsLeave.is_deleted.is_(False),
            CsLeave.affairs_status.in_(list(_REVIEW_NODES))).order_by(CsLeave.id.desc())).all()
        out = []
        for x in rows:
            if not _node_visible(ctx, x.affairs_status):
                continue
            s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            out.append(_row(x, s))
        _resolve_class_names(db, out)  # list_leaves 已有此转换，list_pending 此前遗漏（className 一直回数字 class_id）
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total
