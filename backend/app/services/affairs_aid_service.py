"""13A-P3 困难认定闭环（范式五件套 + 强敏感家庭经济管线）。

12 态：DRAFT/SUBMITTED/CLASS_REVIEW/COUNSELOR_REVIEW/COLLEGE_REVIEW/SCHOOL_REVIEW/
PUBLICITY/APPROVED/REJECTED/ADJUST_REVIEW/ARCHIVED（NOT_STARTED 为批次前置态）。
管理端 apply 直接受理到 CLASS_REVIEW 并建 workflow；SCHOOL_REVIEW 通过→PUBLICITY；
公示期满→APPROVED，写 level_history 进困难库 + StageEvent 进 360。
家庭经济：列表/详情默认脱敏，income_encrypted 永不出列表；查看完整走 reveal（sensitiveView 鉴权 + SENSITIVE_VIEW 审计）。
"""

from app.core.optimistic_lock import atomic_claim_version

import json
from datetime import datetime, timedelta

from sqlalchemy import and_, func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, no_permission, not_found
from app.core.field_crypto import decrypt_field, encrypt_field
from app.core.pagination import normalize_page
from app.services.db_service import _iso, _tid, audit_insert, session

LEVELS = {"SPECIAL": "特别困难", "DIFFICULT": "困难", "GENERAL": "一般困难"}
_LEVEL_RANK = {"GENERAL": 1, "DIFFICULT": 2, "SPECIAL": 3}


def _students_by_ids(db, rows, attr="student_id"):
    """批量取回 rows 涉及的学生档案 {id: StudentProfile}，替代列表循环内逐行 db.get（消 N+1）。"""
    from app.models import StudentProfile
    sids = {int(getattr(x, attr)) for x in rows if getattr(x, attr, None)}
    if not sids:
        return {}
    return {s.id: s for s in db.scalars(select(StudentProfile).where(StudentProfile.id.in_(sids))).all()}

AID_NODES = ["CLASS_REVIEW", "COUNSELOR_REVIEW", "COLLEGE_REVIEW", "SCHOOL_REVIEW"]
_TERMINAL = {"APPROVED", "REJECTED", "ARCHIVED"}
_SENSITIVE_ROLES = {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN", "FUNDING_TEACHER"}

L_AID = {
    "DRAFT": "草稿", "SUBMITTED": "已提交", "CLASS_REVIEW": "班级评议", "COUNSELOR_REVIEW": "辅导员初审",
    "COLLEGE_REVIEW": "学院复审", "SCHOOL_REVIEW": "学校终审", "PUBLICITY": "公示中",
    "APPROVED": "已通过", "REJECTED": "已驳回", "ADJUST_REVIEW": "动态调整审批", "ARCHIVED": "已归档",
}

_L_OBJ = {"SUBMITTED": "待复核", "CLOSED": "已复核"}
_L_OBJ_RESULT = {"SUSTAINED": "异议成立(驳回)", "OVERRULED": "异议不成立(维持)"}


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


def _audit(db, biz_id, action, detail="", before="", after=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AID", biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             before_val=before, after_val=after, occurred_at=datetime.utcnow()))


def _assignee_for(db, node, student_id):
    from app.services.affairs_assignee_service import require_assignee_id
    return require_assignee_id(db, node, student_id=student_id)


def _open_wf(db, apply_id, applicant_id, title, first_node, assignee_id):
    from app.models import WorkflowInstance, WorkflowTask
    from app.services.runtime_preset_install_service import ensure_workflow_enabled
    ensure_workflow_enabled(db, _tid(), "AFFAIRS_AID_IDENTIFY")
    if int(assignee_id or 0) <= 0:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", f"未配置受理人：{first_node}")
    inst = WorkflowInstance(tenant_id=_tid(), workflow_code="AFFAIRS_AID_IDENTIFY",
                            source_module="student-affairs", source_biz_type="AID",
                            source_biz_id=int(apply_id), applicant_id=int(applicant_id or 0),
                            title=title, status="RUNNING", current_node=first_node)
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


def _todo_upsert(db, apply_id, assignee_id, student_id, title, todo_type="AID_APPROVAL"):
    from app.models import UnifiedTodo
    if int(assignee_id or 0) <= 0:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", "困难认定待办没有具体受理人")
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_id == int(apply_id), UnifiedTodo.todo_type == todo_type,
        UnifiedTodo.assignee_id == int(assignee_id or 0),
        UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title, row.status, row.version = title, "PENDING", row.version + 1
    else:
        db.add(UnifiedTodo(tenant_id=_tid(), source_module="student-affairs", source_biz_type="AID",
                           source_biz_id=int(apply_id), todo_type=todo_type,
                           assignee_id=int(assignee_id or 0), student_id=student_id, title=title,
                           status="PENDING"))


def _todo_done(db, apply_id, todo_type="AID_APPROVAL"):
    from app.models import UnifiedTodo
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.source_biz_id == int(apply_id), UnifiedTodo.todo_type == todo_type,
            UnifiedTodo.is_deleted.is_(False))).all():
        r.status, r.version = "DONE", r.version + 1


def _msg(db, receiver_id, title, content, mtype, apply_id):
    from app.services.message_event_outbox_service import emit_receiver_notice
    emit_receiver_notice(
        db,
        event_code="AID.NOTICE",
        source_module="student-affairs",
        source_biz_type="aid",
        source_biz_id=int(apply_id),
        receiver_id=receiver_id,
        title=title,
        content=content,
        receiver_as="student",
        dedup_extra=mtype,
    )


def _drain_message_outbox():
    from app.services.message_event_outbox_service import try_process_pending_outbox
    try_process_pending_outbox(worker_id="aid-inline")


def _scope_or_403(db, student_id, user):
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is None:
        return
    s = db.get(StudentProfile, int(student_id)) if student_id else None
    if not s or s.class_id not in allowed:
        raise AppException("NO_DATA_SCOPE", "该申请不在您的数据范围内")


def _can_sensitive_view(user, x=None) -> bool:
    role = (user or {}).get("currentRoleCode")
    if role in _SENSITIVE_ROLES:
        return True
    if role == "COUNSELOR" and x is not None and getattr(x, "status", None) in (
            "CLASS_REVIEW", "COUNSELOR_REVIEW"):
        return True
    return False


def _check_node_authority(user, x) -> None:
    from app.core.permissions import has_permission
    if has_permission(user, "studentAffairs.aid.approve"):
        return
    if x.status in ("CLASS_REVIEW", "COUNSELOR_REVIEW") and has_permission(
            user, "studentAffairs.aid.counselorReview"):
        return
    raise no_permission(f"无权审批当前节点（{L_AID.get(x.status, x.status)}）")


def _uid_int(user) -> int:
    raw = str((user or {}).get("userId") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _check_aid_assignee(db, x, user, *, todo_type: str = "AID_APPROVAL"):
    from app.core.affairs_security import build_affairs_context
    ctx = build_affairs_context(user, db)
    if ctx.scope_type == "TENANT_ALL" or not x.workflow_instance_id:
        return
    from app.models import WorkflowTask
    task = db.scalars(select(WorkflowTask).where(
        WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == int(x.workflow_instance_id),
        WorkflowTask.node_code == x.status, WorkflowTask.status == "PENDING",
        WorkflowTask.is_deleted.is_(False)).order_by(WorkflowTask.id.desc())).first()
    if task and task.assignee_id:
        uid = _uid_int(user)
        if uid and int(task.assignee_id) != uid:
            raise AppException("NO_PERMISSION", "当前审批任务未指派给您")
        return
    from app.models import UnifiedTodo
    todo = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_id == int(x.id), UnifiedTodo.todo_type == todo_type,
        UnifiedTodo.status == "PENDING", UnifiedTodo.is_deleted.is_(False)
    ).order_by(UnifiedTodo.id.desc())).first()
    if not todo or not todo.assignee_id:
        return
    uid = _uid_int(user)
    if uid and int(todo.assignee_id) != uid:
        raise AppException("NO_PERMISSION", "当前待办未指派给您")


def _income_range(v) -> str:
    try:
        n = float(v or 0)
    except (TypeError, ValueError):
        return "未填写"
    if n <= 0:
        return "未填写"
    if n < 10000:
        return "1万以下"
    if n < 20000:
        return "1-2万"
    if n < 40000:
        return "2-4万"
    return "4万以上"


def _mask_family(fe) -> dict:
    if not fe:
        return {}
    tags = json.loads(fe.special_flags_json) if fe.special_flags_json else []
    return {
        "annualIncomeRange": _income_range(decrypt_field(fe.income_encrypted)),
        "memberCount": fe.member_count or 0,
        "specialTags": tags,
        "detailMasked": True,
    }


def _reveal_family(fe) -> dict:
    if not fe:
        return {}
    tags = json.loads(fe.special_flags_json) if fe.special_flags_json else []
    members = json.loads(fe.family_members_json) if fe.family_members_json else []
    return {
        "annualIncome": decrypt_field(fe.income_encrypted), "debt": decrypt_field(fe.debt_encrypted),
        "memberCount": fe.member_count or 0, "familyMembers": members,
        "specialTags": tags, "detailMasked": False,
    }


def _batch_row(b) -> dict:
    return {
        "batchId": str(b.id), "batchName": b.batch_name, "schoolYear": b.year_code,
        "applyStart": _iso(b.apply_start), "applyEnd": _iso(b.apply_end),
        "publicityDays": b.publicity_days if b.publicity_days is not None else 5,
        "status": b.status,
    }


def _apply_row(x, s=None, fe=None, *, has_pending_objection: bool = False) -> dict:
    return {
        "applyId": str(x.id), "batchId": str(x.batch_id), "studentId": str(x.student_id),
        "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
        "applyLevel": x.apply_level, "suggestLevel": x.suggest_level, "finalLevel": x.final_level,
        "status": x.status, "statusLabel": L_AID.get(x.status, x.status),
        "currentNode": x.status if x.status in AID_NODES else "",
        "familyEconomy": _mask_family(fe),
        "returnReason": getattr(x, "return_reason", None) or "",
        "hasPendingObjection": bool(has_pending_objection),
        "version": x.version,
    }


def _pending_objection_ids(db, apply_ids) -> set[int]:
    from app.models import AidObjection
    ids = {int(i) for i in apply_ids if i}
    if not ids:
        return set()
    return set(db.scalars(select(AidObjection.apply_id).where(
        AidObjection.tenant_id == _tid(), AidObjection.apply_id.in_(ids),
        AidObjection.status == "SUBMITTED", AidObjection.is_deleted.is_(False))).all())


def _assert_no_open_objection(db, apply_id):
    from app.models import AidObjection
    if db.scalars(select(AidObjection.id).where(
            AidObjection.tenant_id == _tid(), AidObjection.apply_id == int(apply_id),
            AidObjection.status == "SUBMITTED", AidObjection.is_deleted.is_(False)).limit(1)).first():
        raise AppException("DATA_CONFLICT", "该申请有进行中的公示异议，须复核完成后方可确认通过")


def create_batch(body, user) -> dict:
    from app.services.affairs_publicity_rules import publicity_days, school_year, validate_dates
    body.batchName = str(getattr(body, "batchName", None) or "").strip()
    if not 2 <= len(body.batchName) <= 200:
        raise AppException("VALIDATION_ERROR", "认定批次名称需2-200字")
    body.schoolYear = school_year(getattr(body, "schoolYear", None))
    body.publicityDays = publicity_days(getattr(body, "publicityDays", None))
    validate_dates(_parse_dt, body)
    with session() as db:
        from app.models import AidBatch
        publish = bool(getattr(body, "publish", False))
        b = AidBatch(tenant_id=_tid(), batch_name=body.batchName, year_code=body.schoolYear,
                     apply_start=_parse_dt(body.applyStart), apply_end=_parse_dt(body.applyEnd),
                     publicity_days=(body.publicityDays if body.publicityDays is not None else 5),
                     level_config_json=json.dumps(body.levelConfig or {}, ensure_ascii=False),
                     status=("OPEN" if publish else "DRAFT"))
        db.add(b)
        db.flush()
        _audit(db, b.id, "BATCH_CREATE", f"publish={publish}")
        db.commit()
        _drain_message_outbox()
        db.refresh(b)
        return _batch_row(b)


def list_batches(user, school_year=None, status=None, page=1, page_size=20):
    with session() as db:
        from app.models import AidBatch
        conds = [AidBatch.tenant_id == _tid(), AidBatch.is_deleted.is_(False)]
        if school_year:
            conds.append(AidBatch.year_code == school_year)
        if status:
            conds.append(AidBatch.status == status)
        page, page_size = normalize_page(page, page_size)
        total = int(db.scalar(select(func.count()).select_from(AidBatch).where(*conds)) or 0)
        rows = db.scalars(select(AidBatch).where(*conds).order_by(AidBatch.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        return [_batch_row(b) for b in rows], total


def _req_int(v, field):
    raw = str(v or "").strip()
    if not raw.isdigit():
        raise AppException("VALIDATION_ERROR", f"请选择有效{field}")
    return int(raw)


def apply(body, user, *, skip_scope_check: bool = False) -> dict:
    student_id = _req_int(getattr(body, "studentId", None), "学生")
    if (body.applyLevel or "") not in LEVELS:
        raise AppException("VALIDATION_ERROR", "申请等级非法")
    st = (body.statement or "").strip()
    if not (10 <= len(st) <= 500):
        raise AppException("VALIDATION_ERROR", "困难情况说明需 10-500 字")
    with session() as db:
        from app.models import AidApply, AidBatch, AidFamilyEconomy, StudentProfile
        s = db.get(StudentProfile, student_id)
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在或不在数据范围内")
        if not skip_scope_check:
            _scope_or_403(db, student_id, user)
        b = db.get(AidBatch, _req_int(getattr(body, "batchId", None), "批次"))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("认定批次不存在")
        if b.status != "OPEN":
            raise AppException("DATA_CONFLICT", "批次未开放或已截止")
        dup = db.scalars(select(AidApply).where(
            AidApply.tenant_id == _tid(), AidApply.batch_id == b.id,
            AidApply.student_id == student_id, AidApply.is_deleted.is_(False))).first()
        if dup and dup.status not in _TERMINAL:
            raise AppException("DATA_CONFLICT", "该生在本批次已有在途申请，不可重复提交")
        first = AID_NODES[0]
        x = AidApply(tenant_id=_tid(), batch_id=b.id, student_id=student_id,
                     apply_level=body.applyLevel, statement=st, status=first)
        db.add(x)
        db.flush()
        fe = AidFamilyEconomy(
            tenant_id=_tid(), apply_id=x.id, student_id=student_id,
            member_count=getattr(body, "memberCount", None),
            income_encrypted=encrypt_field(getattr(body, "annualIncome", None)),
            debt_encrypted=encrypt_field(getattr(body, "debt", None)),
            family_members_json=json.dumps(getattr(body, "familyMembers", []) or [], ensure_ascii=False),
            special_flags_json=json.dumps(getattr(body, "specialTags", []) or [], ensure_ascii=False))
        db.add(fe)
        assignee = _assignee_for(db, first, student_id)
        inst = _open_wf(db, x.id, student_id, f"{s.real_name} 困难认定", first, assignee)
        x.workflow_instance_id = inst.id
        _todo_upsert(db, x.id, assignee, student_id, f"困难认定待评议：{s.real_name}")
        _audit(db, x.id, "APPLY", f"level={body.applyLevel}")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        db.refresh(fe)
        return _apply_row(x, s, fe)


def _load(db, apply_id):
    from app.models import AidApply, StudentProfile
    x = db.get(AidApply, int(apply_id))
    if not x or x.is_deleted or x.tenant_id != _tid():
        raise not_found("认定申请不存在")
    s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
    return x, s


def _family_of(db, apply_id):
    from app.models import AidFamilyEconomy
    return db.scalars(select(AidFamilyEconomy).where(
        AidFamilyEconomy.tenant_id == _tid(), AidFamilyEconomy.apply_id == int(apply_id),
        AidFamilyEconomy.is_deleted.is_(False))).first()


def _act_task(db, x, action, reason=""):
    from app.models import WorkflowInstance
    inst = db.get(WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
    task = _cur_task(db, inst.id, x.status) if inst else None
    if task:
        task.status, task.acted_at, task.action_reason = action, datetime.utcnow(), reason
        task.version += 1
    return inst


def review(apply_id, user, action, level=None, reason="", expected_version=None) -> dict:
    action = (action or "").upper()
    with session() as db:
        from app.models import WorkflowTask
        x, s = _load(db, apply_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in AID_NODES:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请当前状态不可评审，请刷新")
        atomic_claim_version(db, x, expected_version)
        _check_node_authority(user, x)
        _check_aid_assignee(db, x, user)
        if action == "APPROVE":
            inst = _act_task(db, x, "APPROVED", reason or "")
            if x.status == "COUNSELOR_REVIEW" and level in LEVELS:
                x.suggest_level = level
            i = AID_NODES.index(x.status)
            if i + 1 < len(AID_NODES):
                nxt = AID_NODES[i + 1]
                x.status, x.version = nxt, x.version + 1
                if inst:
                    inst.current_node = nxt
                assignee = _assignee_for(db, nxt, x.student_id)
                db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=nxt,
                                    assignee_id=assignee, status="PENDING"))
                _todo_upsert(db, x.id, assignee, x.student_id,
                             f"困难认定待审（{L_AID[nxt]}）：{s.real_name if s else ''}")
                _audit(db, x.id, "REVIEW_STEP", f"{AID_NODES[i]}->{nxt}")
            else:
                x.final_level = (level if level in LEVELS else (x.suggest_level or x.apply_level))
                x.status, x.publicity_at, x.version = "PUBLICITY", datetime.utcnow(), x.version + 1
                if inst:
                    inst.current_node = "PUBLICITY"
                _todo_done(db, x.id)
                _msg(db, x.student_id, "困难认定进入公示",
                     f"你的困难认定（拟定{LEVELS.get(x.final_level, '')}）进入公示", "PUBLISHED_NOTICE", x.id)
                _audit(db, x.id, "TO_PUBLICITY", f"final={x.final_level}")
        elif action == "REJECT":
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
            inst = _act_task(db, x, "REJECTED", reason.strip())
            x.status, x.return_reason, x.result_at, x.version = "REJECTED", reason.strip(), datetime.utcnow(), x.version + 1
            if inst:
                inst.status = "REJECTED"
            _todo_done(db, x.id)
            _msg(db, x.student_id, "困难认定未通过", reason.strip(), "WORKFLOW_RESULT", x.id)
            _audit(db, x.id, "REJECTED", reason.strip())
        elif action == "RETURN":
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
            _act_task(db, x, "TRANSFERRED", reason.strip())
            x.status, x.return_reason, x.version = "DRAFT", reason.strip(), x.version + 1
            _todo_done(db, x.id)
            _msg(db, x.student_id, "困难认定被退回", reason.strip(), "RETURNED_NOTICE", x.id)
            _audit(db, x.id, "RETURNED", reason.strip())
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _apply_row(x, s, _family_of(db, x.id))


def resubmit(apply_id, user, expected_version=None) -> dict:
    with session() as db:
        from app.models import WorkflowInstance, WorkflowTask
        x, s = _load(db, apply_id)
        _scope_or_403(db, x.student_id, user)
        if x.status != "DRAFT":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅被退回的申请可重新提交")
        atomic_claim_version(db, x, expected_version)
        first = AID_NODES[0]
        x.status, x.return_reason, x.version = first, None, x.version + 1
        inst = db.get(WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
        if inst:
            inst.status, inst.current_node = "RUNNING", first
        assignee = _assignee_for(db, first, x.student_id)
        db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id if inst else 0, node_code=first,
                            assignee_id=assignee, status="PENDING"))
        _todo_upsert(db, x.id, assignee, x.student_id, f"困难认定重新提交待评议：{s.real_name if s else ''}")
        _audit(db, x.id, "RESUBMIT")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _apply_row(x, s, _family_of(db, x.id))


def _confirm_one(db, x):
    from app.models import AidLevelHistory, StudentStageEvent, WorkflowInstance
    x.status, x.result_at, x.version = "APPROVED", datetime.utcnow(), x.version + 1
    if x.workflow_instance_id:
        inst = db.get(WorkflowInstance, int(x.workflow_instance_id))
        if inst:
            inst.status = "APPROVED"
    db.add(AidLevelHistory(tenant_id=_tid(), student_id=int(x.student_id), from_level=None,
                           to_level=x.final_level, change_type="IDENTIFY", apply_id=x.id,
                           batch_id=x.batch_id, effective_at=datetime.utcnow()))
    from app.models import StudentStageEvent
    db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(x.student_id), from_stage=None,
                             to_stage="AID_APPROVED", reason=f"困难认定通过（{LEVELS.get(x.final_level, '')}）",
                             source_module="student-affairs"))
    _todo_done(db, x.id)
    _msg(db, x.student_id, "困难认定通过", f"你的困难认定已通过（{LEVELS.get(x.final_level, '')}）", "WORKFLOW_RESULT", x.id)
    _audit(db, x.id, "APPROVED", f"final={x.final_level}")


def scan_publicity() -> dict:
    from app.models import AidApply, AidBatch
    now = datetime.utcnow()
    with session() as db:
        rows = db.scalars(select(AidApply).where(
            AidApply.tenant_id == _tid(), AidApply.status == "PUBLICITY",
            AidApply.publicity_at.is_not(None), AidApply.is_deleted.is_(False),
        ).order_by(AidApply.id).limit(200).with_for_update(skip_locked=True)).all()
        pending = _pending_objection_ids(db, [row.id for row in rows])
        batch_ids = {int(row.batch_id) for row in rows if row.batch_id}
        batches = {
            int(batch.id): batch
            for batch in db.scalars(select(AidBatch).where(
                AidBatch.tenant_id == _tid(),
                AidBatch.id.in_(batch_ids) if batch_ids else AidBatch.id == -1,
                AidBatch.is_deleted.is_(False),
            )).all()
        }
        confirmed = skipped = invalid = 0
        for row in rows:
            if int(row.id) in pending:
                skipped += 1
                continue
            batch = batches.get(int(row.batch_id)) if row.batch_id else None
            if not batch:
                invalid += 1
                continue
            due = row.publicity_at + timedelta(days=max(1, int(batch.publicity_days or 5)))
            if due > now:
                continue
            _confirm_one(db, row)
            confirmed += 1
        db.commit()
    _drain_message_outbox()
    return {"count": confirmed, "skippedObjection": skipped, "invalidBatch": invalid}


def confirm_publicity(apply_id, user, expected_version=None) -> dict:
    with session() as db:
        x, s = _load(db, apply_id)
        _scope_or_403(db, x.student_id, user)
        if x.status != "PUBLICITY":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请不在公示状态")
        atomic_claim_version(db, x, expected_version)
        _assert_no_open_objection(db, x.id)
        from app.models import AidBatch
        batch = db.get(AidBatch, int(x.batch_id))
        days = batch.publicity_days if batch and batch.publicity_days is not None else 5
        if not x.publicity_at or x.publicity_at + timedelta(days=max(1, days)) > datetime.utcnow():
            raise AppException("DATA_CONFLICT", "公示期尚未结束，不能提前确认")
        _confirm_one(db, x)
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _apply_row(x, s, _family_of(db, x.id), has_pending_objection=False)


def adjust(apply_id, user, target_level, reason="", expected_version=None) -> dict:
    if target_level not in LEVELS:
        raise AppException("VALIDATION_ERROR", "目标等级非法")
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "调整原因必填且不少于 5 字")
    with session() as db:
        x, s = _load(db, apply_id)
        _scope_or_403(db, x.student_id, user)
        if x.status != "APPROVED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已通过的认定可发起动态调整")
        atomic_claim_version(db, x, expected_version)
        x.status, x.suggest_level, x.version = "ADJUST_REVIEW", target_level, x.version + 1
        assignee = _assignee_for(db, "COUNSELOR_REVIEW", x.student_id)
        _todo_upsert(db, x.id, assignee, x.student_id, f"困难等级调整待审：{s.real_name if s else ''}",
                     todo_type="AID_ADJUST")
        _audit(db, x.id, "ADJUST_SUBMIT", f"{x.final_level}->{target_level}: {reason.strip()}")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _apply_row(x, s, _family_of(db, x.id))


def approve_adjust(apply_id, user, action="APPROVE", expected_version=None) -> dict:
    from app.core.permissions import has_permission
    if not has_permission(user, "studentAffairs.aid.approve"):
        raise no_permission("无权审批困难等级动态调整")
    with session() as db:
        from app.models import AidLevelHistory
        x, s = _load(db, apply_id)
        _scope_or_403(db, x.student_id, user)
        if x.status != "ADJUST_REVIEW":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请不在调整审批状态")
        atomic_claim_version(db, x, expected_version)
        _check_aid_assignee(db, x, user, todo_type="AID_ADJUST")
        if (action or "").upper() == "APPROVE":
            old = x.final_level
            db.add(AidLevelHistory(tenant_id=_tid(), student_id=int(x.student_id), from_level=old,
                                   to_level=x.suggest_level, change_type="ADJUST", apply_id=x.id,
                                   batch_id=x.batch_id, effective_at=datetime.utcnow()))
            x.final_level = x.suggest_level
            _audit(db, x.id, "ADJUST_APPROVED", f"{old}->{x.final_level}")
        else:
            _audit(db, x.id, "ADJUST_REJECTED")
        x.status, x.version = "APPROVED", x.version + 1
        _todo_done(db, x.id, todo_type="AID_ADJUST")
        _msg(db, x.student_id, "困难等级调整结果", f"当前等级：{LEVELS.get(x.final_level, '')}", "WORKFLOW_RESULT", x.id)
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _apply_row(x, s, _family_of(db, x.id))


def list_applications(user, status=None, batch_id=None, level=None, page=1, page_size=20,
                      student_id=None):
    from app.models import AidApply, AidFamilyEconomy, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.services.affairs_list_stats import status_counts_by_column
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        base_conds = [AidApply.tenant_id == _tid(), AidApply.is_deleted.is_(False)]
        if batch_id:
            base_conds.append(AidApply.batch_id == int(batch_id))
        if level:
            base_conds.append(AidApply.final_level == level)
        if student_id:
            try:
                base_conds.append(AidApply.student_id == int(student_id))
            except (TypeError, ValueError):
                return [], 0, {"ALL": 0}
        conds = list(base_conds)
        if status:
            statuses = [item.strip() for item in status.split(",") if item.strip()]
            conds.append(AidApply.status.in_(statuses))
        student_conds = [
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ]
        status_counts = status_counts_by_column(
            db, AidApply, AidApply.status, [*base_conds, *student_conds],
            join_student=StudentProfile, allowed_class_ids=allowed,
        )
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        page, page_size = normalize_page(page, page_size)
        total = int(db.scalar(select(func.count()).select_from(AidApply)
                              .join(StudentProfile, StudentProfile.id == AidApply.student_id)
                              .where(*conds, *student_conds)) or 0)
        rows = db.scalars(select(AidApply).join(StudentProfile, StudentProfile.id == AidApply.student_id)
                          .where(*conds, *student_conds).order_by(AidApply.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        students = _students_by_ids(db, rows)
        pending = _pending_objection_ids(db, [x.id for x in rows])
        apply_ids = [x.id for x in rows]
        families = {fe.apply_id: fe for fe in db.scalars(select(AidFamilyEconomy).where(
            AidFamilyEconomy.tenant_id == _tid(), AidFamilyEconomy.apply_id.in_(apply_ids),
            AidFamilyEconomy.is_deleted.is_(False))).all()} if apply_ids else {}
        return [
            _apply_row(x, students.get(int(x.student_id)) if x.student_id else None,
                       families.get(x.id), has_pending_objection=int(x.id) in pending)
            for x in rows
        ], total, status_counts


def get_application(apply_id, user) -> dict:
    with session() as db:
        x, s = _load(db, apply_id)
        _scope_or_403(db, x.student_id, user)
        return _apply_row(x, s, _family_of(db, x.id),
                          has_pending_objection=int(x.id) in _pending_objection_ids(db, [x.id]))


def reveal_family_economy(apply_id, user, reason="") -> dict:
    with session() as db:
        x, s = _load(db, apply_id)
        _scope_or_403(db, x.student_id, user)
        fe = _family_of(db, x.id)
    if not _can_sensitive_view(user, x):
        audit_insert("SENSITIVE_VIEW", "aid_family_economy",
                     {"applyId": str(apply_id), "reason": reason, "granted": False}, "DENY")
        raise no_permission("无家庭经济完整信息查看权限")
    audit_insert("SENSITIVE_VIEW", "aid_family_economy",
                 {"applyId": str(apply_id), "studentId": str(x.student_id), "reason": reason,
                  "granted": True}, "SUCCESS")
    return {"applyId": str(x.id), "studentId": str(x.student_id),
            "realName": s.real_name if s else "", "familyEconomy": _reveal_family(fe)}


def difficult_students(user, level=None, page=1, page_size=50):
    from app.core.pagination import normalize_page
    from app.models import AidApply, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        page, page_size = normalize_page(page, page_size, default_size=50)
        latest = (
            select(
                AidApply.student_id.label("student_id"),
                func.max(AidApply.id).label("max_id"),
            )
            .where(
                AidApply.tenant_id == _tid(),
                AidApply.status == "APPROVED",
                AidApply.is_deleted.is_(False),
            )
            .group_by(AidApply.student_id)
            .subquery()
        )
        conds = [
            AidApply.id == latest.c.max_id,
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ]
        if level:
            conds.append(AidApply.final_level == level)
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        base = (
            select(AidApply)
            .join(latest, AidApply.id == latest.c.max_id)
            .join(StudentProfile, StudentProfile.id == AidApply.student_id)
            .where(*conds)
        )
        total = int(db.scalar(
            select(func.count()).select_from(base.subquery())) or 0)
        rows = db.scalars(
            base.order_by(AidApply.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        students = _students_by_ids(db, rows)
        out = []
        for x in rows:
            s = students.get(int(x.student_id)) if x.student_id else None
            out.append({
                "studentId": str(x.student_id),
                "realName": s.real_name if s else "",
                "level": x.final_level,
                "levelLabel": LEVELS.get(x.final_level, ""),
                "identifiedAt": _iso(x.result_at),
                "batchId": str(x.batch_id),
            })
        return out, total


def is_in_difficult_library(db, student_id) -> str | None:
    from app.models import AidApply
    x = db.scalars(select(AidApply).where(
        AidApply.tenant_id == _tid(), AidApply.student_id == int(student_id),
        AidApply.status == "APPROVED", AidApply.is_deleted.is_(False)).order_by(
        AidApply.id.desc())).first()
    return x.final_level if x else None


def aid_stats(user):
    """困难认定统计：在数据库侧按状态/等级聚合，口径与范围列表一致。"""
    from app.models import AidApply, AidBatch, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        base = [
            AidApply.tenant_id == _tid(),
            AidApply.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ]
        if allowed is not None:
            base.append(StudentProfile.class_id.in_(allowed or {-1}))
        status_rows = db.execute(
            select(AidApply.status, func.count(AidApply.id))
            .join(StudentProfile, StudentProfile.id == AidApply.student_id)
            .where(*base).group_by(AidApply.status)
        ).all()
        level_rows = db.execute(
            select(AidApply.final_level, func.count(AidApply.id))
            .join(StudentProfile, StudentProfile.id == AidApply.student_id)
            .where(*base, AidApply.status == "APPROVED", AidApply.final_level.is_not(None))
            .group_by(AidApply.final_level)
        ).all()
        by_status = {str(key or ""): int(count or 0) for key, count in status_rows}
        by_level = {str(key or ""): int(count or 0) for key, count in level_rows}
        total = sum(by_status.values())
        approved = by_status.get("APPROVED", 0)
        batch_count = int(db.scalar(select(func.count()).select_from(AidBatch).where(
            AidBatch.tenant_id == _tid(), AidBatch.is_deleted.is_(False),
        )) or 0)
        return {
            "total": total, "approved": approved,
            "publicity": by_status.get("PUBLICITY", 0),
            "rejected": by_status.get("REJECTED", 0),
            "batchCount": batch_count,
            "approvalRate": round(approved / total, 3) if total else 0.0,
            "byStatus": [{"key": key, "count": count} for key, count in by_status.items()],
            "byLevel": [{"key": key, "count": count} for key, count in by_level.items()],
        }

def _obj_row(o, s=None) -> dict:
    return {
        "objectionId": str(o.id), "applyId": str(o.apply_id), "studentId": str(o.student_id or ""),
        "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
        "objectorName": o.objector_name or "", "reason": o.reason or "",
        "status": o.status, "statusLabel": _L_OBJ.get(o.status, o.status),
        "result": o.result or "", "resultLabel": _L_OBJ_RESULT.get(o.result, ""),
        "reviewOpinion": o.review_opinion or "", "reviewer": o.reviewer or "",
        "reviewedAt": _iso(o.reviewed_at), "version": int(o.version or 0),
    }


def submit_objection(apply_id, body, user, *, skip_scope_check: bool = False) -> dict:
    from app.models import AidApply, AidObjection, StudentProfile
    if isinstance(body, dict):
        reason = str(body.get("reason") or "").strip()
        objector = body.get("objectorName")
    else:
        reason = str(getattr(body, "reason", None) or "").strip()
        objector = getattr(body, "objectorName", None)
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "异议理由至少 5 字")
    with session() as db:
        x = db.scalars(select(AidApply).where(AidApply.id == int(apply_id)).with_for_update()).first()
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("认定申请不存在")
        if not skip_scope_check:
            _scope_or_403(db, x.student_id, user)
        if x.status != "PUBLICITY":
            raise AppException("DATA_CONFLICT", "仅公示中的申请可提异议")
        from app.services import affairs_appeal_todo_service as appeal_todo
        appeal_todo.require_submission_assignee(db, "AID_OBJECTION_REVIEW", int(x.student_id))
        dup = db.scalars(select(AidObjection).where(
            AidObjection.tenant_id == _tid(), AidObjection.apply_id == int(apply_id),
            AidObjection.status == "SUBMITTED", AidObjection.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该申请已有进行中的异议")
        o = AidObjection(tenant_id=_tid(), apply_id=int(apply_id), student_id=x.student_id,
                         objector_name=objector, reason=reason, status="SUBMITTED",
                         open_key=int(apply_id))
        db.add(o)
        try:
            db.flush()
        except Exception as e:
            from sqlalchemy.exc import IntegrityError
            if isinstance(e, IntegrityError):
                db.rollback()
                raise AppException("DATA_CONFLICT", "该申请已有进行中的异议")
            raise
        _audit(db, x.id, "AID_OBJECTION_SUBMIT", "")
        db.commit(); db.refresh(o)
        _drain_message_outbox()
        s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
        result = _obj_row(o, s)
        return appeal_todo.sync_after_submit("AID_OBJECTION_REVIEW", result, "objectionId", "id")


def list_objections(user, status=None, page=1, page_size=50):
    """异议列表使用数据库范围过滤、真计数和真分页，避免全量加载及逐行查学生。"""
    from app.models import AidObjection, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids

    page, page_size = normalize_page(page, page_size)
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        student_join = and_(
            StudentProfile.id == AidObjection.student_id,
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        conds = [AidObjection.tenant_id == _tid(), AidObjection.is_deleted.is_(False)]
        if status:
            conds.append(AidObjection.status == status)
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        total = int(db.scalar(
            select(func.count()).select_from(AidObjection)
            .outerjoin(StudentProfile, student_join).where(*conds)
        ) or 0)
        rows = db.execute(
            select(AidObjection, StudentProfile)
            .outerjoin(StudentProfile, student_join).where(*conds)
            .order_by(AidObjection.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return [_obj_row(objection, student) for objection, student in rows], total


def review_objection(objection_id, body, user) -> dict:
    from datetime import datetime
    from app.models import AidApply, AidObjection, StudentProfile
    if isinstance(body, dict):
        result = str(body.get("result") or "").strip()
        opinion = str(body.get("opinion") or "").strip()
    else:
        result = str(getattr(body, "result", None) or "").strip()
        opinion = str(getattr(body, "opinion", None) or "").strip()
    if result not in ("SUSTAINED", "OVERRULED"):
        raise AppException("VALIDATION_ERROR", "复核结论非法")
    if len(opinion) < 5:
        raise AppException("VALIDATION_ERROR", "复核意见至少 5 字")
    with session() as db:
        o = db.scalars(select(AidObjection).where(
            AidObjection.id == int(objection_id)).with_for_update()).first()
        if not o or o.is_deleted or o.tenant_id != _tid():
            raise not_found("异议不存在")
        _scope_or_403(db, o.student_id, user)
        expected_version = body.get("version") if isinstance(body, dict) else getattr(body, "version", None)
        atomic_claim_version(db, o, expected_version)
        if o.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "该异议已复核")
        o.status, o.result = "CLOSED", result
        o.open_key = None
        o.review_opinion, o.reviewer = opinion, _op()[0]
        o.reviewed_at, o.version = datetime.utcnow(), o.version + 1
        if result == "SUSTAINED":
            x = db.get(AidApply, int(o.apply_id))
            if x and x.status in ("PUBLICITY", "APPROVED"):
                was_approved = x.status == "APPROVED"
                old_level = x.final_level
                x.status, x.result_at, x.return_reason = "REJECTED", datetime.utcnow(), (opinion[:200] or "公示异议成立")
                x.version += 1
                if was_approved:
                    from app.models import AidLevelHistory, StudentStageEvent
                    db.add(AidLevelHistory(
                        tenant_id=_tid(), student_id=int(x.student_id), from_level=old_level,
                        to_level="", change_type="ADJUST", apply_id=x.id, batch_id=x.batch_id,
                        effective_at=datetime.utcnow()))
                    db.add(StudentStageEvent(
                        tenant_id=_tid(), student_id=int(x.student_id), from_stage="AID_APPROVED",
                        to_stage="AID_REVOKED", reason="公示异议成立，撤回困难认定结果",
                        source_module="student-affairs"))
                    x.final_level = None
                _todo_done(db, x.id)
                _msg(db, x.student_id, "困难认定未通过",
                     x.return_reason or "公示异议成立，认定结果已取消", "WORKFLOW_RESULT", x.id)
        _audit(db, o.apply_id, "AID_OBJECTION_REVIEW", result)
        db.commit(); db.refresh(o)
        _drain_message_outbox()
        s = db.get(StudentProfile, int(o.student_id)) if o.student_id else None
        result_row = _obj_row(o, s)
        from app.services import affairs_appeal_todo_service as appeal_todo
        return appeal_todo.sync_after_review("AID_OBJECTION_REVIEW", int(objection_id), result_row)
