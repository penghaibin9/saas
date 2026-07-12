"""13B-P2 学籍异动全链路（休学/复学/退学/转专业/留级）。

各类异动多节点审批（ACAD_STATUS_*），终审经 change_student_status() 单一入口生效。
真实业务补充：休学到期日(最长年限 suspendMaxYears，规则中心默认2年)；复学校验未超期；
转专业/复学终审同步迁移主档院系班。在途异动重复 409；终态学生禁发起 422。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.modules.academic_affairs.services.academic_affairs_status_service import (audit_status_change,
                                                          change_student_status, is_enrolled)
from app.services.db_service import _iso, _tid, session

# change_type → (目标学籍状态, 审批节点序列)
CHANGE_FLOW = {
    "SUSPEND": ("SUSPENDED", ["COUNSELOR_REVIEW", "COLLEGE_REVIEW", "AA_OFFICE_FINAL"]),
    "WITHDRAW": ("WITHDRAWN", ["COUNSELOR_REVIEW", "COLLEGE_REVIEW", "AA_OFFICE_FINAL"]),
    "RESUME": ("REGISTERED", ["COUNSELOR_REVIEW", "COLLEGE_ASSIGN_CLASS", "AA_OFFICE_FINAL"]),
    "RETAIN": ("RETAINED", ["COLLEGE_REVIEW", "AA_OFFICE_FINAL"]),
    "TRANSFER_MAJOR": ("REGISTERED", ["COUNSELOR_REVIEW", "OUT_COLLEGE_REVIEW",
                                      "IN_COLLEGE_REVIEW", "AA_OFFICE_FINAL"]),
}
_WF_CODE = {"SUSPEND": "ACAD_STATUS_SUSPEND", "WITHDRAW": "ACAD_STATUS_WITHDRAW",
            "RESUME": "ACAD_STATUS_RESUME", "RETAIN": "ACAD_STATUS_RETAIN",
            "TRANSFER_MAJOR": "ACAD_STATUS_TRANSFER_MAJOR"}
_ACTIVE = {"DRAFT", "SUBMITTED", "IN_REVIEW"}  # 在途（未终结）异动状态

L_CT = {"SUSPEND": "休学", "WITHDRAW": "退学", "RESUME": "复学", "RETAIN": "留级",
        "TRANSFER_MAJOR": "转专业"}


def _suspend_max_years() -> int:
    """规则中心 academicAffairs.status.suspendMaxYears，默认 2 年。"""
    from app.services.platform_service import get_config_json
    cfg = get_config_json(_tid(), "ACAD_RULE", "suspend_max_years")
    try:
        return int(cfg.get("years")) if cfg and cfg.get("years") else 2
    except (TypeError, ValueError):
        return 2


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_STATUS_CHANGE",
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n or uid, role_name=r, detail=detail, occurred_at=datetime.utcnow()))


def _assignee_for(db, node, student_id):
    if node in ("COUNSELOR_REVIEW",) and student_id:
        from app.models import SchoolClass, StudentProfile
        s = db.get(StudentProfile, int(student_id))
        if s and s.class_id:
            c = db.get(SchoolClass, int(s.class_id))
            if c and c.counselor_id:
                return int(c.counselor_id)
    return 0


def _open_wf(db, wf_code, sc_id, applicant_id, title, first_node, assignee):
    from app.models import WorkflowInstance, WorkflowTask
    inst = WorkflowInstance(tenant_id=_tid(), workflow_code=wf_code, source_module="academic-affairs",
                            source_biz_type="AA_STATUS_CHANGE", source_biz_id=int(sc_id),
                            applicant_id=int(applicant_id or 0), title=title, status="RUNNING",
                            current_node=first_node)
    db.add(inst)
    db.flush()
    db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=first_node,
                        assignee_id=int(assignee or 0), status="PENDING"))
    return inst


def _todo_upsert(db, sc_id, assignee, student_id, title):
    from app.models import UnifiedTodo
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "academic-affairs",
        UnifiedTodo.source_biz_id == int(sc_id), UnifiedTodo.todo_type == "AA_STATUS_APPROVAL",
        UnifiedTodo.assignee_id == int(assignee or 0), UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title, row.status, row.version = title, "PENDING", row.version + 1
    else:
        db.add(UnifiedTodo(tenant_id=_tid(), source_module="academic-affairs",
                           source_biz_type="AA_STATUS_CHANGE", source_biz_id=int(sc_id),
                           todo_type="AA_STATUS_APPROVAL", assignee_id=int(assignee or 0),
                           student_id=student_id, title=title, status="PENDING"))


def _todo_done(db, sc_id):
    from app.models import UnifiedTodo
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "academic-affairs",
            UnifiedTodo.source_biz_id == int(sc_id), UnifiedTodo.todo_type == "AA_STATUS_APPROVAL",
            UnifiedTodo.is_deleted.is_(False))).all():
        r.status, r.version = "DONE", r.version + 1


def _msg(db, receiver_id, title, content, mtype, sc_id):
    from app.models import UnifiedMessage
    db.add(UnifiedMessage(tenant_id=_tid(), receiver_id=int(receiver_id or 0),
                          source_module="academic-affairs", source_biz_id=int(sc_id),
                          title=title, content=content, message_type=mtype, status="UNREAD"))


def _row(x, s=None) -> dict:
    return {"changeId": str(x.id), "studentId": str(x.student_id),
            "realName": s.real_name if s else "", "changeType": x.change_type,
            "changeTypeLabel": L_CT.get(x.change_type, x.change_type),
            "fromStatus": x.from_status, "toStatus": x.to_status, "reason": x.reason or "",
            "status": x.status, "currentNode": x.current_node or "",
            "effectiveDate": _iso(x.effective_date), "expireDate": _iso(x.expire_date),
            "toClassId": str(x.to_class_id or ""), "toMajorId": str(x.to_major_id or ""),
            "version": x.version}


def _load(db, sc_id):
    from app.models import AaStatusChange, StudentProfile
    x = db.get(AaStatusChange, int(sc_id))
    if not x or x.is_deleted or x.tenant_id != _tid():
        raise not_found("异动单不存在")
    s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
    return x, s


# ═══════════ 发起异动 ═══════════

def submit(body, user) -> dict:
    ct = (body.changeType or "").upper()
    if ct not in CHANGE_FLOW:
        raise AppException("VALIDATION_ERROR", "异动类型非法")
    student_id = int(body.studentId)
    with session() as db:
        from app.models import AaStatusChange, StudentProfile
        s = db.get(StudentProfile, student_id)
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        cur = s.student_status
        # 终态学生禁发起
        if cur in ("MERGED", "RECYCLED", "WITHDRAWN", "GRADUATED"):
            raise AppException("VALIDATION_ERROR", f"学生已处于终态 {cur}，不可发起异动")
        # 前置状态校验（真实业务）
        if ct == "RESUME":
            if cur != "SUSPENDED":
                raise AppException("DATA_CONFLICT", "仅休学中的学生可申请复学")
            # 真实业务：休学超期未复学应作退学处理，禁复学
            prior = db.scalars(select(AaStatusChange).where(
                AaStatusChange.tenant_id == _tid(), AaStatusChange.student_id == student_id,
                AaStatusChange.change_type == "SUSPEND", AaStatusChange.status == "EFFECTIVE",
                AaStatusChange.is_deleted.is_(False)).order_by(AaStatusChange.id.desc())).first()
            if prior and prior.expire_date and prior.expire_date < datetime.utcnow():
                raise AppException("DATA_CONFLICT", "休学已超过最长年限，应作退学处理，不可复学")
        if ct in ("SUSPEND", "WITHDRAW", "RETAIN", "TRANSFER_MAJOR") and not is_enrolled(cur):
            raise AppException("DATA_CONFLICT", "仅在籍学生可发起该异动")
        # 在途异动重复 → 409
        dup = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == _tid(), AaStatusChange.student_id == student_id,
            AaStatusChange.status.in_(list(_ACTIVE)), AaStatusChange.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该生存在在途学籍异动，不可重复发起")
        to_status, nodes = CHANGE_FLOW[ct]
        first = nodes[0]
        x = AaStatusChange(tenant_id=_tid(), student_id=student_id, change_type=ct,
                           from_status=cur, to_status=to_status, reason=getattr(body, "reason", None),
                           from_college_id=s.college_id, from_major_id=s.major_id, from_class_id=s.class_id,
                           to_college_id=(int(body.toCollegeId) if getattr(body, "toCollegeId", None) else None),
                           to_major_id=(int(body.toMajorId) if getattr(body, "toMajorId", None) else None),
                           to_class_id=(int(body.toClassId) if getattr(body, "toClassId", None) else None),
                           status="SUBMITTED", current_node=first)
        # 休学到期日（真实补充：最长年限）
        if ct == "SUSPEND":
            x.expire_date = datetime.utcnow() + timedelta(days=365 * _suspend_max_years())
        db.add(x)
        db.flush()
        assignee = _assignee_for(db, first, student_id)
        inst = _open_wf(db, _WF_CODE[ct], x.id, student_id, f"{s.real_name} {L_CT[ct]}", first, assignee)
        x.workflow_instance_id = inst.id
        _todo_upsert(db, x.id, assignee, student_id, f"{L_CT[ct]}待审：{s.real_name}")
        _audit(db, x.id, "SUBMIT", ct)
        db.commit()
        db.refresh(x)
        return _row(x, s)


# ═══════════ 审批（多节点）═══════════

def review(sc_id, user, action, reason="") -> dict:
    action = (action or "").upper()
    _n, _r, uid = _op()
    with session() as db:
        from app.models import WorkflowInstance, WorkflowTask
        x, s = _load(db, sc_id)
        if x.status not in _ACTIVE and x.status != "IN_REVIEW":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该异动当前状态不可审批")
        nodes = CHANGE_FLOW[x.change_type][1]
        inst = db.get(WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
        task = db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == (inst.id if inst else 0),
            WorkflowTask.node_code == x.current_node, WorkflowTask.status == "PENDING",
            WorkflowTask.is_deleted.is_(False))).first() if inst else None
        if action in ("REJECT", "RETURN"):
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回/退回原因必填且不少于 5 字")
            if task:
                task.status, task.action_reason, task.acted_at = ("REJECTED" if action == "REJECT" else "TRANSFERRED"), reason.strip(), datetime.utcnow()
            x.status = "REJECTED" if action == "REJECT" else "RETURNED"
            x.version += 1
            if inst:
                inst.status = "REJECTED" if action == "REJECT" else "RETURNED"
            _todo_done(db, x.id)
            _msg(db, x.student_id, f"{L_CT[x.change_type]}{'未通过' if action == 'REJECT' else '被退回'}",
                 reason.strip(), "WORKFLOW_RESULT" if action == "REJECT" else "RETURNED_NOTICE", x.id)
            _audit(db, x.id, x.status, reason.strip())
            db.commit()
            db.refresh(x)
            return _row(x, s)
        if action != "APPROVE":
            raise AppException("VALIDATION_ERROR", "无效操作")
        if task:
            task.status, task.acted_at = "APPROVED", datetime.utcnow()
        i = nodes.index(x.current_node) if x.current_node in nodes else 0
        if i + 1 < len(nodes):
            nxt = nodes[i + 1]
            x.current_node, x.status, x.version = nxt, "IN_REVIEW", x.version + 1
            if inst:
                inst.current_node = nxt
            assignee = _assignee_for(db, nxt, x.student_id)
            db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=nxt,
                                assignee_id=assignee, status="PENDING"))
            _todo_upsert(db, x.id, assignee, x.student_id, f"{L_CT[x.change_type]}待审（{nxt}）：{s.real_name if s else ''}")
            _audit(db, x.id, "STEP", f"->{nxt}")
            db.commit()
            db.refresh(x)
            return _row(x, s)
        # 终审通过 → 经单一入口生效
        res = change_student_status(
            db, x.student_id, x.to_status, change_type=x.change_type, reason=x.reason or "",
            operator=uid, existing_change_id=x.id,
            to_college_id=x.to_college_id, to_major_id=x.to_major_id, to_class_id=x.to_class_id)
        if inst:
            inst.status = "APPROVED"
        _todo_done(db, x.id)
        _msg(db, x.student_id, f"{L_CT[x.change_type]}已生效",
             f"你的{L_CT[x.change_type]}申请已通过并生效", "WORKFLOW_RESULT", x.id)
        _audit(db, x.id, "EFFECTIVE", f"{res['fromStatus']}->{res['toStatus']}")
        db.commit()
        db.refresh(x)
        out = _row(x, s)
    audit_status_change(x.student_id, res["fromStatus"], res["toStatus"], x.change_type, uid)
    return out


# ═══════════ 查询 ═══════════

def get_change(sc_id, user) -> dict:
    with session() as db:
        x, s = _load(db, sc_id)
        return _row(x, s)


def list_changes(user, change_type=None, status=None, student_id=None, page=1, page_size=20):
    from app.models import AaStatusChange, StudentProfile
    with session() as db:
        conds = [AaStatusChange.tenant_id == _tid(), AaStatusChange.is_deleted.is_(False),
                 AaStatusChange.change_type != "ENROLL_REGISTER",
                 AaStatusChange.change_type != "ANNUAL_REGISTER"]
        if change_type:
            conds.append(AaStatusChange.change_type == change_type)
        if status:
            conds.append(AaStatusChange.status == status)
        if student_id:
            conds.append(AaStatusChange.student_id == int(student_id))
        join = and_(StudentProfile.id == AaStatusChange.student_id,
                    StudentProfile.tenant_id == AaStatusChange.tenant_id)
        total = db.scalar(select(func.count()).select_from(AaStatusChange)
                          .outerjoin(StudentProfile, join).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.execute(select(AaStatusChange, StudentProfile)
                          .outerjoin(StudentProfile, join).where(*conds)
                          .order_by(AaStatusChange.id.desc()).offset(offset).limit(page_size)).all()
        out = [_row(x, s) for x, s in rows]
        return out, total
