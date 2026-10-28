"""13A-P4 违纪处分闭环（11 态 + EFFECTIVE 事务内投影 t_cs_discipline + 解除子流程）。

登记→学院初审→学工处复核→(严重)校级→EFFECTIVE(投影 t_cs_discipline 一行,进360)；
解除：EFFECTIVE→REMOVE_REVIEW(辅→院→处三节点)→REMOVED(更新投影 record_status,进360,历史保留)。
硬约束：EFFECTIVE case 数 == ACTIVE 投影行数（对账口径）；EFFECTIVE 不可编辑(409)。
"""

from app.core.optimistic_lock import atomic_claim_version

from datetime import datetime

from sqlalchemy import and_, false, func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.core.pagination import normalize_page
from app.services.db_service import _iso, _tid, session

DISC_TYPES = ("WARNING", "SERIOUS_WARNING", "DEMERIT", "PROBATION", "EXPEL")
_SEVERE = ("PROBATION", "EXPEL")  # 需校级审批
REMOVE_NODES = ["COUNSELOR_REVIEW", "COLLEGE_REVIEW", "SA_OFFICE_FINAL"]

L_DISC = {
    "REGISTERED": "已登记", "COLLEGE_REVIEW": "学院初审", "STUDENT_AFFAIRS_REVIEW": "学工处复核",
    "SCHOOL_REVIEW": "校级审批", "EFFECTIVE": "已生效", "REJECTED": "已驳回", "RETURNED": "已退回",
    "CANCELLED": "已撤销", "REMOVE_REVIEW": "解除审批中", "REMOVED": "已解除", "ARCHIVED": "已归档",
}

_DELIVERY = ("DIRECT", "MAIL", "PUBLIC", "LEAVE")

_L_APPEAL = {
    "SUBMITTED": "待复核", "REVIEWING": "复核中",
    "UPHELD": "维持原决定", "REVISED": "已变更", "REVOKED": "已撤销",
}


def _students_by_ids(db, rows, attr="student_id"):
    """批量取回 rows 涉及的学生档案 {id: StudentProfile}，替代列表循环内逐行 db.get（消 N+1）。"""
    from app.models import StudentProfile
    sids = {int(getattr(x, attr)) for x in rows if getattr(x, attr, None)}
    if not sids:
        return {}
    return {s.id: s for s in db.scalars(select(StudentProfile).where(StudentProfile.id.in_(sids))).all()}


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


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


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="DISCIPLINE", biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow(), created_by=_uid_int(get_current_user_ctx())))


def _assignee_for(db, node, student_id, *, exclude_user_ids=()):
    from app.services.affairs_assignee_service import require_assignee_id
    return require_assignee_id(db, node, student_id=student_id, exclude_user_ids=exclude_user_ids)


def _open_wf(db, wf_code, biz_type, biz_id, applicant_id, title, first_node, assignee_id):
    from app.models import WorkflowInstance, WorkflowTask
    from app.services.runtime_preset_install_service import ensure_workflow_enabled
    ensure_workflow_enabled(db, _tid(), wf_code)
    if int(assignee_id or 0) <= 0:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", f"未配置受理人：{first_node}")
    inst = WorkflowInstance(tenant_id=_tid(), workflow_code=wf_code, source_module="student-affairs",
                            source_biz_type=biz_type, source_biz_id=int(biz_id),
                            applicant_id=int(applicant_id or 0), title=title, status="RUNNING",
                            current_node=first_node)
    db.add(inst)
    db.flush()
    db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=first_node,
                        assignee_id=int(assignee_id or 0), status="PENDING"))
    return inst


def _todo_upsert(db, biz_id, assignee_id, student_id, title, todo_type="DISCIPLINE_APPROVAL"):
    from app.models import UnifiedTodo
    if int(assignee_id or 0) <= 0:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", "处分待办没有具体受理人")
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_id == int(biz_id), UnifiedTodo.todo_type == todo_type,
        UnifiedTodo.assignee_id == int(assignee_id or 0),
        UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title, row.status, row.version = title, "PENDING", row.version + 1
    else:
        db.add(UnifiedTodo(tenant_id=_tid(), source_module="student-affairs", source_biz_type="DISCIPLINE",
                           source_biz_id=int(biz_id), todo_type=todo_type,
                           assignee_id=int(assignee_id or 0), student_id=student_id, title=title,
                           status="PENDING"))


def _todo_done(db, biz_id, todo_type="DISCIPLINE_APPROVAL"):
    from app.models import UnifiedTodo
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.source_biz_id == int(biz_id), UnifiedTodo.todo_type == todo_type,
            UnifiedTodo.is_deleted.is_(False))).all():
        r.status, r.version = "DONE", r.version + 1


def _msg(db, receiver_id, title, content, mtype, biz_id):
    from app.services.message_event_outbox_service import emit_receiver_notice
    emit_receiver_notice(
        db,
        event_code="DISCIPLINE.NOTICE",
        source_module="student-affairs",
        source_biz_type="discipline",
        source_biz_id=int(biz_id),
        receiver_id=receiver_id,
        title=title,
        content=content,
        receiver_as="student",
        dedup_extra=mtype,
    )



def _drain_message_outbox():
    from app.services.message_event_outbox_service import try_process_pending_outbox
    try_process_pending_outbox(worker_id="discipline-inline")


def _scope_or_403(db, student_id, user):
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is None:
        return
    s = db.get(StudentProfile, int(student_id)) if student_id else None
    if not s or s.class_id not in allowed:
        raise AppException("NO_DATA_SCOPE", "该处分不在您的数据范围内")


def _uid_int(user) -> int:
    raw = str((user or {}).get("userId") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _disc_node_visible(ctx, node: str) -> bool:
    """处分/解除节点可见性：学工处复核、校级审批、解除处终审仅 TENANT_ALL；
    学院仅 COLLEGE_REVIEW；辅导员仅 COUNSELOR_REVIEW（解除初审）。"""
    if ctx.scope_type == "TENANT_ALL":
        return True
    if node in ("STUDENT_AFFAIRS_REVIEW", "SCHOOL_REVIEW", "SA_OFFICE_FINAL"):
        return False
    if ctx.scope_type == "COLLEGE":
        return node == "COLLEGE_REVIEW"
    return node == "COUNSELOR_REVIEW"


def _check_disc_node(db, node, user, *, workflow_instance_id=None, label_map=None, student_id=None):
    from app.core.affairs_security import build_affairs_context
    ctx = build_affairs_context(user, db)
    labels = label_map or L_DISC
    if not _disc_node_visible(ctx, node):
        raise AppException("NO_PERMISSION", f"无权审批当前节点（{labels.get(node, node)}）")
    if not workflow_instance_id:
        raise AppException("DATA_CONFLICT", "处分审批流缺失，请先核实历史单据并配置受理人")
    from app.models import WorkflowTask
    task = db.scalars(select(WorkflowTask).where(
        WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == int(workflow_instance_id),
        WorkflowTask.node_code == node, WorkflowTask.status == "PENDING",
        WorkflowTask.is_deleted.is_(False)).order_by(WorkflowTask.id.desc())).first()
    if not task or int(task.assignee_id or 0) <= 0:
        raise AppException("DATA_CONFLICT", "当前审批节点缺少有效受理人，请先配置或交接任务")
    uid = _uid_int(user)
    if uid <= 0:
        raise AppException("NO_PERMISSION", "当前账号缺少可核验的受理人身份")
    if int(task.assignee_id) != uid:
        raise AppException("NO_PERMISSION", "当前审批任务未指派给您")
    _check_review_membership(db, user, node, student_id=student_id)


def _check_review_membership(db, user, node, *, student_id=None):
    from app.services.affairs_assignee_service import _NODE_ROLES, resolve_assignee_ids
    role = str(user.get("currentRoleCode") or "").upper()
    roles = {"COUNSELOR"} if node in {"COUNSELOR_REVIEW", "CLASS_REVIEW"} else _NODE_ROLES.get(node, set())
    if role not in roles or _uid_int(user) not in resolve_assignee_ids(db, node, student_id=student_id, role_codes={role}):
        raise AppException("NO_PERMISSION", "当前职责不是该节点的有效审核任职，请切换并核验授权")


def _registrar(case):
    if not case.created_by or int(case.created_by) <= 0:
        raise AppException("DATA_CONFLICT", "历史登记人尚无法核实，原处分及材料保留，请先核验交接")
    return int(case.created_by)


def _decision_reviewers(db, case):
    from app.services.affairs_assignee_service import completed_review_actor_ids
    nodes = {"COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW"}
    if case.disc_type in _SEVERE:
        nodes.add("SCHOOL_REVIEW")
    return completed_review_actor_ids(db, case.workflow_instance_id, nodes)


def _appeal_assignee(db, case, *, preferred_id=None):
    from app.services.affairs_assignee_service import require_assignee_id, resolve_assignee_ids
    excluded = _decision_reviewers(db, case)
    if preferred_id and int(preferred_id) not in excluded and int(preferred_id) in resolve_assignee_ids(db, "SA_OFFICE_REVIEW", student_id=case.student_id):
        return int(preferred_id)
    return require_assignee_id(db, "SA_OFFICE_REVIEW", student_id=case.student_id, exclude_user_ids=excluded)


def _check_appeal_review(db, appeal, case, user):
    from app.models import UnifiedTodo
    uid = _uid_int(user)
    if uid in _decision_reviewers(db, case):
        raise AppException("NO_PERMISSION", "原决定审核人不得复核对应申诉，请转其他有权人员")
    _check_review_membership(db, user, "SA_OFFICE_REVIEW", student_id=case.student_id)
    from app.core.affairs_security import require_school_scope
    require_school_scope(db, user)
    todo = db.scalar(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_type == "DISCIPLINE_APPEAL", UnifiedTodo.source_biz_id == appeal.id,
        UnifiedTodo.student_id == appeal.student_id, UnifiedTodo.todo_type == "DISCIPLINE_APPEAL_REVIEW",
        UnifiedTodo.status == "PENDING", UnifiedTodo.is_deleted.is_(False),
    ).order_by(UnifiedTodo.id.desc()).with_for_update())
    if not todo or not todo.assignee_id:
        raise AppException("DATA_CONFLICT", "本申诉缺少有效待办受理人，请先核验交接")
    if int(todo.assignee_id) != uid:
        raise AppException("NO_PERMISSION", "本申诉未指派给当前人员")


def _cs_student_id(db, student_id):
    """全局学生 → 在校服务台账 id（投影用）；无台账行时退回全局 id（degraded，非空即可）。"""
    from app.models import CsServiceStudent
    cs = db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == _tid(), CsServiceStudent.student_id == int(student_id),
        CsServiceStudent.is_deleted.is_(False))).first()
    return cs.id if cs else int(student_id)


def _row(x, s=None) -> dict:
    return {
        "caseId": str(x.id), "studentId": str(x.student_id),
        "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
        "discType": x.disc_type, "reason": x.reason or "", "docNo": x.doc_no or "",
        "status": x.status, "statusLabel": L_DISC.get(x.status, x.status),
        "effectiveAt": _iso(x.effective_at), "removedAt": _iso(x.removed_at),
        "csDisciplineId": str(x.cs_discipline_id or ""), "version": x.version,
        "deliveredAt": _iso(getattr(x, "delivered_at", None)),
        "deliveryMethod": getattr(x, "delivery_method", None) or "",
    }


def _load(db, case_id):
    from app.models import DisciplineCase, StudentProfile
    x = db.get(DisciplineCase, int(case_id))
    if not x or x.is_deleted or x.tenant_id != _tid():
        raise not_found("处分记录不存在")
    s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
    return x, s


# ═══════════ 登记 / 提交 ═══════════

def _req_int(v, field):
    """必填数字字段安全转 int：非数字→400（原裸 int() 抛 ValueError→500）。"""
    raw = str(v or "").strip()
    if not raw.isdigit():
        raise AppException("VALIDATION_ERROR", f"请选择有效{field}")
    return int(raw)


def register(body, user) -> dict:
    if (body.discType or "") not in DISC_TYPES:
        raise AppException("VALIDATION_ERROR", "处分类型非法")
    if not (body.reason or "").strip() or len((body.reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "违纪事实必填且不少于 5 字")
    with session() as db:
        from app.models import DisciplineCase, StudentProfile
        s = db.get(StudentProfile, _req_int(getattr(body, "studentId", None), "学生"))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在或不在数据范围内")
        _scope_or_403(db, s.id, user)
        x = DisciplineCase(tenant_id=_tid(), student_id=s.id, disc_type=body.discType,
                           reason=body.reason.strip(), doc_no=getattr(body, "docNo", None),
                           status="REGISTERED", created_by=_uid_int(user))
        db.add(x)
        db.flush()
        _audit(db, x.id, "REGISTER", body.discType)
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _present_case(db, x, s, user)


def submit(case_id, user, expected_version=None) -> dict:
    with session() as db:
        x, s = _load(db, case_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in ("REGISTERED", "RETURNED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅登记/退回的处分可提交")
        was_returned = x.status == "RETURNED"
        if was_returned and not x.workflow_instance_id:
            raise AppException("DATA_CONFLICT", "历史退回单缺少原流程，记录保留，请先核验交接")
        atomic_claim_version(db, x, expected_version)
        x.status, x.version = "COLLEGE_REVIEW", x.version + 1
        assignee = _assignee_for(db, "COLLEGE_REVIEW", x.student_id)
        if not x.workflow_instance_id:
            inst = _open_wf(db, "AFFAIRS_DISCIPLINE", "DISCIPLINE", x.id, x.student_id,
                            f"{s.real_name if s else ''} 违纪处分", "COLLEGE_REVIEW", assignee)
            x.workflow_instance_id = inst.id
        else:
            from app.models import WorkflowInstance, WorkflowTask
            inst = db.get(WorkflowInstance, int(x.workflow_instance_id))
            if (not was_returned or not inst or inst.tenant_id != _tid() or inst.is_deleted
                    or inst.source_module != "student-affairs" or inst.source_biz_type != "DISCIPLINE"
                    or int(inst.source_biz_id or 0) != int(x.id)):
                raise AppException("DATA_CONFLICT", "原处分流程关联异常，记录保留，请先核验")
            if db.scalar(select(WorkflowTask.id).where(WorkflowTask.tenant_id == _tid(),
                    WorkflowTask.instance_id == inst.id, WorkflowTask.status == "PENDING", WorkflowTask.is_deleted.is_(False)).limit(1)):
                raise AppException("DATA_CONFLICT", "原流程仍有待审任务，拒绝重复创建，请先核验")
            inst.status, inst.current_node = "RUNNING", "COLLEGE_REVIEW"
            db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code="COLLEGE_REVIEW",
                assignee_id=assignee, status="PENDING", created_by=_uid_int(user)))
        _todo_upsert(db, x.id, assignee, x.student_id, f"处分待初审：{s.real_name if s else ''}")
        _audit(db, x.id, "SUBMIT")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _present_case(db, x, s, user)


def cancel(case_id, user, expected_version=None) -> dict:
    with session() as db:
        x, s = _load(db, case_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in ("REGISTERED", "RETURNED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅登记/退回的处分可撤销")
        atomic_claim_version(db, x, expected_version)
        x.status, x.version = "CANCELLED", x.version + 1
        _todo_done(db, x.id)
        _audit(db, x.id, "CANCELLED")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _present_case(db, x, s, user)


# ═══════════ 审批 ═══════════

def _make_effective(db, x, s):
    """EFFECTIVE：事务内投影 t_cs_discipline 一行 + 进 360 + 统计。"""
    from app.models import CsDiscipline, StudentStageEvent
    proj = CsDiscipline(tenant_id=_tid(), cs_student_id=_cs_student_id(db, x.student_id),
                        disc_type=x.disc_type, reason=x.reason, decide_date=x.decide_date,
                        doc_no=x.doc_no, status="EFFECTIVE", record_status="ACTIVE",
                        source_case_id=x.id)
    db.add(proj)
    db.flush()
    x.cs_discipline_id = proj.id
    x.status, x.effective_at, x.version = "EFFECTIVE", datetime.utcnow(), x.version + 1
    db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(x.student_id), from_stage=None,
                             to_stage="DISCIPLINE_EFFECTIVE",
                             reason=f"处分生效（{x.disc_type}）", source_module="student-affairs"))
    _todo_done(db, x.id)
    _msg(db, x.student_id, "处分决定送达", f"你的处分（{x.disc_type}）已生效", "WORKFLOW_RESULT", x.id)
    _audit(db, x.id, "EFFECTIVE", f"proj={proj.id}")


def _act_task(db, x, action, reason="", *, actor_id=None):
    from app.models import WorkflowInstance, WorkflowTask
    inst = db.get(WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
    if inst:
        task = db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == inst.id,
            WorkflowTask.node_code == x.status, WorkflowTask.status == "PENDING",
            WorkflowTask.is_deleted.is_(False)).order_by(WorkflowTask.id.desc())).first()
        if task:
            task.status, task.acted_at, task.action_reason = action, datetime.utcnow(), reason
            task.updated_by = actor_id or _uid_int(get_current_user_ctx())
            if str(task.remark or "").startswith("TRANSFER_TO:"):
                task.remark = None
            task.version += 1
    return inst


def review(case_id, user, action, reason="", expected_version=None) -> dict:
    action = (action or "").upper()
    with session() as db:
        from app.models import WorkflowTask
        x, s = _load(db, case_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in ("COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW", "SCHOOL_REVIEW"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该处分当前状态不可审批，请刷新")
        atomic_claim_version(db, x, expected_version)
        _check_disc_node(db, x.status, user, workflow_instance_id=x.workflow_instance_id, student_id=x.student_id)
        if x.status in ("STUDENT_AFFAIRS_REVIEW", "SCHOOL_REVIEW") and _uid_int(user) == _registrar(x):
            raise AppException("NO_PERMISSION", "处分登记人不能担任该处分的正式复核人")
        if action == "APPROVE":
            inst = _act_task(db, x, "APPROVED", reason or "", actor_id=_uid_int(user))
            if x.status == "COLLEGE_REVIEW":
                nxt = "STUDENT_AFFAIRS_REVIEW"
            elif x.status == "STUDENT_AFFAIRS_REVIEW":
                nxt = "SCHOOL_REVIEW" if x.disc_type in _SEVERE else "EFFECTIVE"
            else:  # SCHOOL_REVIEW
                nxt = "EFFECTIVE"
            if nxt == "EFFECTIVE":
                if inst:
                    inst.status = "APPROVED"
                _make_effective(db, x, s)
            else:
                x.status, x.version = nxt, x.version + 1
                if inst:
                    inst.current_node = nxt
                assignee = _assignee_for(db, nxt, x.student_id, exclude_user_ids={_registrar(x)})
                db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=nxt,
                                    assignee_id=assignee, status="PENDING"))
                _todo_upsert(db, x.id, assignee, x.student_id,
                             f"处分待审（{L_DISC[nxt]}）：{s.real_name if s else ''}")
                _audit(db, x.id, "REVIEW_STEP", f"->{nxt}")
        elif action in ("REJECT", "RETURN"):
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回/退回原因必填且不少于 5 字")
            inst = _act_task(db, x, "REJECTED" if action == "REJECT" else "TRANSFERRED", reason.strip(), actor_id=_uid_int(user))
            new = "REJECTED" if action == "REJECT" else "RETURNED"
            x.status, x.return_reason, x.version = new, reason.strip(), x.version + 1
            if inst and action == "REJECT":
                inst.status = "REJECTED"
            _todo_done(db, x.id)
            _msg(db, x.student_id, f"处分{'不予立案' if action == 'REJECT' else '被退回'}", reason.strip(),
                 "WORKFLOW_RESULT" if action == "REJECT" else "RETURNED_NOTICE", x.id)
            _audit(db, x.id, new, reason.strip())
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _present_case(db, x, s, user)


# ═══════════ 解除子流程 ═══════════

def submit_remove(case_id, user, reason="", expected_version=None) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "解除理由必填且不少于 5 字")
    with session() as db:
        from app.models import DisciplineRemoveApply
        x, s = _load(db, case_id)
        _scope_or_403(db, x.student_id, user)
        if x.status != "EFFECTIVE":
            raise AppException("DATA_CONFLICT", "处分未生效或已解除，不可发起解除")
        atomic_claim_version(db, x, expected_version)
        # 在途解除申请查重 → 409
        dup = db.scalars(select(DisciplineRemoveApply).where(
            DisciplineRemoveApply.tenant_id == _tid(), DisciplineRemoveApply.case_id == x.id,
            DisciplineRemoveApply.status.notin_(["APPROVED", "REJECTED"]),
            DisciplineRemoveApply.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该处分已有在途解除申请")
        first = REMOVE_NODES[0]
        ra = DisciplineRemoveApply(tenant_id=_tid(), case_id=x.id, student_id=x.student_id,
                                   apply_reason=reason.strip(), min_months_check=True,
                                   status="COUNSELOR_REVIEW", current_node=first)
        db.add(ra)
        db.flush()
        inst = _open_wf(db, "AFFAIRS_DISCIPLINE_REMOVE", "DISCIPLINE_REMOVE", ra.id, x.student_id,
                        f"{s.real_name if s else ''} 处分解除", first, _assignee_for(db, first, x.student_id))
        ra.workflow_instance_id = inst.id
        x.status, x.version = "REMOVE_REVIEW", x.version + 1
        _todo_upsert(db, x.id, _assignee_for(db, first, x.student_id), x.student_id,
                     f"处分解除待初审：{s.real_name if s else ''}", todo_type="DISCIPLINE_REMOVE")
        _audit(db, x.id, "REMOVE_SUBMIT")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _present_case(db, x, s, user)


def review_remove(case_id, user, action, reason="", expected_version=None) -> dict:
    """解除审批：辅→院→处三节点推进；终审通过→REMOVED（更新投影 record_status，进360）。"""
    action = (action or "").upper()
    with session() as db:
        from app.models import CsDiscipline, DisciplineRemoveApply, StudentStageEvent
        x, s = _load(db, case_id)
        _scope_or_403(db, x.student_id, user)
        if x.status != "REMOVE_REVIEW":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该处分不在解除审批状态")
        atomic_claim_version(db, x, expected_version)
        ra = db.scalars(select(DisciplineRemoveApply).where(
            DisciplineRemoveApply.tenant_id == _tid(), DisciplineRemoveApply.case_id == x.id,
            DisciplineRemoveApply.status.notin_(["APPROVED", "REJECTED"]),
            DisciplineRemoveApply.is_deleted.is_(False)).order_by(
            DisciplineRemoveApply.id.desc())).first()
        if not ra:
            raise AppException("APPROVAL_VERSION_CONFLICT", "解除申请不存在")
        _check_disc_node(db, ra.current_node or REMOVE_NODES[0], user,
                         workflow_instance_id=ra.workflow_instance_id,
                         student_id=x.student_id,
                         label_map={"COUNSELOR_REVIEW": "辅导员初审", "COLLEGE_REVIEW": "学院复核",
                                    "SA_OFFICE_FINAL": "学工处终审"})
        from app.models import WorkflowInstance, WorkflowTask
        inst = db.get(WorkflowInstance, int(ra.workflow_instance_id)) if ra.workflow_instance_id else None

        def _complete_remove_task(result: str, why: str = ""):
            if not inst:
                return
            task = db.scalars(select(WorkflowTask).where(
                WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == inst.id,
                WorkflowTask.node_code == (ra.current_node or REMOVE_NODES[0]),
                WorkflowTask.status == "PENDING", WorkflowTask.is_deleted.is_(False)
            ).order_by(WorkflowTask.id.desc())).first()
            if task:
                task.status, task.acted_at, task.action_reason = result, datetime.utcnow(), why
                task.version += 1

        if action == "REJECT":
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
            _complete_remove_task("REJECTED", reason.strip())
            if inst:
                inst.status = "REJECTED"
            ra.status, ra.return_reason = "REJECTED", reason.strip()
            x.status, x.version = "EFFECTIVE", x.version + 1  # 回生效，可再申请
            _todo_done(db, x.id, todo_type="DISCIPLINE_REMOVE")
            _msg(db, x.student_id, "处分解除未通过", reason.strip(), "WORKFLOW_RESULT", x.id)
            _audit(db, x.id, "REMOVE_REJECTED", reason.strip())
        elif action == "APPROVE":
            i = REMOVE_NODES.index(ra.current_node) if ra.current_node in REMOVE_NODES else 0
            _complete_remove_task("APPROVED", reason or "")
            if i + 1 < len(REMOVE_NODES):
                nxt = REMOVE_NODES[i + 1]
                ra.current_node, ra.status = nxt, nxt
                assignee = _assignee_for(db, nxt, x.student_id)
                if inst:
                    inst.current_node = nxt
                    db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=nxt,
                                        assignee_id=assignee, status="PENDING"))
                _todo_upsert(db, x.id, assignee, x.student_id,
                             f"处分解除待审（{nxt}）：{s.real_name if s else ''}", todo_type="DISCIPLINE_REMOVE")
                _audit(db, x.id, "REMOVE_STEP", f"->{nxt}")
            else:
                # 学工处终审通过 → REMOVED + 更新投影行
                ra.status = "APPROVED"
                if inst:
                    inst.status = "APPROVED"
                x.status, x.removed_at, x.version = "REMOVED", datetime.utcnow(), x.version + 1
                if x.cs_discipline_id:
                    proj = db.get(CsDiscipline, int(x.cs_discipline_id))
                    if proj:
                        proj.record_status, proj.revoke_date, proj.revoke_reason = \
                            "REVOKED", datetime.utcnow(), (ra.apply_reason or "")
                db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(x.student_id), from_stage=None,
                                         to_stage="DISCIPLINE_REMOVED", reason="处分解除",
                                         source_module="student-affairs"))
                _todo_done(db, x.id, todo_type="DISCIPLINE_REMOVE")
                _msg(db, x.student_id, "处分已解除", "你的处分已解除，奖助/评优资格恢复", "WORKFLOW_RESULT", x.id)
                _audit(db, x.id, "REMOVED")
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _present_case(db, x, s, user)


# ═══════════ 查询 / 对账 ═══════════

def get_case(case_id, user) -> dict:
    """处分单条详情：仅在 detail 读取最新申诉摘要，避免主列表逐行查询。"""
    with session() as db:
        from app.models import DisciplineAppeal
        x, s = _load(db, case_id)
        _scope_or_403(db, x.student_id, user)
        row = _present_case(db, x, s, user)
        appeal = db.scalars(select(DisciplineAppeal).where(
            DisciplineAppeal.tenant_id == _tid(), DisciplineAppeal.case_id == int(x.id),
            DisciplineAppeal.is_deleted.is_(False)
        ).order_by(DisciplineAppeal.id.desc())).first()
        row["appealSummary"] = None if not appeal else {
            "appealId": str(appeal.id), "status": appeal.status,
            "statusLabel": _L_APPEAL.get(appeal.status, appeal.status), "result": appeal.result or None,
        }
        return row


def _pending_conditions(db, user, kind):
    from sqlalchemy import case, false
    from app.core.affairs_security import build_affairs_context
    from app.models import DisciplineCase, DisciplineRemoveApply, WorkflowTask

    actor_id = _uid_int(user)
    if actor_id <= 0:
        return [false()]
    ctx = build_affairs_context(user, db)
    from app.services.affairs_assignee_service import _NODE_ROLES, _active_user_ids_for_roles
    role = str(user.get("currentRoleCode") or "").upper()
    if actor_id not in _active_user_ids_for_roles(db, {role}):
        return [false()]
    remove_query = select(DisciplineRemoveApply).where(
        DisciplineRemoveApply.tenant_id == _tid(),
        DisciplineRemoveApply.case_id == DisciplineCase.id,
        DisciplineRemoveApply.status.notin_(["APPROVED", "REJECTED"]),
        DisciplineRemoveApply.is_deleted.is_(False),
    ).order_by(DisciplineRemoveApply.id.desc()).limit(1).correlate(DisciplineCase)
    remove_flow = remove_query.with_only_columns(DisciplineRemoveApply.workflow_instance_id).scalar_subquery()
    remove_node = remove_query.with_only_columns(DisciplineRemoveApply.current_node).scalar_subquery()
    is_remove = DisciplineCase.status == "REMOVE_REVIEW"
    flow_id = case((is_remove, remove_flow), else_=DisciplineCase.workflow_instance_id)
    node = case((is_remove, func.coalesce(func.nullif(remove_node, ""), REMOVE_NODES[0])),
                else_=DisciplineCase.status)
    owner = select(WorkflowTask.assignee_id).where(
        WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == flow_id,
        WorkflowTask.node_code == node, WorkflowTask.status == "PENDING",
        WorkflowTask.is_deleted.is_(False),
    ).order_by(WorkflowTask.id.desc()).limit(1).correlate(DisciplineCase).scalar_subquery()
    statuses = ["COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW", "SCHOOL_REVIEW", "REMOVE_REVIEW"]
    if kind == "DISCIPLINE_REMOVE":
        statuses = ["REMOVE_REVIEW"]
    elif kind == "DISCIPLINE_APPROVAL":
        statuses.remove("REMOVE_REVIEW")
    visible = [value for value in set(statuses + REMOVE_NODES) if _disc_node_visible(ctx, value)
        and role in ({"COUNSELOR"} if value in {"COUNSELOR_REVIEW", "CLASS_REVIEW"} else _NODE_ROLES.get(value, set()))]
    registrar_valid = or_(is_remove, and_(DisciplineCase.created_by > 0,
        or_(~node.in_(("STUDENT_AFFAIRS_REVIEW", "SCHOOL_REVIEW")), DisciplineCase.created_by != actor_id)))
    return [DisciplineCase.status.in_(statuses), node.in_(visible), owner == actor_id, registrar_valid]


_CASE_ACTION_PERMISSIONS = {"SUBMIT": "discipline.create", "CANCEL": "discipline.create",
    "APPROVE": "discipline.approve", "RETURN": "discipline.approve", "REJECT": "discipline.approve",
    "REMOVE_APPROVE": "discipline.remove.approve", "REMOVE_REJECT": "discipline.remove.approve",
    "DELIVER": "discipline.deliver", "REMOVE": "discipline.remove.create", "APPEAL": "discipline.appeal.create"}


def _permitted_case_actions(user):
    from app.core.permissions import permission_decisions
    decisions = permission_decisions(user, ("studentAffairs." + code for code in set(_CASE_ACTION_PERMISSIONS.values())))
    return {action for action, code in _CASE_ACTION_PERMISSIONS.items() if decisions["studentAffairs." + code]}


def _present_case(db, row, student, user, *, review_allowed=None, permitted_actions=None):
    from app.models import DisciplineCase
    data = _row(row, student)
    permitted_actions = _permitted_case_actions(user) if permitted_actions is None else permitted_actions
    data["allowedActions"] = [action for action in data.get("allowedActions", []) if action in permitted_actions]
    if row.status in ("COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW", "SCHOOL_REVIEW", "REMOVE_REVIEW"):
        if review_allowed is None:
            review_allowed = db.scalar(select(DisciplineCase.id).where(DisciplineCase.id == row.id,
                DisciplineCase.tenant_id == _tid(), *_pending_conditions(db, user, "ALL"))) is not None
        if not review_allowed:
            data["allowedActions"] = []
    return data


def list_cases(user, status=None, disc_type=None, page=1, page_size=20, student_id=None, *, pending_kind=None):
    from app.models import DisciplineCase, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.services.affairs_list_stats import status_counts_by_column
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        base_conds = [DisciplineCase.tenant_id == _tid(), DisciplineCase.is_deleted.is_(False)]
        if pending_kind:
            base_conds.extend(_pending_conditions(db, user, pending_kind))
        if disc_type:
            base_conds.append(DisciplineCase.disc_type == disc_type)
        if student_id:
            try:
                base_conds.append(DisciplineCase.student_id == int(student_id))
            except (TypeError, ValueError):
                return [], 0, {"ALL": 0}
        conds = list(base_conds)
        if status:
            statuses = [item.strip() for item in status.split(",") if item.strip()]
            conds.append(DisciplineCase.status.in_(statuses))
        student_conds = [
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ]
        status_counts = status_counts_by_column(
            db, DisciplineCase, DisciplineCase.status, [*base_conds, *student_conds],
            join_student=StudentProfile, allowed_class_ids=allowed,
        )
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        page, page_size = normalize_page(page, page_size)
        total = int(db.scalar(select(func.count()).select_from(DisciplineCase)
                              .join(StudentProfile, StudentProfile.id == DisciplineCase.student_id)
                              .where(*conds, *student_conds)) or 0)
        can_review = and_(*_pending_conditions(db, user, "ALL"))
        result = db.execute(select(DisciplineCase, can_review.label("can_review"))
                          .join(StudentProfile, StudentProfile.id == DisciplineCase.student_id)
                          .where(*conds, *student_conds).order_by(DisciplineCase.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        rows = [row for row, _ in result]
        students = _students_by_ids(db, rows)
        permitted_actions = _permitted_case_actions(user)
        return ([_present_case(db, x, students.get(int(x.student_id)) if x.student_id else None,
                    user, review_allowed=permitted, permitted_actions=permitted_actions) for x, permitted in result],
                total, status_counts)


def projection_reconcile() -> dict:
    """对账：EFFECTIVE case 数 == ACTIVE 投影行数（source_case_id 非空）。"""
    from app.models import CsDiscipline, DisciplineCase
    with session() as db:
        eff = db.scalar(select(func.count()).select_from(DisciplineCase).where(
            DisciplineCase.tenant_id == _tid(), DisciplineCase.status == "EFFECTIVE",
            DisciplineCase.is_deleted.is_(False))) or 0
        proj = db.scalar(select(func.count()).select_from(CsDiscipline).where(
            CsDiscipline.tenant_id == _tid(), CsDiscipline.source_case_id.is_not(None),
            CsDiscipline.record_status == "ACTIVE", CsDiscipline.is_deleted.is_(False))) or 0
        return {"effectiveCases": eff, "activeProjections": proj, "consistent": eff == proj}


def discipline_stats(user) -> dict:
    """处分统计：数据库按处分类型/状态聚合，数据范围与列表一致。"""
    from app.models import DisciplineCase, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        base = [
            DisciplineCase.tenant_id == _tid(),
            DisciplineCase.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ]
        if allowed is not None:
            base.append(StudentProfile.class_id.in_(allowed or {-1}))
        type_rows = db.execute(
            select(DisciplineCase.disc_type, func.count(DisciplineCase.id))
            .join(StudentProfile, StudentProfile.id == DisciplineCase.student_id)
            .where(*base).group_by(DisciplineCase.disc_type)
        ).all()
        status_rows = db.execute(
            select(DisciplineCase.status, func.count(DisciplineCase.id))
            .join(StudentProfile, StudentProfile.id == DisciplineCase.student_id)
            .where(*base).group_by(DisciplineCase.status)
        ).all()
        by_type = {str(key or ""): int(count or 0) for key, count in type_rows}
        by_status = {str(key or ""): int(count or 0) for key, count in status_rows}
    return {
        "total": sum(by_status.values()),
        "byType": [{"key": key, "count": count} for key, count in by_type.items()],
        "byStatus": [{"key": key, "count": count} for key, count in by_status.items()],
        "reconcile": projection_reconcile(),
    }

def deliver_case(case_id, body, user) -> dict:
    """登记决定书送达（仅 EFFECTIVE 处分可送达；记方式/时间）。"""
    from datetime import datetime
    from app.models import StudentProfile
    method = (getattr(body, "method", "") or "").strip()
    if method not in _DELIVERY:
        raise AppException("VALIDATION_ERROR", "送达方式非法")
    with session() as db:
        x, s = _load(db, case_id)
        _scope_or_403(db, x.student_id, user)
        if x.status != "EFFECTIVE":
            raise AppException("DATA_CONFLICT", "仅已生效处分可登记送达")
        atomic_claim_version(db, x, getattr(body, "version", None))
        x.delivered_at, x.delivery_method = datetime.utcnow(), method
        x.delivery_remark, x.version = getattr(body, "remark", None), x.version + 1
        _audit(db, x.id, "DISCIPLINE_DELIVER", method)
        db.commit(); db.refresh(x)
        _drain_message_outbox()
        return _present_case(db, x, s, user)


def _appeal_row(a, s=None) -> dict:
    return {"appealId": str(a.id), "caseId": str(a.case_id), "studentId": str(a.student_id or ""),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "reason": a.reason or "", "status": a.status, "statusLabel": _L_APPEAL.get(a.status, a.status),
            "result": a.result or "", "reviewOpinion": a.review_opinion or "",
            "reviewer": a.reviewer or "", "reviewedAt": _iso(a.reviewed_at)}


def submit_appeal(case_id, body, user, *, skip_scope_check: bool = False) -> dict:
    """提起申诉（EFFECTIVE 后；同一 case 不得有进行中的申诉）。理由≥5字。
    skip_scope_check=True 仅供学生本人自助申诉入口使用（case_id 已由调用方核验属于本人）。"""
    from app.models import DisciplineAppeal, StudentProfile
    reason = (getattr(body, "reason", "") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申诉理由至少 5 字")
    with session() as db:
        x, s = _load(db, case_id)
        if not skip_scope_check:
            _scope_or_403(db, x.student_id, user)
        if x.status != "EFFECTIVE":
            raise AppException("DATA_CONFLICT", "仅已生效处分可申诉")
        from app.services import affairs_appeal_todo_service as appeal_todo
        appeal_todo.require_submission_assignee(db, "DISCIPLINE_APPEAL_REVIEW", int(x.student_id))
        # 一案一诉：已有任何申诉（含已结案）不得再提，避免结案后反复申诉绕过复核结论。
        prior = db.scalars(select(DisciplineAppeal).where(
            DisciplineAppeal.tenant_id == _tid(), DisciplineAppeal.case_id == int(case_id),
            DisciplineAppeal.is_deleted.is_(False))).first()
        if prior:
            raise AppException("DATA_CONFLICT", "该处分已提交过申诉，不可再次提起")
        a = DisciplineAppeal(tenant_id=_tid(), case_id=int(case_id), student_id=x.student_id,
                             reason=reason, status="SUBMITTED")
        db.add(a); db.flush()
        _audit(db, x.id, "DISCIPLINE_APPEAL_SUBMIT", "")
        db.commit(); db.refresh(a)
        _drain_message_outbox()
        s = db.get(StudentProfile, int(x.student_id))
        result_row = _appeal_row(a, s)
        return appeal_todo.sync_after_submit("DISCIPLINE_APPEAL_REVIEW", result_row, "appealId", "id")


def _appeal_review_predicate(db, user):
    from app.core.affairs_security import require_school_scope
    from app.core.permissions import has_permission
    from app.models import DisciplineAppeal, DisciplineCase, UnifiedTodo, WorkflowTask
    if not has_permission(user, "studentAffairs.discipline.appeal.review"):
        return false()
    try:
        require_school_scope(db, user)
        _check_review_membership(db, user, "SA_OFFICE_REVIEW")
    except AppException:
        return false()
    uid = _uid_int(user)
    def approved(node):
        return select(WorkflowTask.id).where(
            WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == DisciplineCase.workflow_instance_id,
            WorkflowTask.node_code == node, WorkflowTask.status == "APPROVED", WorkflowTask.acted_at.is_not(None),
            WorkflowTask.updated_by > 0, WorkflowTask.is_deleted.is_(False),
        ).exists()
    bad_actor = select(WorkflowTask.id).where(
        WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == DisciplineCase.workflow_instance_id,
        WorkflowTask.node_code.in_(("COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW", "SCHOOL_REVIEW")),
        WorkflowTask.acted_at.is_not(None), WorkflowTask.status.in_(("APPROVED", "REJECTED", "TRANSFERRED")),
        WorkflowTask.is_deleted.is_(False),
        or_(WorkflowTask.status != "TRANSFERRED", WorkflowTask.remark.is_(None), ~WorkflowTask.remark.like("TRANSFER_TO:%")),
        or_(WorkflowTask.updated_by.is_(None), WorkflowTask.updated_by <= 0, WorkflowTask.updated_by == uid),
    ).exists()
    source = select(DisciplineCase.id).where(
        DisciplineCase.tenant_id == _tid(), DisciplineCase.id == DisciplineAppeal.case_id,
        DisciplineCase.is_deleted.is_(False), DisciplineCase.status == "EFFECTIVE",
        approved("COLLEGE_REVIEW"), approved("STUDENT_AFFAIRS_REVIEW"),
        or_(~DisciplineCase.disc_type.in_(_SEVERE), approved("SCHOOL_REVIEW")), ~bad_actor,
    ).exists()
    todo = select(UnifiedTodo.id).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_type == "DISCIPLINE_APPEAL", UnifiedTodo.source_biz_id == DisciplineAppeal.id,
        UnifiedTodo.student_id == DisciplineAppeal.student_id, UnifiedTodo.todo_type == "DISCIPLINE_APPEAL_REVIEW",
        UnifiedTodo.status == "PENDING", UnifiedTodo.assignee_id == uid, UnifiedTodo.is_deleted.is_(False),
    ).exists()
    return and_(DisciplineAppeal.status.in_(("SUBMITTED", "REVIEWING")), source, todo)


def list_appeals(user, status=None, page=1, page_size=50, case_id=None, appeal_id=None, pending_only=False):
    from app.models import DisciplineAppeal, DisciplineCase, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [DisciplineAppeal.tenant_id == _tid(), DisciplineAppeal.is_deleted.is_(False)]
        if status:
            conds.append(DisciplineAppeal.status == status)
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        can_review = _appeal_review_predicate(db, user)
        if pending_only:
            conds.append(can_review)
        if case_id not in (None, ""):
            try:
                conds.append(DisciplineAppeal.case_id == int(case_id))
            except (TypeError, ValueError):
                return [], 0
        if appeal_id not in (None, ""):
            try:
                conds.append(DisciplineAppeal.id == int(appeal_id))
            except (TypeError, ValueError):
                return [], 0
        relation = and_(StudentProfile.id == DisciplineAppeal.student_id,
                        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))
        total = int(db.scalar(select(func.count()).select_from(DisciplineAppeal).outerjoin(StudentProfile, relation).where(*conds)) or 0)
        result = db.execute(select(DisciplineAppeal, can_review.label("can_review")).outerjoin(StudentProfile, relation)
            .where(*conds).order_by(DisciplineAppeal.id.desc()).offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        rows = [row for row, _ in result]
        students = _students_by_ids(db, rows)
        out = []
        for a, permitted in result:
            s = students.get(int(a.student_id)) if a.student_id else None
            item = _appeal_row(a, s)
            item["allowedActions"] = ["REVIEW"] if permitted else []
            if not permitted and a.status in ("SUBMITTED", "REVIEWING"):
                item["reviewBlockReason"] = "当前身份不是本单可办受理人，或历史审核证据尚待核验，请核对职责与交接。"
            out.append(item)
        return out, total


def review_appeal(appeal_id, body, user) -> dict:
    """申诉复核：result UPHELD维持/REVISED变更/REVOKED撤销。REVOKED→原处分不再有效(投影下线)。"""
    from datetime import datetime
    from app.models import CsDiscipline, DisciplineAppeal, StudentProfile, StudentStageEvent
    result = (getattr(body, "result", "") or "").strip()
    if result not in ("UPHELD", "REVISED", "REVOKED"):
        raise AppException("VALIDATION_ERROR", "复核结论非法")
    opinion = (getattr(body, "opinion", "") or "").strip()
    if len(opinion) < 5:
        raise AppException("VALIDATION_ERROR", "复核意见至少 5 字")
    with session() as db:
        a = db.get(DisciplineAppeal, int(appeal_id))
        if not a or a.is_deleted or a.tenant_id != _tid():
            raise not_found("申诉不存在")
        _scope_or_403(db, a.student_id, user)
        if a.status not in ("SUBMITTED", "REVIEWING"):
            raise AppException("DATA_CONFLICT", "该申诉已结案")
        atomic_claim_version(db, a, getattr(body, "version", None))
        status_map = {"UPHELD": "UPHELD", "REVISED": "REVISED", "REVOKED": "REVOKED"}
        a.status, a.result = status_map[result], result
        a.review_opinion, a.reviewer = opinion, _op()[0]
        a.reviewed_at, a.version = datetime.utcnow(), a.version + 1
        if result == "REVOKED":
            x, _cs = _load(db, a.case_id)
            if x.status == "EFFECTIVE":
                x.status, x.removed_at, x.version = "REMOVED", datetime.utcnow(), x.version + 1
                if x.cs_discipline_id:
                    proj = db.get(CsDiscipline, int(x.cs_discipline_id))
                    if proj:
                        proj.record_status, proj.revoke_date, proj.revoke_reason = \
                            "REVOKED", datetime.utcnow(), opinion
                db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(x.student_id), from_stage=None,
                                         to_stage="DISCIPLINE_REMOVED", reason="申诉复核撤销处分",
                                         source_module="student-affairs"))
                _todo_done(db, x.id)
                _msg(db, x.student_id, "处分已撤销", "你的申诉已获支持，原处分决定已撤销", "WORKFLOW_RESULT", x.id)
        _audit(db, a.case_id, "DISCIPLINE_APPEAL_REVIEW", result)
        db.commit(); db.refresh(a)
        _drain_message_outbox()
        s = db.scalars(select(StudentProfile).where(
            StudentProfile.id == int(a.student_id), StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False)
        )).first() if a.student_id else None
        result_row = _appeal_row(a, s)
        from app.services import affairs_appeal_todo_service as appeal_todo
        return appeal_todo.sync_after_review("DISCIPLINE_APPEAL_REVIEW", int(appeal_id), result_row)
