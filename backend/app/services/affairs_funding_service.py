"""13A-P3 奖助闭环（统一资助抽象，V1 只启用 SCHOLARSHIP/GRANT）。

11 态：DRAFT/SUBMITTED/COUNSELOR_REVIEW/COLLEGE_REVIEW/SCHOOL_REVIEW/PUBLICITY/
GRANTED/REJECTED/RETURNED/CANCELLED/ARCHIVED（勤工 ON_POST/TERMINATED、贷款 P2 后置）。
资格硬校验链（受理即拦）：奖学金查学籍/处分未解除/成绩挂科；助学金查困难库在库。
管理端 apply 直达 COUNSELOR_REVIEW 并建 workflow；SCHOOL_REVIEW 通过→PUBLICITY；
公示期满(可配 0 天)→GRANTED，写 StageEvent 进 360。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

PROJECT_TYPES = {"SCHOLARSHIP", "GRANT", "WORK_STUDY", "LOAN",
                 "TUITION_REDUCTION", "TEMPORARY_AID", "GREEN_CHANNEL"}
V1_TYPES = {"SCHOLARSHIP", "GRANT"}  # 本阶段只做这两类
FUND_NODES = ["COUNSELOR_REVIEW", "COLLEGE_REVIEW", "SCHOOL_REVIEW"]
_TERMINAL = {"GRANTED", "REJECTED", "CANCELLED", "ARCHIVED"}
_AMOUNT_ROLES = {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN", "FUNDING_TEACHER"}

L_FUND = {
    "DRAFT": "草稿", "SUBMITTED": "已提交", "COUNSELOR_REVIEW": "辅导员初审",
    "COLLEGE_REVIEW": "学院评审", "SCHOOL_REVIEW": "学校审批", "PUBLICITY": "公示中",
    "GRANTED": "已获资助", "REJECTED": "已驳回", "RETURNED": "已退回",
    "CANCELLED": "已取消", "ARCHIVED": "已归档",
}


def _req_int(v, field):
    """必填数字字段安全转 int：非数字→400（原裸 int() 抛 ValueError→500）。"""
    raw = str(v or "").strip()
    if not raw.isdigit():
        raise AppException("VALIDATION_ERROR", f"请选择有效{field}")
    return int(raw)


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
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="FUNDING", biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _wf_code(ptype):
    return "AFFAIRS_GRANT" if ptype == "GRANT" else "AFFAIRS_SCHOLARSHIP"


def _assignee_for(db, node, student_id):
    if node == "COUNSELOR_REVIEW" and student_id:
        from app.models import SchoolClass, StudentProfile
        s = db.get(StudentProfile, int(student_id))
        if s and s.class_id:
            c = db.get(SchoolClass, int(s.class_id))
            if c and c.counselor_id:
                return int(c.counselor_id)
    return 0


def _open_wf(db, app_id, ptype, applicant_id, title, first_node, assignee_id):
    from app.models import WorkflowInstance, WorkflowTask
    from app.services.runtime_preset_install_service import ensure_workflow_enabled
    ensure_workflow_enabled(db, _tid(), _wf_code(ptype))
    inst = WorkflowInstance(tenant_id=_tid(), workflow_code=_wf_code(ptype),
                            source_module="student-affairs", source_biz_type="FUNDING",
                            source_biz_id=int(app_id), applicant_id=int(applicant_id or 0),
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


def _todo_upsert(db, app_id, assignee_id, student_id, title):
    from app.models import UnifiedTodo
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_id == int(app_id), UnifiedTodo.todo_type == "FUNDING_APPROVAL",
        UnifiedTodo.assignee_id == int(assignee_id or 0),
        UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title, row.status, row.version = title, "PENDING", row.version + 1
    else:
        db.add(UnifiedTodo(tenant_id=_tid(), source_module="student-affairs", source_biz_type="FUNDING",
                           source_biz_id=int(app_id), todo_type="FUNDING_APPROVAL",
                           assignee_id=int(assignee_id or 0), student_id=student_id, title=title,
                           status="PENDING"))


def _todo_done(db, app_id):
    from app.models import UnifiedTodo
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.source_biz_id == int(app_id), UnifiedTodo.todo_type == "FUNDING_APPROVAL",
            UnifiedTodo.is_deleted.is_(False))).all():
        r.status, r.version = "DONE", r.version + 1


def _msg(db, receiver_id, title, content, mtype, app_id):
    from app.services.message_event_outbox_service import emit_receiver_notice
    emit_receiver_notice(
        db,
        event_code="FUNDING.NOTICE",
        source_module="student-affairs",
        source_biz_type="funding",
        source_biz_id=int(app_id),
        receiver_id=receiver_id,
        title=title,
        content=content,
        receiver_as="student",
        dedup_extra=mtype,
    )


def _drain_message_outbox():
    from app.services.message_event_outbox_service import try_process_pending_outbox
    try_process_pending_outbox(worker_id="funding-inline")


def _scope_or_403(db, student_id, user):
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is None:
        return
    s = db.get(StudentProfile, int(student_id)) if student_id else None
    if not s or s.class_id not in allowed:
        raise AppException("NO_DATA_SCOPE", "该申请不在您的数据范围内")


def _uid_int(user) -> int:
    raw = str((user or {}).get("userId") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _fund_node_visible(ctx, node: str) -> bool:
    """奖助节点：学校审批仅 TENANT_ALL；学院可审学院/辅导员节点；其余仅辅导员初审。"""
    if ctx.scope_type == "TENANT_ALL":
        return True
    if node == "SCHOOL_REVIEW":
        return False
    if ctx.scope_type == "COLLEGE":
        return node in ("COUNSELOR_REVIEW", "COLLEGE_REVIEW")
    return node == "COUNSELOR_REVIEW"


def _check_fund_review_node(db, x, user):
    from app.core.affairs_security import build_affairs_context
    ctx = build_affairs_context(user, db)
    if not _fund_node_visible(ctx, x.status):
        raise AppException("NO_PERMISSION",
                           f"无权审批当前节点（{L_FUND.get(x.status, x.status)}）")
    if ctx.scope_type == "TENANT_ALL" or not x.workflow_instance_id:
        return
    from app.models import WorkflowTask
    task = db.scalars(select(WorkflowTask).where(
        WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == int(x.workflow_instance_id),
        WorkflowTask.node_code == x.status, WorkflowTask.status == "PENDING",
        WorkflowTask.is_deleted.is_(False)).order_by(WorkflowTask.id.desc())).first()
    if not task or not task.assignee_id:
        return
    uid = _uid_int(user)
    if uid and int(task.assignee_id) != uid:
        raise AppException("NO_PERMISSION", "当前审批任务未指派给您")


# ── 资格硬校验链（跨域只读，快照入 check_snapshot_json）──

def _check_scholarship(db, student_id) -> dict:
    """奖学金：学籍在籍 + 无未解除处分 + 无挂科。返回快照 dict（含 ok 与各项）。"""
    from app.models import (AcademicGrade, AcademicStudent, CsDiscipline,
                            CsServiceStudent, StudentProfile)
    s = db.get(StudentProfile, int(student_id))
    status_ok = bool(s and (s.student_status in (None, "NORMAL", "在籍", "ACTIVE")))
    # 处分：映射到在校服务台账 → 未解除(record_status=ACTIVE)
    discipline_ok = True
    cs = db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == _tid(), CsServiceStudent.student_id == int(student_id),
        CsServiceStudent.is_deleted.is_(False))).first()
    if cs:
        cnt = db.scalar(select(CsDiscipline).where(
            CsDiscipline.tenant_id == _tid(), CsDiscipline.cs_student_id == cs.id,
            CsDiscipline.record_status == "ACTIVE", CsDiscipline.is_deleted.is_(False)))
        discipline_ok = cnt is None
    # 成绩：映射到学业台账 → 无挂科(pass_status=FAILED)
    grade_ok = True
    acad = db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == int(student_id),
        AcademicStudent.is_deleted.is_(False))).first()
    if acad:
        fail = db.scalar(select(AcademicGrade).where(
            AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == acad.id,
            AcademicGrade.pass_status == "FAILED", AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False)))
        grade_ok = fail is None
    return {"type": "SCHOLARSHIP", "statusOk": status_ok, "disciplineOk": discipline_ok,
            "gradeOk": grade_ok, "ok": status_ok and discipline_ok and grade_ok}


def _check_grant(db, student_id) -> dict:
    """助学金：必须在困难库（认定通过）。"""
    from app.services.affairs_aid_service import is_in_difficult_library
    level = is_in_difficult_library(db, student_id)
    return {"type": "GRANT", "aidLevel": level, "inDifficultLibrary": bool(level), "ok": bool(level)}


def _reject_reason(snap: dict) -> str:
    if snap["type"] == "GRANT":
        return "未通过困难认定或已过期，不满足助学金申请条件"
    parts = []
    if not snap.get("statusOk"):
        parts.append("学籍异常")
    if not snap.get("disciplineOk"):
        parts.append("存在未解除处分")
    if not snap.get("gradeOk"):
        parts.append("存在挂科成绩")
    return "、".join(parts) or "资格校验未通过"


# ── 序列化 ──

def _amount_view(amount, user):
    """金额脱敏：授权角色见真实值，其余见区间。"""
    if amount is None:
        return None
    role = (user or {}).get("currentRoleCode")
    if role in _AMOUNT_ROLES:
        return float(amount)
    n = float(amount)
    if n < 2000:
        return "2000以下"
    if n < 5000:
        return "2000-5000"
    return "5000以上"


def _project_row(p) -> dict:
    return {"projectId": str(p.id), "projectType": p.project_type, "projectName": p.project_name,
            "amount": float(p.amount) if p.amount is not None else None,
            "quota": p.quota, "status": p.status}


def _batch_row(b) -> dict:
    return {"batchId": str(b.id), "projectId": str(b.project_id), "projectType": b.project_type,
            "schoolYear": b.year_code, "applyStart": _iso(b.apply_start), "applyEnd": _iso(b.apply_end),
            "publicityDays": b.publicity_days if b.publicity_days is not None else 5,
            "quota": b.quota, "status": b.status}


def _app_row(x, user, s=None, *, has_pending_appeal: bool = False) -> dict:
    return {"applicationId": str(x.id), "batchId": str(x.batch_id), "studentId": str(x.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "projectType": x.project_type, "applySource": x.apply_source,
            "amount": _amount_view(x.amount, user), "status": x.status,
            "statusLabel": L_FUND.get(x.status, x.status),
            "returnReason": getattr(x, "return_reason", None) or "",
            "hasPendingAppeal": bool(has_pending_appeal),
            "currentNode": x.status if x.status in FUND_NODES else "", "version": x.version}


def _pending_appeal_ids(db, app_ids) -> set[int]:
    from app.models import FundingAppeal
    ids = {int(i) for i in app_ids if i}
    if not ids:
        return set()
    return set(db.scalars(select(FundingAppeal.application_id).where(
        FundingAppeal.tenant_id == _tid(), FundingAppeal.application_id.in_(ids),
        FundingAppeal.status == "SUBMITTED", FundingAppeal.is_deleted.is_(False))).all())


def _assert_no_open_appeal(db, app_id):
    from app.models import FundingAppeal
    if db.scalars(select(FundingAppeal.id).where(
            FundingAppeal.tenant_id == _tid(), FundingAppeal.application_id == int(app_id),
            FundingAppeal.status == "SUBMITTED", FundingAppeal.is_deleted.is_(False)).limit(1)).first():
        raise AppException("DATA_CONFLICT", "该申请有进行中的公示申诉，须复核完成后方可确认获资助")



# ═══════════ 项目 / 批次 ═══════════

def create_project(body, user) -> dict:
    if body.projectType not in PROJECT_TYPES:
        raise AppException("VALIDATION_ERROR", "项目类型非法")
    if body.projectType not in V1_TYPES:
        raise AppException("DATA_CONFLICT", "该资助类型 V1 暂未开放（仅奖学金/助学金）")
    with session() as db:
        from app.models import FundingProject
        p = FundingProject(tenant_id=_tid(), project_name=body.projectName, project_type=body.projectType,
                           amount=body.amount, quota=body.quota,
                           condition_json=json.dumps(body.conditions or {}, ensure_ascii=False),
                           status="ENABLED")
        db.add(p)
        db.flush()
        _audit(db, p.id, "PROJECT_CREATE", body.projectType)
        db.commit()
        _drain_message_outbox()
        db.refresh(p)
        return _project_row(p)


def list_projects(user, project_type=None, status=None, page=1, page_size=20):
    with session() as db:
        from app.models import FundingProject
        conds = [FundingProject.tenant_id == _tid(), FundingProject.is_deleted.is_(False)]
        if project_type:
            conds.append(FundingProject.project_type == project_type)
        if status:
            conds.append(FundingProject.status == status)
        rows = db.scalars(select(FundingProject).where(*conds).order_by(FundingProject.id.desc())).all()
        out = [_project_row(p) for p in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def create_batch(body, user) -> dict:
    with session() as db:
        from app.models import FundingBatch, FundingProject
        p = db.get(FundingProject, int(body.projectId))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("资助项目不存在")
        publish = bool(getattr(body, "publish", False))
        b = FundingBatch(tenant_id=_tid(), project_id=p.id, project_type=p.project_type,
                         year_code=body.schoolYear, apply_start=_parse_dt(body.applyStart),
                         apply_end=_parse_dt(body.applyEnd),
                         publicity_days=(body.publicityDays if body.publicityDays is not None else 5),
                         quota=body.quota, status=("OPEN" if publish else "DRAFT"))
        db.add(b)
        db.flush()
        _audit(db, b.id, "BATCH_CREATE", f"publish={publish}")
        db.commit()
        _drain_message_outbox()
        db.refresh(b)
        return _batch_row(b)


def list_batches(user, project_id=None, status=None, page=1, page_size=20):
    with session() as db:
        from app.models import FundingBatch
        conds = [FundingBatch.tenant_id == _tid(), FundingBatch.is_deleted.is_(False)]
        if project_id:
            conds.append(FundingBatch.project_id == int(project_id))
        if status:
            conds.append(FundingBatch.status == status)
        rows = db.scalars(select(FundingBatch).where(*conds).order_by(FundingBatch.id.desc())).all()
        out = [_batch_row(b) for b in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


# ═══════════ 申请（含资格硬校验）═══════════

def apply(body, user, *, skip_scope_check: bool = False) -> dict:
    student_id = _req_int(getattr(body, "studentId", None), "学生")
    with session() as db:
        from app.models import FundingApplication, FundingBatch, StudentProfile
        s = db.get(StudentProfile, student_id)
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在或不在数据范围内")
        # skip_scope_check=True 仅供学生本人自助申请入口使用（studentId 已由服务端按登录身份
        # 解析，不接受客户端指定）；越范围禁止为他院学生建奖助申请的校验只对代发起场景生效。
        if not skip_scope_check:
            _scope_or_403(db, student_id, user)
        b = db.get(FundingBatch, _req_int(getattr(body, "batchId", None), "批次"))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("资助批次不存在")
        if b.status != "OPEN":
            raise AppException("DATA_CONFLICT", "批次未开放或已截止")
        # 同批次重复申请 → 409
        dup = db.scalars(select(FundingApplication).where(
            FundingApplication.tenant_id == _tid(), FundingApplication.batch_id == b.id,
            FundingApplication.student_id == student_id, FundingApplication.is_deleted.is_(False))).first()
        if dup and dup.status not in _TERMINAL:
            raise AppException("DATA_CONFLICT", "该生在本批次已有在途申请，不可重复提交")
        # 资格硬校验链
        snap = _check_grant(db, student_id) if b.project_type == "GRANT" else _check_scholarship(db, student_id)
        if not snap["ok"]:
            raise AppException("DATA_CONFLICT", _reject_reason(snap))
        first = FUND_NODES[0]
        x = FundingApplication(tenant_id=_tid(), batch_id=b.id, student_id=student_id,
                               apply_source=(body.applySource or "SELF"), project_type=b.project_type,
                               amount=body.amount, statement=(body.statement or ""),
                               check_snapshot_json=json.dumps(snap, ensure_ascii=False), status=first)
        db.add(x)
        db.flush()
        assignee = _assignee_for(db, first, student_id)
        inst = _open_wf(db, x.id, b.project_type, student_id, f"{s.real_name} {b.project_type}", first, assignee)
        x.workflow_instance_id = inst.id
        _todo_upsert(db, x.id, assignee, student_id, f"资助申请待审：{s.real_name}")
        _audit(db, x.id, "APPLY", b.project_type)
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _app_row(x, user, s)


# ═══════════ 评审 ═══════════

def _load(db, app_id):
    from app.models import FundingApplication, StudentProfile
    x = db.get(FundingApplication, int(app_id))
    if not x or x.is_deleted or x.tenant_id != _tid():
        raise not_found("资助申请不存在")
    s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
    return x, s


def _act_task(db, x, action, reason=""):
    from app.models import WorkflowInstance
    inst = db.get(WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
    task = _cur_task(db, inst.id, x.status) if inst else None
    if task:
        task.status, task.acted_at, task.action_reason = action, datetime.utcnow(), reason
        task.version += 1
    return inst


def review(app_id, user, action, reason="") -> dict:
    action = (action or "").upper()
    with session() as db:
        from app.models import WorkflowTask
        x, s = _load(db, app_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in FUND_NODES:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请当前状态不可评审，请刷新")
        _check_fund_review_node(db, x, user)
        if action == "APPROVE":
            inst = _act_task(db, x, "APPROVED", reason or "")
            i = FUND_NODES.index(x.status)
            if i + 1 < len(FUND_NODES):
                nxt = FUND_NODES[i + 1]
                x.status, x.version = nxt, x.version + 1
                assignee = _assignee_for(db, nxt, x.student_id)
                # 无 workflow 实例的申请（如沙箱种子直接置 COUNSELOR_REVIEW，未走 apply() 开流程）
                # 仍推进状态机 + 建待办 + 落审计，只跳过需要 instance_id 的 WorkflowTask 行，避免
                # inst 为 None 时 inst.id 抛 AttributeError → 500（历史欠账：沙箱奖助 review APPROVE 崩）。
                if inst:
                    inst.current_node = nxt
                    db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=nxt,
                                        assignee_id=assignee, status="PENDING"))
                _todo_upsert(db, x.id, assignee, x.student_id,
                             f"资助申请待审（{L_FUND[nxt]}）：{s.real_name if s else ''}")
                _audit(db, x.id, "REVIEW_STEP", f"{FUND_NODES[i]}->{nxt}")
            else:
                x.status, x.publicity_at, x.version = "PUBLICITY", datetime.utcnow(), x.version + 1
                if inst:
                    inst.current_node = "PUBLICITY"
                _todo_done(db, x.id)
                _msg(db, x.student_id, "资助申请进入公示", "你的资助申请进入公示", "PUBLISHED_NOTICE", x.id)
                _audit(db, x.id, "TO_PUBLICITY")
        elif action in ("REJECT", "RETURN"):
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回/退回原因必填且不少于 5 字")
            inst = _act_task(db, x, action + "ED" if action == "REJECT" else "TRANSFERRED", reason.strip())
            new = "REJECTED" if action == "REJECT" else "RETURNED"
            x.status, x.return_reason, x.version = new, reason.strip(), x.version + 1
            if inst and action == "REJECT":
                inst.status = "REJECTED"
            _todo_done(db, x.id)
            _msg(db, x.student_id, f"资助申请{'未通过' if action == 'REJECT' else '被退回'}", reason.strip(),
                 "WORKFLOW_RESULT" if action == "REJECT" else "RETURNED_NOTICE", x.id)
            _audit(db, x.id, new, reason.strip())
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _app_row(x, user, s)


# ═══════════ 公示 → GRANTED ═══════════

def _grant_one(db, x):
    from app.models import StudentStageEvent, WorkflowInstance
    x.status, x.result_at, x.version = "GRANTED", datetime.utcnow(), x.version + 1
    if x.workflow_instance_id:
        inst = db.get(WorkflowInstance, int(x.workflow_instance_id))
        if inst:
            inst.status = "APPROVED"
    db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(x.student_id), from_stage=None,
                             to_stage="FUNDING_GRANTED",
                             reason=f"获得资助（{L_FUND.get(x.project_type, x.project_type)}）",
                             source_module="student-affairs"))
    _todo_done(db, x.id)
    _msg(db, x.student_id, "资助申请通过", "你的资助申请已通过并公示完成", "WORKFLOW_RESULT", x.id)
    _audit(db, x.id, "GRANTED")


def scan_publicity() -> dict:
    from app.models import FundingApplication, FundingBatch
    now = datetime.utcnow()
    with session() as db:
        rows = db.scalars(select(FundingApplication).where(
            FundingApplication.tenant_id == _tid(), FundingApplication.status == "PUBLICITY",
            FundingApplication.publicity_at.is_not(None),
            FundingApplication.is_deleted.is_(False))).all()
        pending = _pending_appeal_ids(db, [x.id for x in rows])
        cnt = skipped = 0
        for x in rows:
            if int(x.id) in pending:
                skipped += 1
                continue
            b = db.get(FundingBatch, int(x.batch_id))
            days = (b.publicity_days if b and b.publicity_days is not None else 5)
            if x.publicity_at + timedelta(days=days) <= now:
                # 再断言一次，避免扫描窗口内新提交申诉
                if int(x.id) in _pending_appeal_ids(db, [x.id]):
                    skipped += 1
                    continue
                _grant_one(db, x)
                cnt += 1
        db.commit()
        _drain_message_outbox()
        return {"count": cnt, "skippedAppeal": skipped}


def confirm_publicity(app_id, user) -> dict:
    with session() as db:
        x, s = _load(db, app_id)
        _scope_or_403(db, x.student_id, user)
        if x.status != "PUBLICITY":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请不在公示状态")
        _assert_no_open_appeal(db, x.id)
        _grant_one(db, x)
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _app_row(x, user, s, has_pending_appeal=False)



# ═══════════ 查询 ═══════════

def list_applications(user, batch_id=None, project_type=None, status=None, page=1, page_size=20):
    from app.models import FundingApplication, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [FundingApplication.tenant_id == _tid(), FundingApplication.is_deleted.is_(False)]
        if batch_id:
            conds.append(FundingApplication.batch_id == int(batch_id))
        if project_type:
            conds.append(FundingApplication.project_type == project_type)
        if status:
            conds.append(FundingApplication.status == status)
        rows = db.scalars(select(FundingApplication).where(*conds).order_by(
            FundingApplication.id.desc())).all()
        # 消 N+1：批量取本页学生档案，替代循环内逐行 db.get（行为等价，见 list_risks 同款收口）。
        sids = {int(x.student_id) for x in rows if x.student_id}
        students = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_(sids))).all()} if sids else {}
        pending = _pending_appeal_ids(db, [x.id for x in rows])
        out = []
        for x in rows:
            s = students.get(int(x.student_id)) if x.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            out.append(_app_row(x, user, s, has_pending_appeal=int(x.id) in pending))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def funding_stats(user) -> dict:
    """奖助统计（按状态/项目类型聚合，计数口径不含金额明细，规避金额脱敏）；数据范围与列表一致。"""
    from app.models import FundingApplication, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        rows = db.scalars(select(FundingApplication).where(
            FundingApplication.tenant_id == _tid(), FundingApplication.is_deleted.is_(False))).all()
        # 消 N+1：批量取学生档案用于数据范围判定（统计遍历全量，逐行 db.get 放大更明显）。
        sids = {int(x.student_id) for x in rows if x.student_id}
        students = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_(sids))).all()} if sids else {}
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        total = 0
        for x in rows:
            s = students.get(int(x.student_id)) if x.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            total += 1
            by_status[x.status] = by_status.get(x.status, 0) + 1
            if x.project_type:
                by_type[x.project_type] = by_type.get(x.project_type, 0) + 1
    return {"total": total, "granted": by_status.get("GRANTED", 0),
            "byStatus": [{"key": k, "count": v} for k, v in by_status.items()],
            "byType": [{"key": k, "count": v} for k, v in by_type.items()]}


def get_application(app_id, user) -> dict:
    with session() as db:
        x, s = _load(db, app_id)
        _scope_or_403(db, x.student_id, user)
        d = _app_row(x, user, s, has_pending_appeal=int(x.id) in _pending_appeal_ids(db, [x.id]))
        d["checkSnapshot"] = json.loads(x.check_snapshot_json) if x.check_snapshot_json else {}
        return d


# ═══════════ 发放台账（C 包·发放状态/发放导入/异常处理）═══════════

_L_BANK = {"PENDING": "待发放", "ISSUED": "已发放", "FAILED": "发放失败", "RETURNED": "已退回"}


def _disb_uid(user):
    try:
        return int((user or {}).get("userId") or 0) or None
    except (TypeError, ValueError):
        return None


def _disb_row(d, user, s=None) -> dict:
    return {"disbursementId": str(d.id), "applicationId": str(d.application_id),
            "batchId": str(d.batch_id or ""), "studentId": str(d.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "projectType": d.project_type, "amount": _amount_view(d.amount, user),
            "disburseNo": d.disburse_no or "", "bankLast4": d.bank_last4 or "",
            "bankStatus": d.bank_status, "bankStatusLabel": _L_BANK.get(d.bank_status, d.bank_status),
            "issuedAt": _iso(d.issued_at), "failReason": d.fail_reason or ""}


def generate_disbursements(batch_id, user) -> dict:
    """按批次为 GRANTED 且尚无发放记录的申请生成发放台账(PENDING)。幂等。返回 {generated}。"""
    from app.models import FundingApplication, FundingDisbursement
    with session() as db:
        apps = db.scalars(select(FundingApplication).where(
            FundingApplication.tenant_id == _tid(), FundingApplication.batch_id == int(batch_id),
            FundingApplication.status == "GRANTED", FundingApplication.is_deleted.is_(False))).all()
        made = 0
        for a in apps:
            dup = db.scalars(select(FundingDisbursement).where(
                FundingDisbursement.tenant_id == _tid(),
                FundingDisbursement.application_id == a.id,
                FundingDisbursement.is_deleted.is_(False))).first()
            if dup:
                continue
            db.add(FundingDisbursement(tenant_id=_tid(), application_id=a.id, batch_id=a.batch_id,
                                       student_id=a.student_id, project_type=a.project_type,
                                       amount=a.amount, bank_status="PENDING", created_by=_disb_uid(user)))
            made += 1
        if made:
            _audit(db, int(batch_id), "FUNDING_DISBURSE_GENERATE", f"{made}条")
        db.commit()
        _drain_message_outbox()
        return {"generated": made}


def list_disbursements(user, batch_id=None, bank_status=None, page=1, page_size=50):
    from app.models import FundingDisbursement, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [FundingDisbursement.tenant_id == _tid(), FundingDisbursement.is_deleted.is_(False)]
        if batch_id:
            conds.append(FundingDisbursement.batch_id == int(batch_id))
        if bank_status:
            conds.append(FundingDisbursement.bank_status == bank_status)
        rows = db.scalars(select(FundingDisbursement).where(*conds).order_by(
            FundingDisbursement.id.desc())).all()
        out = []
        for d in rows:
            s = db.get(StudentProfile, int(d.student_id)) if d.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            out.append(_disb_row(d, user, s))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def _load_disb(db, disbursement_id):
    from app.models import FundingDisbursement
    d = db.get(FundingDisbursement, int(disbursement_id))
    if not d or d.is_deleted or d.tenant_id != _tid():
        raise not_found("发放记录不存在")
    return d


def issue_disbursement(disbursement_id, body, user) -> dict:
    """标记已发放（PENDING/FAILED→ISSUED，记发放批次号+卡后4位）。"""
    from datetime import datetime
    from app.models import StudentProfile
    with session() as db:
        d = _load_disb(db, disbursement_id)
        _scope_or_403(db, d.student_id, user)
        if d.bank_status == "ISSUED":
            raise AppException("DATA_CONFLICT", "已发放，不可重复")
        d.bank_status, d.issued_at, d.fail_reason = "ISSUED", datetime.utcnow(), None
        d.disburse_no = getattr(body, "disburseNo", None) or d.disburse_no
        last4 = getattr(body, "bankLast4", None)
        if last4:
            d.bank_last4 = str(last4)[-4:]
        d.version += 1
        _audit(db, d.id, "FUNDING_DISBURSE_ISSUE", d.disburse_no or "")
        db.commit(); db.refresh(d)
        _drain_message_outbox()
        s = db.get(StudentProfile, int(d.student_id))
        return _disb_row(d, user, s)


def fail_disbursement(disbursement_id, user, reason="") -> dict:
    """标记发放失败（原因≥5字；可再改发放）。"""
    from app.models import StudentProfile
    if len((reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "失败原因至少 5 字")
    with session() as db:
        d = _load_disb(db, disbursement_id)
        _scope_or_403(db, d.student_id, user)
        if d.bank_status == "ISSUED":
            raise AppException("DATA_CONFLICT", "已发放不可置失败")
        d.bank_status, d.fail_reason, d.version = "FAILED", reason.strip(), d.version + 1
        _audit(db, d.id, "FUNDING_DISBURSE_FAIL", reason.strip())
        db.commit(); db.refresh(d)
        _drain_message_outbox()
        s = db.get(StudentProfile, int(d.student_id))
        return _disb_row(d, user, s)


def disbursement_stats(user) -> dict:
    """发放概览：按状态计数 + 已发放金额合计(授权角色见真实合计,否则仅计数)。"""
    from app.models import FundingDisbursement
    with session() as db:
        rows = db.scalars(select(FundingDisbursement).where(
            FundingDisbursement.tenant_id == _tid(),
            FundingDisbursement.is_deleted.is_(False))).all()
        by_status = {}
        issued_total = 0.0
        role = (user or {}).get("currentRoleCode")
        for d in rows:
            by_status[d.bank_status] = by_status.get(d.bank_status, 0) + 1
            if d.bank_status == "ISSUED":
                issued_total += float(d.amount or 0)
        out = {"total": len(rows),
               "byStatus": [{"key": k, "label": _L_BANK.get(k, k), "count": v} for k, v in by_status.items()]}
        if role in _AMOUNT_ROLES:
            out["issuedAmountTotal"] = round(issued_total, 2)
        return out


# ═══════════ 公示申诉（对齐困难认定异议）═══════════

_L_APPEAL = {"SUBMITTED": "待复核", "CLOSED": "已复核"}
_L_APPEAL_RESULT = {"SUSTAINED": "申诉成立(驳回)", "OVERRULED": "申诉不成立(维持)"}


def _appeal_row(o, s=None) -> dict:
    return {
        "appealId": str(o.id), "applicationId": str(o.application_id),
        "studentId": str(o.student_id or ""),
        "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
        "appellantName": o.appellant_name or "", "reason": o.reason or "",
        "status": o.status, "statusLabel": _L_APPEAL.get(o.status, o.status),
        "result": o.result or "", "resultLabel": _L_APPEAL_RESULT.get(o.result or "", ""),
        "reviewOpinion": o.review_opinion or "", "reviewer": o.reviewer or "",
        "reviewedAt": _iso(o.reviewed_at),
    }


def submit_appeal(app_id, body, user, *, skip_scope_check: bool = False) -> dict:
    """对公示中资助申请提起申诉（仅 PUBLICITY；理由≥5字；进行中唯一）。"""
    from app.models import FundingAppeal, FundingApplication, StudentProfile
    if isinstance(body, dict):
        reason = str(body.get("reason") or "").strip()
        appellant = body.get("appellantName")
    else:
        reason = str(getattr(body, "reason", None) or "").strip()
        appellant = getattr(body, "appellantName", None)
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申诉理由至少 5 字")
    with session() as db:
        x = db.scalars(select(FundingApplication).where(
            FundingApplication.id == int(app_id)).with_for_update()).first()
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("资助申请不存在")
        if x.status != "PUBLICITY":
            raise AppException("DATA_CONFLICT", "仅公示中的资助申请可申诉")
        if not skip_scope_check:
            _scope_or_403(db, x.student_id, user)
        dup = db.scalars(select(FundingAppeal).where(
            FundingAppeal.tenant_id == _tid(), FundingAppeal.application_id == int(app_id),
            FundingAppeal.status == "SUBMITTED", FundingAppeal.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该申请已有进行中的申诉")
        o = FundingAppeal(
            tenant_id=_tid(), application_id=int(app_id), student_id=x.student_id,
            appellant_name=appellant, reason=reason, status="SUBMITTED",
            open_key=int(app_id))
        db.add(o)
        try:
            db.flush()
        except Exception as e:
            from sqlalchemy.exc import IntegrityError
            if isinstance(e, IntegrityError):
                db.rollback()
                raise AppException("DATA_CONFLICT", "该申请已有进行中的申诉")
            raise
        _audit(db, x.id, "FUNDING_APPEAL_SUBMIT", reason[:200])
        db.commit()
        _drain_message_outbox()
        db.refresh(o)
        s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
        return _appeal_row(o, s)


def list_appeals(user, status=None, page=1, page_size=50):
    from app.models import FundingAppeal, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [FundingAppeal.tenant_id == _tid(), FundingAppeal.is_deleted.is_(False)]
        if status:
            conds.append(FundingAppeal.status == status)
        rows = db.scalars(select(FundingAppeal).where(*conds).order_by(FundingAppeal.id.desc())).all()
        out = []
        for o in rows:
            s = db.get(StudentProfile, int(o.student_id)) if o.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            out.append(_appeal_row(o, s))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def review_appeal(appeal_id, body, user) -> dict:
    """申诉复核：SUSTAINED→申请 REJECTED；OVERRULED→维持 PUBLICITY。意见≥5字。"""
    from app.models import FundingAppeal, FundingApplication, StudentProfile, WorkflowInstance
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
        o = db.scalars(select(FundingAppeal).where(
            FundingAppeal.id == int(appeal_id)).with_for_update()).first()
        if not o or o.is_deleted or o.tenant_id != _tid():
            raise not_found("申诉不存在")
        _scope_or_403(db, o.student_id, user)
        if o.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "该申诉已复核")
        o.status, o.result = "CLOSED", result
        o.open_key = None
        o.review_opinion, o.reviewer = opinion, _op()[0]
        o.reviewed_at, o.version = datetime.utcnow(), o.version + 1
        if result == "SUSTAINED":
            x = db.get(FundingApplication, int(o.application_id))
            # 正常应仍为 PUBLICITY（授予前已拦截进行中申诉）；若竞态已 GRANTED 亦撤回为驳回
            if x and x.status in ("PUBLICITY", "GRANTED"):
                was_granted = x.status == "GRANTED"
                x.status, x.result_at = "REJECTED", datetime.utcnow()
                x.return_reason = (opinion[:200] if opinion else "公示申诉成立")
                x.version += 1
                if x.workflow_instance_id:
                    inst = db.get(WorkflowInstance, int(x.workflow_instance_id))
                    if inst:
                        inst.status = "REJECTED"
                if was_granted and x.student_id:
                    from app.models import StudentStageEvent
                    db.add(StudentStageEvent(
                        tenant_id=_tid(), student_id=int(x.student_id), from_stage="FUNDING_GRANTED",
                        to_stage="FUNDING_REVOKED", reason="公示申诉成立，撤回已获资助资格",
                        source_module="student-affairs"))
                _todo_done(db, x.id)
                _msg(db, x.student_id, "资助申请未通过",
                     x.return_reason or "公示申诉成立，资助资格已取消", "WORKFLOW_RESULT", x.id)
        _audit(db, o.application_id, "FUNDING_APPEAL_REVIEW", result)
        db.commit()
        _drain_message_outbox()
        db.refresh(o)
        s = db.get(StudentProfile, int(o.student_id)) if o.student_id else None
        return _appeal_row(o, s)
