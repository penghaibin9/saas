"""13B-R2 调停课（SM-08，workflow_code=ACAD_SCHEDULE_CHANGE）。

对齐正方/强智调停课：教师就已发布课表项发起调课/停课/补课，提交即做目标课位三重冲突预检
(复用 schedule_service._detect_conflict，冲突则 422/409 不落库)；审批链学院审→教务处审；
终审通过后系统改写课表——原课位标 CHANGED 保留历史(禁直接 UPDATE 已发布项、不动发布批次)，
调课/补课生成新课表项并回链本单(new_item_id + schedule_item.change_id)，STATUS_CHANGED 通知师生。

数据范围(COURSE)：教师仅可就本人任课课位发起(teacher_key 命中)；TENANT_ALL 角色(教务处/校管)代办放行；
学院教务员按所辖班级可见。越范围 → 403 NO_DATA_SCOPE。撤销仅限 SUBMITTED/COLLEGE_REVIEW，APPROVED 后 409。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, select

from app.core.affairs_security import _derive_keys, build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.modules.academic_affairs.services.academic_affairs_schedule_service import _detect_conflict
from app.services.db_service import _iso, _tid, session

WORKFLOW_CODE = "ACAD_SCHEDULE_CHANGE"
CHANGE_TYPES = {"ADJUST", "STOP", "MAKEUP"}
L_CT = {"ADJUST": "调课", "STOP": "停课", "MAKEUP": "补课"}
# 审批节点序列（学院审 → 教务处审）
NODES = ["COLLEGE_REVIEW", "ACADEMIC_REVIEW"]
# 各节点 PENDING 时对应的单据状态
_NODE_STATUS = {"COLLEGE_REVIEW": "SUBMITTED", "ACADEMIC_REVIEW": "COLLEGE_REVIEW"}
_CANCELLABLE = {"SUBMITTED", "COLLEGE_REVIEW"}       # 终审前可撤销
_ACTIVE = {"SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW"}  # 在途（含终审中）


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _op_uid() -> int | None:
    """解析当前操作者的真实数字 user_id：真实账号登录的 userId 形如 'db-N'（剥离前缀取数字）；
    mock 演示登录形如 'u_xxx' 无法解析为数字，返回 None（对齐 mobile_student_service._resolve_uid
    同款「解析不到就不勉强填」的约定）。此前 `uid.isdigit()` 未剥离 'db-' 前缀，导致 applicant_id
    在真实账号登录下也恒为 None，APPLIED 通知回退成 receiver_id=0（广播语义），与调停课通知
    「精确送达，不用 receiver_id=0」的设计要求（施工包 D-11）相悖，此处修正。"""
    v = str((get_current_user_ctx() or {}).get("userId") or "")
    if v.startswith("db-"):
        v = v[3:]
    return int(v) if v.isdigit() else None


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_SCHEDULE_CHANGE",
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n or uid, role_name=r, detail=detail, occurred_at=datetime.utcnow()))


def _msg(db, receiver_id, title, content, mtype, biz_id):
    from app.services.message_event_outbox_service import emit_receiver_notice
    code = "SCHEDULE_CHANGE.RETURNED" if "RETURNED" in (mtype or "").upper() else "SCHEDULE_CHANGE.RESULT"
    emit_receiver_notice(
        db,
        event_code=code,
        source_module="academic-affairs",
        source_biz_type="AA_SCHEDULE_CHANGE",
        source_biz_id=int(biz_id),
        receiver_id=receiver_id,
        title=title,
        content=content,
        receiver_as="user",
        dedup_extra=mtype,
    )


def _open_wf(db, cid, applicant_id, title, first_node):
    from app.models import WorkflowInstance, WorkflowTask
    from app.services.runtime_preset_install_service import ensure_workflow_enabled
    ensure_workflow_enabled(db, _tid(), WORKFLOW_CODE)
    inst = WorkflowInstance(tenant_id=_tid(), workflow_code=WORKFLOW_CODE, source_module="academic-affairs",
                            source_biz_type="AA_SCHEDULE_CHANGE", source_biz_id=int(cid),
                            applicant_id=int(applicant_id or 0), title=title, status="RUNNING",
                            current_node=first_node)
    db.add(inst)
    db.flush()
    db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=first_node,
                        assignee_id=0, status="PENDING"))
    return inst


def _todo_upsert(db, cid, node, title):
    from app.models import UnifiedTodo
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "academic-affairs",
        UnifiedTodo.source_biz_id == int(cid), UnifiedTodo.todo_type == "AA_SCHEDULE_CHANGE_APPROVAL",
        UnifiedTodo.assignee_id == 0, UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title, row.status, row.remark, row.version = title, "PENDING", node, row.version + 1
    else:
        db.add(UnifiedTodo(tenant_id=_tid(), source_module="academic-affairs",
                           source_biz_type="AA_SCHEDULE_CHANGE", source_biz_id=int(cid),
                           todo_type="AA_SCHEDULE_CHANGE_APPROVAL", assignee_id=0,
                           title=title, status="PENDING", remark=node))


def _todo_done(db, cid):
    from app.models import UnifiedTodo
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "academic-affairs",
            UnifiedTodo.source_biz_id == int(cid), UnifiedTodo.todo_type == "AA_SCHEDULE_CHANGE_APPROVAL",
            UnifiedTodo.is_deleted.is_(False))).all():
        r.status, r.version = "DONE", r.version + 1


def _row(x) -> dict:
    return {
        "changeId": str(x.id), "changeType": x.change_type,
        "changeTypeLabel": L_CT.get(x.change_type, x.change_type),
        "termId": str(x.term_id or ""), "batchId": str(x.batch_id or ""),
        "originItemId": str(x.origin_item_id or ""), "taskId": str(x.task_id or ""),
        "courseName": x.course_name or "", "className": x.class_name or "",
        "classId": str(x.class_id or ""), "teacherName": x.teacher_name or "",
        "teacherKey": x.teacher_key or "",
        "origin": {"weekday": x.origin_weekday, "slotNo": x.origin_slot_no,
                   "startWeek": x.origin_start_week, "endWeek": x.origin_end_week,
                   "weekParity": x.origin_week_parity, "classroom": x.origin_classroom or ""},
        "target": {"weekday": x.target_weekday, "slotNo": x.target_slot_no,
                   "startWeek": x.target_start_week, "endWeek": x.target_end_week,
                   "weekParity": x.target_week_parity, "classroom": x.target_classroom or ""},
        "makeupPlan": x.makeup_plan or "", "reason": x.reason or "",
        "status": x.status, "currentNode": x.current_node or "",
        "newItemId": str(x.new_item_id or ""), "appliedAt": _iso(x.applied_at),
        "createdAt": _iso(x.created_at), "version": x.version,
    }


def _load(db, cid):
    from app.models import AaScheduleChange
    x = db.get(AaScheduleChange, int(cid))
    if not x or x.is_deleted or x.tenant_id != _tid():
        raise not_found("调停课单不存在")
    return x


def _can_manage_all(ctx) -> bool:
    return ctx.scope_type == "TENANT_ALL"


_TERMINAL_STATES = ("APPLIED", "REJECTED", "CANCELLED")


# ═══════════ 冲突预检（只读，不落库；供三申请表单提交前 UX 反馈）═══════════

def conflict_check(body, user) -> dict:
    """只读预检：复用 `_detect_conflict`（不重复实现算法）。仍需归属校验——
    否则会变成一个可被任意教师用来探测他人课表安排信息的越权通道（CLAUDE.md §6.1）。"""
    from app.models import AaScheduleItem
    origin_id = getattr(body, "originItemId", None)
    if not origin_id:
        raise AppException("VALIDATION_ERROR", "originItemId 必填")
    tw, ts = getattr(body, "targetWeekday", None), getattr(body, "targetSlotNo", None)
    if tw is None or ts is None:
        raise AppException("VALIDATION_ERROR", "目标星期/节次必填")
    with session() as db:
        origin = db.get(AaScheduleItem, int(origin_id))
        if not origin or origin.is_deleted or origin.tenant_id != _tid():
            raise not_found("原课表项不存在")
        ctx = build_affairs_context(user, db)
        if not _can_manage_all(ctx):
            keys = _derive_keys(user)
            if not origin.teacher_key or origin.teacher_key not in keys:
                raise no_data_scope("仅可对本人任课课位做冲突预检")
        tsw = int(getattr(body, "targetStartWeek", None) or origin.start_week)
        tew = int(getattr(body, "targetEndWeek", None) or origin.end_week)
        tp = getattr(body, "targetWeekParity", None) or origin.week_parity or "ALL"
        tcr = getattr(body, "targetClassroom", None) or origin.classroom_text
        conflict = _detect_conflict(db, origin.batch_id, int(tw), int(ts), tsw, tew, tp,
                                    origin.teacher_key, origin.class_id, tcr, exclude_id=origin.id)
        return {"conflict": conflict}


# ═══════════ 发起（教师，提交即冲突预检）═══════════

def submit(body, user) -> dict:
    ct = (getattr(body, "changeType", "") or "").upper()
    if ct not in CHANGE_TYPES:
        raise AppException("VALIDATION_ERROR", "调停课类型非法（ADJUST/STOP/MAKEUP）")
    reason = (getattr(body, "reason", None) or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "调停课原因必填且不少于 5 字")
    with session() as db:
        from app.models import AaScheduleBatch, AaScheduleChange, AaScheduleItem
        ctx = build_affairs_context(user, db)
        origin = db.get(AaScheduleItem, int(body.originItemId)) if getattr(body, "originItemId", None) else None
        if not origin or origin.is_deleted or origin.tenant_id != _tid():
            raise not_found("原课表项不存在")
        if origin.status != "EFFECTIVE":
            raise AppException("DATA_CONFLICT", "原课表项已变更/失效，不可再发起调停课")
        b = db.get(AaScheduleBatch, int(origin.batch_id)) if origin.batch_id else None
        if not b or b.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布课表的课位可发起调停课")
        # 数据范围(COURSE)：非 TENANT_ALL 角色须为本人任课课位
        if not _can_manage_all(ctx):
            keys = _derive_keys(user)
            if not origin.teacher_key or origin.teacher_key not in keys:
                raise no_data_scope("仅可对本人任课课位发起调停课")
        # 停课需给出后续安排（真实业务：不填补课安排且课程仍有周学时缺口 → 422 警示）
        if ct == "STOP" and not (getattr(body, "makeupPlan", None) or "").strip():
            raise AppException("VALIDATION_ERROR", "停课须填写补课/后续安排说明")
        # 目标课位（调课/补课必填）
        tw = ts = tsw = tew = tp = tcr = None
        if ct in ("ADJUST", "MAKEUP"):
            if getattr(body, "targetWeekday", None) is None or getattr(body, "targetSlotNo", None) is None:
                raise AppException("VALIDATION_ERROR", "调课/补课须填写目标星期与节次")
            tw, ts = int(body.targetWeekday), int(body.targetSlotNo)
            tsw = int(getattr(body, "targetStartWeek", None) or origin.start_week)
            tew = int(getattr(body, "targetEndWeek", None) or origin.end_week)
            tp = (getattr(body, "targetWeekParity", None) or origin.week_parity or "ALL")
            tcr = getattr(body, "targetClassroom", None) or origin.classroom_text
            if tw < 1 or tw > 7:
                raise AppException("VALIDATION_ERROR", "目标星期非法")
            # 提交即三重冲突预检（同批次；排除原课位自身）
            conflict = _detect_conflict(db, origin.batch_id, tw, ts, tsw, tew, tp,
                                        origin.teacher_key, origin.class_id, tcr,
                                        exclude_id=origin.id)
            if conflict:
                raise AppException("DATA_CONFLICT",
                                   f"目标课位冲突（{conflict['type']}）：{conflict['detail']}，单据不予受理")
        uid_num = _op_uid()
        x = AaScheduleChange(
            tenant_id=_tid(), term_id=b.term_id, batch_id=origin.batch_id, origin_item_id=origin.id,
            task_id=origin.task_id, change_type=ct,
            course_name=origin.course_name, class_id=origin.class_id, class_name=origin.class_name,
            teacher_key=origin.teacher_key, teacher_name=origin.teacher_name,
            origin_weekday=origin.weekday, origin_slot_no=origin.slot_no,
            origin_start_week=origin.start_week, origin_end_week=origin.end_week,
            origin_week_parity=origin.week_parity, origin_classroom=origin.classroom_text,
            target_weekday=tw, target_slot_no=ts, target_start_week=tsw, target_end_week=tew,
            target_week_parity=tp, target_classroom=tcr,
            makeup_plan=(getattr(body, "makeupPlan", None) or None), reason=reason,
            applicant_id=uid_num,
            status="SUBMITTED", current_node="COLLEGE_REVIEW")
        db.add(x)
        db.flush()
        inst = _open_wf(db, x.id, uid_num or 0,
                        f"{origin.teacher_name or ''} {L_CT[ct]}：{origin.course_name or ''}", "COLLEGE_REVIEW")
        x.workflow_instance_id = inst.id
        _todo_upsert(db, x.id, "COLLEGE_REVIEW", f"{L_CT[ct]}待学院审：{origin.course_name or ''}")
        _audit(db, x.id, "SUBMIT", f"{ct} item={origin.id}")
        db.commit()
        db.refresh(x)
        return _row(x)


# ═══════════ 审批（学院审 → 教务处审；终审通过即改写课表）═══════════

def review(cid, user, action, comment="") -> dict:
    action = (action or "").upper()
    with session() as db:
        from app.models import WorkflowInstance, WorkflowTask
        x = _load(db, cid)
        if x.status not in _ACTIVE:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该调停课单当前状态不可审批")
        inst = db.get(WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
        task = db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == (inst.id if inst else 0),
            WorkflowTask.node_code == x.current_node, WorkflowTask.status == "PENDING",
            WorkflowTask.is_deleted.is_(False))).first() if inst else None

        if action == "REJECT":
            if not comment or len(comment.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
            if task:
                task.status, task.action_reason, task.acted_at = "REJECTED", comment.strip(), datetime.utcnow()
            x.status, x.version = "REJECTED", x.version + 1
            if inst:
                inst.status = "REJECTED"
            _todo_done(db, x.id)
            _msg(db, x.applicant_id or 0, f"{L_CT[x.change_type]}未通过", comment.strip(),
                 "WORKFLOW_RESULT", x.id)
            _audit(db, x.id, "REJECT", comment.strip())
            db.commit()
            from app.services.message_event_outbox_service import try_process_pending_outbox
            try_process_pending_outbox(worker_id="aa-sched-change-inline")
            db.refresh(x)
            return _row(x)

        if action != "APPROVE":
            raise AppException("VALIDATION_ERROR", "无效操作")
        if task:
            task.status, task.acted_at = "APPROVED", datetime.utcnow()
        i = NODES.index(x.current_node) if x.current_node in NODES else 0
        if i + 1 < len(NODES):
            nxt = NODES[i + 1]
            x.current_node, x.status, x.version = nxt, _NODE_STATUS[nxt], x.version + 1
            if inst:
                inst.current_node = nxt
            db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=nxt,
                                assignee_id=0, status="PENDING"))
            _todo_upsert(db, x.id, nxt, f"{L_CT[x.change_type]}待教务处审：{x.course_name or ''}")
            _audit(db, x.id, "STEP", f"->{nxt}")
            db.commit()
            db.refresh(x)
            return _row(x)
        # 终审通过 → APPROVED，随即系统改写课表 → APPLIED
        x.status, x.version = "APPROVED", x.version + 1
        if inst:
            inst.status = "APPROVED"
        _audit(db, x.id, "APPROVE", "终审通过")
        applied = _apply_schedule(db, x)
        _todo_done(db, x.id)
        db.commit()
        from app.services.message_event_outbox_service import try_process_pending_outbox
        try_process_pending_outbox(worker_id="aa-sched-change-inline")
        db.refresh(x)
        out = _row(x)
        out["applied"] = applied
        return out


def _apply_schedule(db, x) -> dict:
    """终审通过后改写课表：原课位标 CHANGED(保留历史)，调课/补课生成新项并回链本单，STATUS_CHANGED 通知师生。"""
    from app.models import AaScheduleItem, StudentProfile, User
    origin = db.get(AaScheduleItem, int(x.origin_item_id)) if x.origin_item_id else None
    # 复核目标冲突仍为 0（并发防护）
    new_item_id = None
    if x.change_type in ("ADJUST", "MAKEUP"):
        conflict = _detect_conflict(db, x.batch_id, x.target_weekday, x.target_slot_no,
                                    x.target_start_week, x.target_end_week, x.target_week_parity or "ALL",
                                    x.teacher_key, x.class_id, x.target_classroom,
                                    exclude_id=(origin.id if origin else None))
        if conflict:
            raise AppException("DATA_CONFLICT", f"复核目标课位冲突（{conflict['type']}）：{conflict['detail']}")
    # 原课位：调课/停课置 CHANGED（保留历史，禁直接 UPDATE 已发布项）；补课不动原课位
    if origin and x.change_type in ("ADJUST", "STOP"):
        origin.status = "CHANGED"
    # 调课/补课生成新课表项，回链本单
    if x.change_type in ("ADJUST", "MAKEUP") and origin:
        ni = AaScheduleItem(
            tenant_id=_tid(), batch_id=origin.batch_id, task_id=origin.task_id,
            course_id=origin.course_id, course_name=origin.course_name,
            class_id=origin.class_id, class_name=origin.class_name,
            teacher_key=origin.teacher_key, teacher_name=origin.teacher_name,
            weekday=x.target_weekday, slot_no=x.target_slot_no,
            start_week=x.target_start_week or origin.start_week,
            end_week=x.target_end_week or origin.end_week,
            week_parity=x.target_week_parity or "ALL",
            classroom_text=x.target_classroom, change_id=x.id, status="EFFECTIVE")
        db.add(ni)
        db.flush()
        new_item_id = ni.id
        x.new_item_id = ni.id
    x.status, x.applied_at = "APPLIED", datetime.utcnow()
    # STATUS_CHANGED 真实推送：受影响班级每个学生 + 任课教师（逐条 UnifiedMessage，非单条广播）。
    # receiver_id 必须是 t_user.id（移动端读消息按当前登录 user_id 过滤，mobile_student_service.
    # _resolve_uid 同款约定）——此前分别用 x.applicant_id（未剥离 'db-' 前缀恒为 0）和
    # t_student_profile.id（与 user_id 是两套完全独立的自增主键空间）当 receiver_id，
    # 两者都不在移动端过滤用的 user_id 空间内，师生实际永远收不到本通知，本轮修正为按
    # login_name 精确匹配 t_user 解析真实账号（教师：teacher_key；学生：student_no），
    # 对齐 internship_service.remind_weekly_report 的既有精确送达范式（D-11）。
    # 查不到登录账号的收件人（教师/学生尚未建立账号）当次静默跳过、不计入已通知数——
    # 不伪造成功，通知缺口也不回滚已生效的审批结果。
    title = f"{L_CT[x.change_type]}通知：{x.course_name or ''}"
    content = _notice_text(x)
    teacher_notified = 0
    if x.teacher_key:
        acc = db.scalars(select(User).where(
            User.tenant_id == _tid(), User.login_name == x.teacher_key,
            User.is_deleted.is_(False), User.status == "ACTIVE")).first()
        if acc:
            _msg(db, acc.id, title, content, "STATUS_CHANGED", x.id)
            teacher_notified = 1
    students = 0
    if x.class_id:
        rows = db.execute(select(User.id).select_from(StudentProfile).join(
            User, and_(User.tenant_id == StudentProfile.tenant_id,
                      User.login_name == StudentProfile.student_no,
                      User.is_deleted.is_(False))
        ).where(StudentProfile.tenant_id == _tid(), StudentProfile.class_id == int(x.class_id),
                StudentProfile.is_deleted.is_(False), User.status == "ACTIVE")).all()
        for (uid,) in rows:
            _msg(db, uid, title, content, "STATUS_CHANGED", x.id)
            students += 1
    _audit(db, x.id, "APPLIED", f"newItem={new_item_id},pushed={students}生+{teacher_notified}师")
    return {"status": "APPLIED", "newItemId": str(new_item_id or ""), "originKept": "CHANGED(历史留痕)",
            "notified": {"students": int(students), "teacher": teacher_notified, "channel": "STATUS_CHANGED"}}


def _notice_text(x) -> str:
    o = f"周{x.origin_weekday}第{x.origin_slot_no}节"
    if x.change_type == "STOP":
        return f"{x.course_name or ''}（{o}）停课。{('后续安排：' + x.makeup_plan) if x.makeup_plan else ''}"
    t = f"周{x.target_weekday}第{x.target_slot_no}节 {x.target_classroom or ''}"
    verb = "调至" if x.change_type == "ADJUST" else "补课于"
    return f"{x.course_name or ''}（{o}）{verb} {t}，请留意课表变更。"


# ═══════════ 撤销（教师，终审前）═══════════

def cancel(cid, user, reason="") -> dict:
    with session() as db:
        from app.models import WorkflowInstance, WorkflowTask
        x = _load(db, cid)
        if x.status in ("APPROVED", "APPLIED"):
            raise AppException("DATA_CONFLICT", "已终审通过/已生效，不可撤销")
        if x.status not in _CANCELLABLE:
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前状态不可撤销")
        ctx = build_affairs_context(user, db)
        if not _can_manage_all(ctx):
            keys = _derive_keys(user)
            if not x.teacher_key or x.teacher_key not in keys:
                raise no_data_scope("仅可撤销本人发起的调停课单")
        x.status, x.version = "CANCELLED", x.version + 1
        if x.workflow_instance_id:
            inst = db.get(WorkflowInstance, int(x.workflow_instance_id))
            if inst:
                inst.status = "CANCELLED"
            for t in db.scalars(select(WorkflowTask).where(
                    WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == int(x.workflow_instance_id),
                    WorkflowTask.status == "PENDING", WorkflowTask.is_deleted.is_(False))).all():
                t.status, t.acted_at = "CANCELLED", datetime.utcnow()
        _todo_done(db, x.id)
        _audit(db, x.id, "CANCEL", (reason or "").strip())
        db.commit()
        db.refresh(x)
        return _row(x)


# ═══════════ 查询（范围过滤）═══════════

def get_change(cid, user) -> dict:
    """详情查询。修复：此前只按 id+租户加载，未做归属校验——任何持 view 权限者传任意 cid
    即可查看他人调停课单详情（含目标课位、事由等），与 list_changes/cancel 的范围收敛口径
    不一致。此处补齐同一套范围判断（TENANT_ALL 全放行；COLLEGE 按所辖班级；其余教师仅本人）。"""
    with session() as db:
        x = _load(db, cid)
        ctx = build_affairs_context(user, db)
        if not _can_manage_all(ctx):
            if ctx.scope_type == "COLLEGE":
                allowed = ctx.allowed_class_ids(db)
                if not x.class_id or int(x.class_id) not in (allowed or set()):
                    raise no_data_scope("该调停课单不在您的数据范围内")
            else:
                keys = _derive_keys(user)
                if not x.teacher_key or x.teacher_key not in keys:
                    raise no_data_scope("仅可查看本人发起的调停课单")
        return _row(x)


def list_changes(user, change_type=None, status=None, teacher_key=None, term_id=None,
                 date_from=None, date_to=None, page=1, page_size=20):
    """台账/我的申请列表。`status` 支持逗号分隔多值（IN 查询），供"调停课归档"卡复用同一函数
    (见施工卡 09 §7 注)，不新增第二套 SQL。"""
    from app.models import AaScheduleChange
    with session() as db:
        ctx = build_affairs_context(user, db)
        conds = [AaScheduleChange.tenant_id == _tid(), AaScheduleChange.is_deleted.is_(False)]
        if change_type:
            conds.append(AaScheduleChange.change_type == change_type.upper())
        if status:
            vals = [s.strip().upper() for s in status.split(",") if s.strip()]
            if len(vals) == 1:
                conds.append(AaScheduleChange.status == vals[0])
            elif vals:
                conds.append(AaScheduleChange.status.in_(vals))
        if term_id:
            conds.append(AaScheduleChange.term_id == int(term_id))
        if date_from:
            conds.append(AaScheduleChange.created_at >= date_from)
        if date_to:
            conds.append(AaScheduleChange.created_at <= date_to + " 23:59:59")
        # 范围收敛：TENANT_ALL 全量；COLLEGE 按所辖班级；其余(教师) 仅本人课位
        if not _can_manage_all(ctx):
            if ctx.scope_type == "COLLEGE":
                allowed = ctx.allowed_class_ids(db)
                if not allowed:
                    return [], 0
                conds.append(AaScheduleChange.class_id.in_(list(allowed)))
            else:
                keys = _derive_keys(user)
                if not keys:
                    return [], 0
                conds.append(AaScheduleChange.teacher_key.in_(list(keys)))
        elif teacher_key:
            conds.append(AaScheduleChange.teacher_key == teacher_key)
        total = db.scalar(select(func.count()).select_from(AaScheduleChange).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(AaScheduleChange).where(*conds)
                          .order_by(AaScheduleChange.id.desc()).offset(offset).limit(page_size)).all()
        return [_row(x) for x in rows], total


# ═══════════ 归档（台账的终态特化视图；服务层强制排除在途态，不依赖前端默认参数）═══════════

def archive_list(user, change_type=None, status=None, term_id=None,
                 date_from=None, date_to=None, page=1, page_size=20):
    """归档检索：`list_changes()` 的终态特化视图（APPLIED/REJECTED/CANCELLED），
    与"调停课台账"共用同一查询函数，仅调用参数不同（施工卡 09 §6/§7 已明确此关系，不构成重复实现）。"""
    if status:
        vals = [s.strip().upper() for s in status.split(",") if s.strip().upper() in _TERMINAL_STATES]
        status = ",".join(vals) if vals else ",".join(_TERMINAL_STATES)
    else:
        status = ",".join(_TERMINAL_STATES)
    return list_changes(user, change_type=change_type, status=status, term_id=term_id,
                        date_from=date_from, date_to=date_to, page=page, page_size=page_size)


_EMPTY_STATS = {"total": 0, "byType": {}, "byStatus": {}, "byCollege": [], "topTeachers": []}


def stats(user, term_id=None, dimension=None):
    """调停课统计：按类型/状态/学院/教师聚合（读侧，范围收敛）。`dimension` 目前不改变查询范围，
    仅供前端 Tab 切换展示同一份聚合结果的不同维度（避免切 Tab 反复请求）。

    `byCollege` 通过 class_id → t_class.major_id → t_major.college_id 运行时联查解析
    （表未冗余 college_id 列，V1 数据量级下联查可接受，见二级总包 §8 澄清）。
    `topTeachers` 按当前查询范围（已做 COLLEGE/教师范围收敛）内的教师排名，天然满足
    "COLLEGE_ADMIN 仅见本学院内部排名，ACADEMIC_TEACHER 见全校"的隐私设计（08 卡 §10）。
    """
    from app.models import AaScheduleChange, College, Major, SchoolClass
    with session() as db:
        ctx = build_affairs_context(user, db)
        conds = [AaScheduleChange.tenant_id == _tid(), AaScheduleChange.is_deleted.is_(False)]
        if term_id:
            conds.append(AaScheduleChange.term_id == int(term_id))
        if not _can_manage_all(ctx):
            if ctx.scope_type == "COLLEGE":
                allowed = ctx.allowed_class_ids(db)
                if not allowed:
                    return dict(_EMPTY_STATS)
                conds.append(AaScheduleChange.class_id.in_(list(allowed)))
            else:
                keys = _derive_keys(user)
                if not keys:
                    return dict(_EMPTY_STATS)
                conds.append(AaScheduleChange.teacher_key.in_(list(keys)))
        rows = db.scalars(select(AaScheduleChange).where(*conds)).all()
        by_type, by_status, by_teacher = {}, {}, {}
        class_ids = set()
        for r in rows:
            by_type[r.change_type] = by_type.get(r.change_type, 0) + 1
            by_status[r.status] = by_status.get(r.status, 0) + 1
            if r.teacher_key:
                t = by_teacher.setdefault(r.teacher_key, {"teacherKey": r.teacher_key,
                                          "teacherName": r.teacher_name or r.teacher_key, "count": 0})
                t["count"] += 1
            if r.class_id:
                class_ids.add(int(r.class_id))
        # class_id → college_id（两跳联查，无冗余列）
        class_college: dict[int, int | None] = {}
        college_names: dict[int, str] = {}
        if class_ids:
            cls_rows = db.execute(select(SchoolClass.id, SchoolClass.major_id).where(
                SchoolClass.tenant_id == _tid(), SchoolClass.id.in_(list(class_ids)))).all()
            major_ids = {mid for _, mid in cls_rows if mid}
            major_college: dict[int, int] = {}
            if major_ids:
                maj_rows = db.execute(select(Major.id, Major.college_id).where(
                    Major.tenant_id == _tid(), Major.id.in_(list(major_ids)))).all()
                major_college = dict(maj_rows)
            class_college = {cid: major_college.get(mjid) for cid, mjid in cls_rows}
            college_ids = {cid for cid in class_college.values() if cid}
            if college_ids:
                col_rows = db.execute(select(College.id, College.college_name).where(
                    College.tenant_id == _tid(), College.id.in_(list(college_ids)))).all()
                college_names = dict(col_rows)
        by_college: dict[int, dict] = {}
        for r in rows:
            cid = class_college.get(int(r.class_id)) if r.class_id else None
            key = cid or 0
            c = by_college.setdefault(key, {"collegeId": str(cid or ""),
                                            "collegeName": college_names.get(cid, "未归属学院") if cid else "未归属学院",
                                            "count": 0})
            c["count"] += 1
        return {
            "total": len(rows), "byType": by_type, "byStatus": by_status,
            "byCollege": sorted(by_college.values(), key=lambda x: -x["count"]),
            "topTeachers": sorted(by_teacher.values(), key=lambda x: -x["count"])[:10],
        }
