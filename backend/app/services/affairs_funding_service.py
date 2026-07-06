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
_AMOUNT_ROLES = {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN", "FUNDING_TEACHER", "ADMIN"}

L_FUND = {
    "DRAFT": "草稿", "SUBMITTED": "已提交", "COUNSELOR_REVIEW": "辅导员初审",
    "COLLEGE_REVIEW": "学院评审", "SCHOOL_REVIEW": "学校审批", "PUBLICITY": "公示中",
    "GRANTED": "已获资助", "REJECTED": "已驳回", "RETURNED": "已退回",
    "CANCELLED": "已取消", "ARCHIVED": "已归档",
}


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
    from app.models import UnifiedMessage
    db.add(UnifiedMessage(tenant_id=_tid(), receiver_id=int(receiver_id or 0),
                          source_module="student-affairs", source_biz_id=int(app_id),
                          title=title, content=content, message_type=mtype, status="UNREAD"))


def _scope_or_403(db, student_id, user):
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is None:
        return
    s = db.get(StudentProfile, int(student_id)) if student_id else None
    if not s or s.class_id not in allowed:
        raise AppException("NO_DATA_SCOPE", "该申请不在您的数据范围内")


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
    # 成绩：映射到学业台账 → 无挂科(pass_status=FAIL)
    grade_ok = True
    acad = db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == int(student_id),
        AcademicStudent.is_deleted.is_(False))).first()
    if acad:
        fail = db.scalar(select(AcademicGrade).where(
            AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == acad.id,
            AcademicGrade.pass_status == "FAIL", AcademicGrade.record_status == "ACTIVE",
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


def _app_row(x, user, s=None) -> dict:
    return {"applicationId": str(x.id), "batchId": str(x.batch_id), "studentId": str(x.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "projectType": x.project_type, "applySource": x.apply_source,
            "amount": _amount_view(x.amount, user), "status": x.status,
            "statusLabel": L_FUND.get(x.status, x.status),
            "currentNode": x.status if x.status in FUND_NODES else "", "version": x.version}


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

def apply(body, user) -> dict:
    student_id = int(body.studentId)
    with session() as db:
        from app.models import FundingApplication, FundingBatch, StudentProfile
        s = db.get(StudentProfile, student_id)
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在或不在数据范围内")
        b = db.get(FundingBatch, int(body.batchId))
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
        if action == "APPROVE":
            inst = _act_task(db, x, "APPROVED", reason or "")
            i = FUND_NODES.index(x.status)
            if i + 1 < len(FUND_NODES):
                nxt = FUND_NODES[i + 1]
                x.status, x.version = nxt, x.version + 1
                if inst:
                    inst.current_node = nxt
                assignee = _assignee_for(db, nxt, x.student_id)
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
        cnt = 0
        for x in rows:
            b = db.get(FundingBatch, int(x.batch_id))
            days = (b.publicity_days if b and b.publicity_days is not None else 5)
            if x.publicity_at + timedelta(days=days) <= now:
                _grant_one(db, x)
                cnt += 1
        db.commit()
        return {"count": cnt}


def confirm_publicity(app_id, user) -> dict:
    with session() as db:
        x, s = _load(db, app_id)
        _scope_or_403(db, x.student_id, user)
        if x.status != "PUBLICITY":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请不在公示状态")
        _grant_one(db, x)
        db.commit()
        db.refresh(x)
        return _app_row(x, user, s)


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
        out = []
        for x in rows:
            s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            out.append(_app_row(x, user, s))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def get_application(app_id, user) -> dict:
    with session() as db:
        x, s = _load(db, app_id)
        _scope_or_403(db, x.student_id, user)
        d = _app_row(x, user, s)
        d["checkSnapshot"] = json.loads(x.check_snapshot_json) if x.check_snapshot_json else {}
        return d
