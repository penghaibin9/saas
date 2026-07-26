"""13A-P4 违纪处分闭环（11 态 + EFFECTIVE 事务内投影 t_cs_discipline + 解除子流程）。

登记→学院初审→学工处复核→(严重)校级→EFFECTIVE(投影 t_cs_discipline 一行,进360)；
解除：EFFECTIVE→REMOVE_REVIEW(辅→院→处三节点)→REMOVED(更新投影 record_status,进360,历史保留)。
硬约束：EFFECTIVE case 数 == ACTIVE 投影行数（对账口径）；EFFECTIVE 不可编辑(409)。
"""

from app.core.optimistic_lock import atomic_claim_version

from datetime import datetime

from sqlalchemy import func, select

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
                             occurred_at=datetime.utcnow()))


def _assignee_for(db, node, student_id):
    from app.services.affairs_assignee_service import require_assignee_id
    return require_assignee_id(db, node, student_id=student_id)


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


def _check_disc_node(db, node, user, *, workflow_instance_id=None, label_map=None):
    from app.core.affairs_security import build_affairs_context
    ctx = build_affairs_context(user, db)
    labels = label_map or L_DISC
    if not _disc_node_visible(ctx, node):
        raise AppException("NO_PERMISSION", f"无权审批当前节点（{labels.get(node, node)}）")
    if ctx.scope_type == "TENANT_ALL" or not workflow_instance_id:
        return
    from app.models import WorkflowTask
    task = db.scalars(select(WorkflowTask).where(
        WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == int(workflow_instance_id),
        WorkflowTask.node_code == node, WorkflowTask.status == "PENDING",
        WorkflowTask.is_deleted.is_(False)).order_by(WorkflowTask.id.desc())).first()
    if not task or not task.assignee_id:
        return
    uid = _uid_int(user)
    if uid and int(task.assignee_id) != uid:
        raise AppException("NO_PERMISSION", "当前审批任务未指派给您")


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
                           status="REGISTERED")
        db.add(x)
        db.flush()
        _audit(db, x.id, "REGISTER", body.discType)
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _row(x, s)


def submit(case_id, user, expected_version=None) -> dict:
    with session() as db:
        x, s = _load(db, case_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in ("REGISTERED", "RETURNED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅登记/退回的处分可提交")
        atomic_claim_version(db, x, expected_version)
        x.status, x.version = "COLLEGE_REVIEW", x.version + 1
        assignee = _assignee_for(db, "COLLEGE_REVIEW", x.student_id)
        if not x.workflow_instance_id:
            inst = _open_wf(db, "AFFAIRS_DISCIPLINE", "DISCIPLINE", x.id, x.student_id,
                            f"{s.real_name if s else ''} 违纪处分", "COLLEGE_REVIEW", assignee)
            x.workflow_instance_id = inst.id
        _todo_upsert(db, x.id, assignee, x.student_id, f"处分待初审：{s.real_name if s else ''}")
        _audit(db, x.id, "SUBMIT")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _row(x, s)


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
        return _row(x, s)


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


def _act_task(db, x, action, reason=""):
    from app.models import WorkflowInstance, WorkflowTask
    inst = db.get(WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
    if inst:
        task = db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == inst.id,
            WorkflowTask.node_code == x.status, WorkflowTask.status == "PENDING",
            WorkflowTask.is_deleted.is_(False))).first()
        if task:
            task.status, task.acted_at, task.action_reason = action, datetime.utcnow(), reason
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
        _check_disc_node(db, x.status, user, workflow_instance_id=x.workflow_instance_id)
        if action == "APPROVE":
            inst = _act_task(db, x, "APPROVED", reason or "")
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
                assignee = _assignee_for(db, nxt, x.student_id)
                db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=nxt,
                                    assignee_id=assignee, status="PENDING"))
                _todo_upsert(db, x.id, assignee, x.student_id,
                             f"处分待审（{L_DISC[nxt]}）：{s.real_name if s else ''}")
                _audit(db, x.id, "REVIEW_STEP", f"->{nxt}")
        elif action in ("REJECT", "RETURN"):
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回/退回原因必填且不少于 5 字")
            inst = _act_task(db, x, "REJECTED" if action == "REJECT" else "TRANSFERRED", reason.strip())
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
        return _row(x, s)


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
        return _row(x, s)


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
        return _row(x, s)


# ═══════════ 查询 / 对账 ═══════════

def get_case(case_id, user) -> dict:
    with session() as db:
        x, s = _load(db, case_id)
        _scope_or_403(db, x.student_id, user)
        return _row(x, s)


def list_cases(user, status=None, disc_type=None, page=1, page_size=20, student_id=None):
    from app.models import DisciplineCase, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.services.affairs_list_stats import status_counts_by_column
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        base_conds = [DisciplineCase.tenant_id == _tid(), DisciplineCase.is_deleted.is_(False)]
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
        rows = db.scalars(select(DisciplineCase)
                          .join(StudentProfile, StudentProfile.id == DisciplineCase.student_id)
                          .where(*conds, *student_conds).order_by(DisciplineCase.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        students = _students_by_ids(db, rows)
        return ([_row(x, students.get(int(x.student_id)) if x.student_id else None) for x in rows],
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
    """处分统计（按处分类型/状态聚合 + 投影对账）；数据范围与列表一致（辅导员限本班）。"""
    from app.models import DisciplineCase, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        rows = db.scalars(select(DisciplineCase).where(
            DisciplineCase.tenant_id == _tid(), DisciplineCase.is_deleted.is_(False))).all()
        students = _students_by_ids(db, rows)
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        total = 0
        for x in rows:
            s = students.get(int(x.student_id)) if x.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            total += 1
            by_type[x.disc_type] = by_type.get(x.disc_type, 0) + 1
            by_status[x.status] = by_status.get(x.status, 0) + 1
    return {"total": total,
            "byType": [{"key": k, "count": v} for k, v in by_type.items()],
            "byStatus": [{"key": k, "count": v} for k, v in by_status.items()],
            "reconcile": projection_reconcile()}


# ═══════════ 送达与申诉（C 包·决定与送达 / 申诉复核）═══════════

_DELIVERY = ("DIRECT", "MAIL", "PUBLIC", "LEAVE")
_L_APPEAL = {"SUBMITTED": "已提交", "REVIEWING": "复核中", "UPHELD": "维持原处分",
             "REVISED": "变更处分", "REVOKED": "撤销处分", "WITHDRAWN": "已撤回"}


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
        return _row(x, s)


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
        return _appeal_row(a, s)


def list_appeals(user, status=None, page=1, page_size=50):
    from app.models import DisciplineAppeal, DisciplineCase, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [DisciplineAppeal.tenant_id == _tid(), DisciplineAppeal.is_deleted.is_(False)]
        if status:
            conds.append(DisciplineAppeal.status == status)
        rows = db.scalars(select(DisciplineAppeal).where(*conds).order_by(
            DisciplineAppeal.id.desc())).all()
        students = _students_by_ids(db, rows)
        out = []
        for a in rows:
            s = students.get(int(a.student_id)) if a.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            out.append(_appeal_row(a, s))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


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
        s = db.get(StudentProfile, int(a.student_id)) if a.student_id else None
        return _appeal_row(a, s)
