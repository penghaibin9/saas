"""13A-P3 奖助闭环（统一资助抽象，V1 只启用 SCHOLARSHIP/GRANT）。

11 态：DRAFT/SUBMITTED/COUNSELOR_REVIEW/COLLEGE_REVIEW/SCHOOL_REVIEW/PUBLICITY/
GRANTED/REJECTED/RETURNED/CANCELLED/ARCHIVED（勤工 ON_POST/TERMINATED、贷款 P2 后置）。
资格硬校验链（受理即拦）：奖学金查学籍/处分未解除/成绩挂科；助学金查困难库在库。
管理端 apply 直达 COUNSELOR_REVIEW 并建 workflow；SCHOOL_REVIEW 通过→PUBLICITY；
公示期满(可配 0 天)→GRANTED，写 StageEvent 进 360。
"""

from app.core.optimistic_lock import atomic_claim_version

import json
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import and_, case, exists, func, or_, select, union_all

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.core.tenant_scoped import tenant_get
from app.core.pagination import normalize_page
from app.services.db_service import _iso, _tid, session

PROJECT_TYPES = {"SCHOLARSHIP", "GRANT", "WORK_STUDY", "LOAN",
                 "TUITION_REDUCTION", "TEMPORARY_AID", "GREEN_CHANNEL"}
V1_TYPES = {"SCHOLARSHIP", "GRANT"}  # 本阶段只做这两类
PROJECT_STATUSES = {"ENABLED", "DISABLED"}
FUND_NODES = ["COUNSELOR_REVIEW", "COLLEGE_REVIEW", "SCHOOL_REVIEW"]
_TERMINAL = {"GRANTED", "REJECTED", "CANCELLED", "ARCHIVED"}
_AMOUNT_ROLES = {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN", "FUNDING_TEACHER"}

_DEFAULT_ELIGIBILITY = {
    "version": "2026.1",
    "SCHOLARSHIP": {
        "requireActiveStatus": True,
        "requireNoActiveDiscipline": True,
        "requireNoFailedGrade": True,
    },
    "GRANT": {
        "requireDifficultLibrary": True,
        "allowedAidLevels": [],
    },
}

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
    from app.services.affairs_assignee_service import require_assignee_id
    return require_assignee_id(db, node, student_id=student_id)


def _open_wf(db, app_id, ptype, applicant_id, title, first_node, assignee_id):
    from app.models import WorkflowInstance, WorkflowTask
    from app.services.runtime_preset_install_service import ensure_workflow_enabled
    ensure_workflow_enabled(db, _tid(), _wf_code(ptype))
    if int(assignee_id or 0) <= 0:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", f"未配置受理人：{first_node}")
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
    if int(assignee_id or 0) <= 0:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", "资助待办没有具体受理人")
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
    s = tenant_get(db, StudentProfile, int(student_id)) if student_id else None
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

def _eligibility_rules(project_type: str, project=None) -> dict:
    project_type = str(project_type or "").upper()
    configured = _DEFAULT_ELIGIBILITY
    source = "PACKAGE_DEFAULT"
    chain = []
    try:
        from app.services import effective_config_service
        resolved = effective_config_service.resolve("AFFAIRS_FUNDING_ELIGIBILITY_JSON")
        if isinstance(resolved.get("value"), dict):
            configured = resolved["value"]
            source = resolved.get("sourceLayer") or "PACKAGE_DEFAULT"
            chain = resolved.get("chain") or []
    except Exception:
        pass
    defaults = dict(_DEFAULT_ELIGIBILITY.get(project_type) or {})
    rules = dict(defaults)
    configured_rules = configured.get(project_type) if isinstance(configured, dict) else None
    if isinstance(configured_rules, dict):
        rules.update({key: value for key, value in configured_rules.items() if key in defaults})
    project_rules = {}
    if project is not None and getattr(project, "condition_json", None):
        try:
            parsed = json.loads(project.condition_json)
            if isinstance(parsed, dict):
                candidate = parsed.get("eligibility") or parsed.get(project_type) or parsed
                if isinstance(candidate, dict):
                    project_rules = {key: value for key, value in candidate.items() if key in defaults}
                    rules.update(project_rules)
        except (TypeError, ValueError, json.JSONDecodeError):
            project_rules = {}
    version = str((configured or {}).get("version") or _DEFAULT_ELIGIBILITY["version"])
    return {
        "version": version, "source": source, "sourceChain": chain, "rules": rules,
        "projectId": str(getattr(project, "id", "") or ""),
        "projectOverrides": project_rules,
    }


def _check_scholarship(db, student_id, project=None) -> dict:
    """奖学金资格按学校有效配置与项目覆盖执行，并冻结规则版本和事实快照。"""
    from app.models import (AcademicGrade, AcademicStudent, CsDiscipline,
                            CsServiceStudent, StudentProfile)
    contract = _eligibility_rules("SCHOLARSHIP", project)
    rules = contract["rules"]
    s = db.get(StudentProfile, int(student_id))
    status_fact = bool(s and (s.student_status in (None, "NORMAL", "在籍", "ACTIVE")))
    discipline_fact = True
    cs = db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == _tid(), CsServiceStudent.student_id == int(student_id),
        CsServiceStudent.is_deleted.is_(False))).first()
    if cs:
        exists = db.scalar(select(CsDiscipline.id).where(
            CsDiscipline.tenant_id == _tid(), CsDiscipline.cs_student_id == cs.id,
            CsDiscipline.record_status == "ACTIVE", CsDiscipline.is_deleted.is_(False)).limit(1))
        discipline_fact = exists is None
    grade_fact = True
    acad = db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == int(student_id),
        AcademicStudent.is_deleted.is_(False))).first()
    if acad:
        failed = db.scalar(select(AcademicGrade.id).where(
            AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == acad.id,
            AcademicGrade.pass_status == "FAILED", AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False)).limit(1))
        grade_fact = failed is None
    status_ok = status_fact or not bool(rules.get("requireActiveStatus", True))
    discipline_ok = discipline_fact or not bool(rules.get("requireNoActiveDiscipline", True))
    grade_ok = grade_fact or not bool(rules.get("requireNoFailedGrade", True))
    return {
        "type": "SCHOLARSHIP", "statusOk": status_ok, "disciplineOk": discipline_ok,
        "gradeOk": grade_ok, "facts": {
            "activeStatus": status_fact, "noActiveDiscipline": discipline_fact,
            "noFailedGrade": grade_fact,
        },
        "ruleVersion": contract["version"], "ruleSource": contract["source"],
        "ruleSourceChain": contract["sourceChain"], "projectId": contract["projectId"],
        "projectOverrides": contract["projectOverrides"], "rules": rules,
        "evaluatedAt": datetime.utcnow().isoformat(),
        "ok": status_ok and discipline_ok and grade_ok,
    }


def _check_grant(db, student_id, project=None) -> dict:
    """助学金资格按困难库事实、允许等级和项目覆盖执行，并冻结规则版本。"""
    from app.services.affairs_aid_service import is_in_difficult_library
    contract = _eligibility_rules("GRANT", project)
    rules = contract["rules"]
    level = is_in_difficult_library(db, student_id)
    in_library = bool(level)
    allowed_levels = [str(value) for value in (rules.get("allowedAidLevels") or []) if str(value)]
    library_ok = in_library or not bool(rules.get("requireDifficultLibrary", True))
    level_ok = not allowed_levels or str(level or "") in allowed_levels
    return {
        "type": "GRANT", "aidLevel": level, "inDifficultLibrary": in_library,
        "aidLevelAllowed": level_ok, "ruleVersion": contract["version"],
        "ruleSource": contract["source"], "ruleSourceChain": contract["sourceChain"],
        "projectId": contract["projectId"], "projectOverrides": contract["projectOverrides"],
        "rules": rules, "evaluatedAt": datetime.utcnow().isoformat(),
        "ok": library_ok and level_ok,
    }


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


def _amount_policy(project) -> dict:
    """金额建议的唯一读投影。

    项目 amount 有值时是固定金额；区间策略保存在项目 condition_json.amountPolicy，
    与资格规则共用项目版本快照，不增加第二个金额真值字段。
    """
    if getattr(project, "amount", None) is not None:
        fixed = Decimal(str(project.amount)).quantize(Decimal("0.01"))
        return {"mode": "FIXED", "fixedAmount": format(fixed, ".2f"),
                "suggestedAmount": format(fixed, ".2f"), "source": "PROJECT_STANDARD"}
    parsed = {}
    try:
        parsed = json.loads(project.condition_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed = {}
    raw = parsed.get("amountPolicy") if isinstance(parsed, dict) else None
    if not isinstance(raw, dict) or str(raw.get("mode") or "").upper() != "RANGE":
        return {"mode": "OPTIONAL", "suggestedAmount": None, "source": "MANUAL"}
    try:
        minimum = Decimal(str(raw.get("minAmount"))).quantize(Decimal("0.01"))
        maximum = Decimal(str(raw.get("maxAmount"))).quantize(Decimal("0.01"))
        suggested = Decimal(str(raw.get("suggestedAmount", minimum))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AppException("DATA_CONFLICT", "资助项目金额区间配置无效，请先修正项目") from exc
    if minimum < 0 or maximum < minimum or not minimum <= suggested <= maximum:
        raise AppException("DATA_CONFLICT", "资助项目金额区间配置无效，请先修正项目")
    return {"mode": "RANGE", "minAmount": format(minimum, ".2f"),
            "maxAmount": format(maximum, ".2f"), "suggestedAmount": format(suggested, ".2f"),
            "source": "PROJECT_RANGE"}


def _validated_amount(project, value):
    policy = _amount_policy(project)
    if value in (None, ""):
        value = policy.get("suggestedAmount")
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "申请金额格式不正确") from exc
    if amount < 0:
        raise AppException("VALIDATION_ERROR", "申请金额不能为负数")
    if policy["mode"] == "FIXED" and amount != Decimal(policy["fixedAmount"]):
        raise AppException("DATA_CONFLICT", f"本项目固定金额为 {policy['fixedAmount']} 元")
    if policy["mode"] == "RANGE":
        minimum, maximum = Decimal(policy["minAmount"]), Decimal(policy["maxAmount"])
        if not minimum <= amount <= maximum:
            raise AppException("VALIDATION_ERROR", f"申请金额应在 {policy['minAmount']}-{policy['maxAmount']} 元之间")
    return amount


def preflight(batch_id, student_id, user) -> dict:
    """调用正式资格函数的只读预检；apply() 仍会在同一事务内重新校验。"""
    sid = _req_int(student_id, "学生")
    with session() as db:
        from app.models import FundingBatch, FundingProject, StudentProfile
        student = db.get(StudentProfile, sid)
        if not student or student.is_deleted or student.tenant_id != _tid():
            raise not_found("学生不存在或不在数据范围内")
        _scope_or_403(db, sid, user)
        batch = db.get(FundingBatch, _req_int(batch_id, "批次"))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("资助批次不存在")
        project = require_application_batch(db, batch)
        project_type = str(batch.project_type or project.project_type or "").upper()
        snap = (_check_grant(db, sid, project) if project_type == "GRANT"
                else _check_scholarship(db, sid, project))
        return {
            "eligible": bool(snap.get("ok")),
            "message": "当前资格预检通过" if snap.get("ok") else _reject_reason(snap),
            "ruleVersion": snap.get("ruleVersion"), "ruleSource": snap.get("ruleSource"),
            "evaluatedAt": snap.get("evaluatedAt"), "checkSnapshot": snap,
            "amountPolicy": _amount_policy(project),
            "submitWillRevalidate": True,
        }


# ── 序列化 ──

def _amount_view(amount, user):
    """金额脱敏：授权角色见真实值，其余见区间。"""
    if amount is None:
        return None
    role = (user or {}).get("currentRoleCode")
    if role in _AMOUNT_ROLES:
        return format(amount, ".2f")
    n = amount
    if n < 2000:
        return "2000以下"
    if n < 5000:
        return "2000-5000"
    return "5000以上"


def _project_row(p, user=None, *, batch_count=0, open_batch_count=0) -> dict:
    contract = _eligibility_rules(p.project_type, p)
    allowed_actions = []
    if user is not None:
        from app.core.permissions import has_permission
        if has_permission(user, "studentAffairs.funding.project.manage"):
            allowed_actions = ["DISABLE" if p.status == "ENABLED" else "ENABLE"]
    return {"projectId": str(p.id), "projectType": p.project_type, "projectName": p.project_name,
            "amount": format(p.amount, ".2f") if p.amount is not None else None,
            "amountPolicy": _amount_policy(p), "quota": p.quota, "status": p.status,
            "eligibilityRules": contract.get("rules") or {},
            "eligibilityRuleVersion": contract.get("version"),
            "batchCount": int(batch_count or 0), "openBatchCount": int(open_batch_count or 0),
            "allowedActions": allowed_actions, "version": int(p.version or 0)}


def _batch_intake_state(b, project_status="ENABLED") -> str:
    if b.status == "DRAFT":
        return "DRAFT"
    if b.status != "OPEN" or project_status != "ENABLED":
        return "CLOSED"
    now = datetime.utcnow()
    if b.apply_start and b.apply_start > now:
        return "UPCOMING"
    if b.apply_end and b.apply_end < now:
        return "ENDED"
    return "OPEN"


def _batch_row(b, project=None, user=None, *, application_count=0) -> dict:
    project_status = str(getattr(project, "status", "") or "")
    allowed_actions = []
    if user is not None:
        from app.core.permissions import has_permission
        if has_permission(user, "studentAffairs.funding.project.manage"):
            if b.status == "DRAFT":
                allowed_actions.append("PUBLISH")
            elif b.status == "OPEN":
                allowed_actions.append("CLOSE")
    return {"batchId": str(b.id), "projectId": str(b.project_id), "projectType": b.project_type,
            "projectName": str(getattr(project, "project_name", "") or ""),
            "projectStatus": project_status, "projectAmount": (
                format(project.amount, ".2f") if project is not None and project.amount is not None else None),
            "schoolYear": b.year_code, "applyStart": _iso(b.apply_start), "applyEnd": _iso(b.apply_end),
            "publicityDays": b.publicity_days if b.publicity_days is not None else 5,
            "quota": b.quota,
            "amountBudget": format(b.amount_budget, ".2f") if b.amount_budget is not None else None,
            "reservedQuota": int(b.reserved_quota or 0),
            "reservedAmount": format(b.reserved_amount or 0, ".2f"),
            "applicationCount": int(application_count or 0),
            "status": b.status, "intakeState": _batch_intake_state(b, project_status),
            "allowedActions": allowed_actions, "version": int(b.version or 0)}


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
    project_type = str(body.projectType or "").upper()
    project_name = str(body.projectName or "").strip()
    if not project_name:
        raise AppException("VALIDATION_ERROR", "项目名称不能为空")
    if project_type not in PROJECT_TYPES:
        raise AppException("VALIDATION_ERROR", "项目类型非法")
    if project_type not in V1_TYPES:
        raise AppException("DATA_CONFLICT", "该资助类型 V1 暂未开放（仅奖学金/助学金）")
    try:
        amount = Decimal(str(body.amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "请配置有效的项目标准金额") from exc
    if amount <= 0:
        raise AppException("VALIDATION_ERROR", "项目标准金额必须大于0")
    quota = body.quota
    if quota is not None and (int(quota) < 1 or int(quota) > 100000):
        raise AppException("VALIDATION_ERROR", "项目默认名额应为1-100000")
    with session() as db:
        from app.models import FundingProject
        p = FundingProject(tenant_id=_tid(), project_name=project_name, project_type=project_type,
                           amount=amount, quota=quota,
                           condition_json=json.dumps(body.conditions or {}, ensure_ascii=False),
                           status="ENABLED")
        db.add(p)
        db.flush()
        _audit(db, p.id, "PROJECT_CREATE", project_type)
        db.commit()
        _drain_message_outbox()
        db.refresh(p)
        return _project_row(p, user)


def list_projects(user, project_type=None, status=None, page=1, page_size=20, keyword=None):
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 200))
    with session() as db:
        from app.models import FundingBatch, FundingProject
        base = [FundingProject.tenant_id == _tid(), FundingProject.is_deleted.is_(False)]
        value = str(keyword or "").strip()
        if value:
            base.append(FundingProject.project_name.contains(value, autoescape=True))
        conds = list(base)
        if project_type:
            conds.append(FundingProject.project_type == project_type)
        if status:
            conds.append(FundingProject.status == status)
        total = int(db.scalar(select(func.count()).select_from(FundingProject).where(*conds)) or 0)
        rows = db.scalars(select(FundingProject).where(*conds).order_by(
            FundingProject.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        ids = {int(row.id) for row in rows}
        batch_counts = {}
        open_counts = {}
        if ids:
            for project_id, batch_status, count in db.execute(select(
                    FundingBatch.project_id, FundingBatch.status, func.count(FundingBatch.id)).where(
                    FundingBatch.tenant_id == _tid(), FundingBatch.project_id.in_(ids),
                    FundingBatch.is_deleted.is_(False)).group_by(
                    FundingBatch.project_id, FundingBatch.status)).all():
                batch_counts[int(project_id)] = batch_counts.get(int(project_id), 0) + int(count or 0)
                if batch_status == "OPEN":
                    open_counts[int(project_id)] = int(count or 0)
        status_counts = {str(key or ""): int(count or 0) for key, count in db.execute(
            select(FundingProject.status, func.count(FundingProject.id)).where(*base).group_by(
                FundingProject.status)).all()}
        type_counts = {str(key or ""): int(count or 0) for key, count in db.execute(
            select(FundingProject.project_type, func.count(FundingProject.id)).where(*base).group_by(
                FundingProject.project_type)).all()}
        return [
            _project_row(row, user, batch_count=batch_counts.get(int(row.id), 0),
                         open_batch_count=open_counts.get(int(row.id), 0))
            for row in rows
        ], total, {"all": sum(status_counts.values()), "byStatus": status_counts, "byType": type_counts}


def set_project_status(project_id, target_status, expected_version, user) -> dict:
    target = str(target_status or "").upper()
    if target not in PROJECT_STATUSES:
        raise AppException("VALIDATION_ERROR", "项目状态仅支持启用或停用")
    with session() as db:
        from app.models import FundingBatch, FundingProject
        project = db.get(FundingProject, _req_int(project_id, "项目"))
        if not project or project.is_deleted or project.tenant_id != _tid():
            raise not_found("资助项目不存在")
        check_version(project.version, expected_version)
        if project.status == target:
            return _project_row(project, user)
        atomic_claim_version(db, project, expected_version)
        project.status = target
        project.version += 1
        _audit(db, project.id, "PROJECT_ENABLE" if target == "ENABLED" else "PROJECT_DISABLE",
               "启用项目" if target == "ENABLED" else "停用项目；不影响既有申请继续办理")
        db.commit()
        _drain_message_outbox()
        db.refresh(project)
        counts = db.execute(select(FundingBatch.status, func.count(FundingBatch.id)).where(
            FundingBatch.tenant_id == _tid(), FundingBatch.project_id == project.id,
            FundingBatch.is_deleted.is_(False)).group_by(FundingBatch.status)).all()
        batch_count = sum(int(count or 0) for _, count in counts)
        open_count = sum(int(count or 0) for status, count in counts if status == "OPEN")
        return _project_row(project, user, batch_count=batch_count, open_batch_count=open_count)


def create_batch(body, user) -> dict:
    from app.services.affairs_publicity_rules import publicity_days, school_year, validate_dates
    body.schoolYear = school_year(getattr(body, "schoolYear", None))
    body.publicityDays = publicity_days(getattr(body, "publicityDays", None))
    validate_dates(_parse_dt, body)
    quota = getattr(body, "quota", None)
    if quota not in (None, ""):
        try:
            quota = int(quota)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "资助名额必须为整数") from exc
        if quota < 1 or quota > 100000:
            raise AppException("VALIDATION_ERROR", "资助名额应为1-100000")
        body.quota = quota
    with session() as db:
        from app.models import FundingBatch, FundingProject
        p = db.get(FundingProject, int(body.projectId))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("资助项目不存在")
        publish = bool(getattr(body, "publish", False))
        if p.project_type not in V1_TYPES:
            raise AppException("DATA_CONFLICT", "该项目类型尚未接入奖学金/助学金申请流程")
        if publish and p.status != "ENABLED":
            raise AppException("DATA_CONFLICT", "资助项目已停用，只能先保存草稿")
        if publish and (p.amount is None or Decimal(str(p.amount)) <= 0):
            raise AppException("DATA_CONFLICT", "发布前请先配置有效的项目标准金额")
        batch_quota = body.quota if body.quota not in (None, "") else p.quota
        amount_budget = (Decimal(str(p.amount)) * int(batch_quota)
                         if p.amount is not None and batch_quota is not None else None)
        b = FundingBatch(tenant_id=_tid(), project_id=p.id, project_type=p.project_type,
                         year_code=body.schoolYear, apply_start=_parse_dt(body.applyStart),
                         apply_end=_parse_dt(body.applyEnd),
                         publicity_days=(body.publicityDays if body.publicityDays is not None else 5),
                         quota=batch_quota, amount_budget=amount_budget,
                         status=("OPEN" if publish else "DRAFT"))
        db.add(b)
        db.flush()
        _audit(db, b.id, "BATCH_CREATE", f"publish={publish}")
        db.commit()
        _drain_message_outbox()
        db.refresh(b)
        return _batch_row(b, p, user)


def list_batches(user, project_id=None, status=None, page=1, page_size=20, keyword=None):
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 200))
    with session() as db:
        from app.models import FundingApplication, FundingBatch, FundingProject
        base = [FundingBatch.tenant_id == _tid(), FundingBatch.is_deleted.is_(False),
                FundingProject.id == FundingBatch.project_id,
                FundingProject.tenant_id == _tid(), FundingProject.is_deleted.is_(False)]
        value = str(keyword or "").strip()
        if value:
            base.append(or_(FundingProject.project_name.contains(value, autoescape=True),
                            FundingBatch.year_code.contains(value, autoescape=True)))
        conds = list(base)
        if project_id:
            conds.append(FundingBatch.project_id == _req_int(project_id, "项目"))
        if status:
            conds.append(FundingBatch.status == status)
        total = int(db.scalar(select(func.count()).select_from(FundingBatch).join(
            FundingProject, FundingProject.id == FundingBatch.project_id).where(*conds)) or 0)
        rows = db.scalars(select(FundingBatch).join(
            FundingProject, FundingProject.id == FundingBatch.project_id).where(*conds).order_by(
            FundingBatch.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        project_ids = {row.project_id for row in rows}
        projects = {p.id: p for p in db.scalars(select(FundingProject).where(
            FundingProject.tenant_id == _tid(), FundingProject.id.in_(project_ids),
            FundingProject.is_deleted.is_(False))).all()} if project_ids else {}
        batch_ids = {int(row.id) for row in rows}
        application_counts = {int(batch_id): int(count or 0) for batch_id, count in db.execute(select(
            FundingApplication.batch_id, func.count(FundingApplication.id)).where(
            FundingApplication.tenant_id == _tid(), FundingApplication.batch_id.in_(batch_ids or {-1}),
            FundingApplication.is_deleted.is_(False)).group_by(FundingApplication.batch_id)).all()}
        summary_conds = list(base)
        if project_id:
            summary_conds.append(FundingBatch.project_id == _req_int(project_id, "项目"))
        status_counts = {str(key or ""): int(count or 0) for key, count in db.execute(select(
            FundingBatch.status, func.count(FundingBatch.id)).select_from(FundingBatch).join(
            FundingProject, FundingProject.id == FundingBatch.project_id).where(*summary_conds).group_by(
            FundingBatch.status)).all()}
        now = datetime.utcnow()
        available_now = int(db.scalar(select(func.count()).select_from(FundingBatch).join(
            FundingProject, FundingProject.id == FundingBatch.project_id).where(
            *summary_conds, FundingBatch.status == "OPEN", FundingProject.status == "ENABLED",
            or_(FundingBatch.apply_start.is_(None), FundingBatch.apply_start <= now),
            or_(FundingBatch.apply_end.is_(None), FundingBatch.apply_end >= now))) or 0)
        return [
            _batch_row(row, projects.get(row.project_id), user,
                       application_count=application_counts.get(int(row.id), 0))
            for row in rows
        ], total, {"all": sum(status_counts.values()), "byStatus": status_counts,
                   "availableNow": available_now}


def act_batch(batch_id, action, expected_version, user) -> dict:
    command = str(action or "").upper()
    if command not in {"PUBLISH", "CLOSE"}:
        raise AppException("VALIDATION_ERROR", "批次操作仅支持发布或关闭申请")
    with session() as db:
        from app.models import FundingApplication, FundingBatch, FundingProject
        batch = db.get(FundingBatch, _req_int(batch_id, "批次"))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("资助批次不存在")
        project = db.get(FundingProject, int(batch.project_id)) if batch.project_id else None
        if not project or project.is_deleted or project.tenant_id != _tid():
            raise AppException("DATA_CONFLICT", "所属资助项目不存在或已失效")
        check_version(batch.version, expected_version)
        if command == "PUBLISH":
            if batch.status != "DRAFT":
                raise AppException("DATA_CONFLICT", "仅草稿批次可以发布，请刷新核对状态")
            if project.status != "ENABLED":
                raise AppException("DATA_CONFLICT", "资助项目已停用，启用项目后才能发布批次")
            if project.project_type not in V1_TYPES or batch.project_type != project.project_type:
                raise AppException("DATA_CONFLICT", "批次与项目类型不一致或尚未开放")
            if project.amount is None or Decimal(str(project.amount)) <= 0:
                raise AppException("DATA_CONFLICT", "发布前请先配置有效的项目标准金额")
            if batch.apply_end and batch.apply_end < datetime.utcnow():
                raise AppException("DATA_CONFLICT", "申请截止时间已过，请新建正确申请窗口的批次")
            target = "OPEN"
        else:
            if batch.status != "OPEN":
                raise AppException("DATA_CONFLICT", "仅开放中的批次可以关闭申请")
            target = "CLOSED"
        atomic_claim_version(db, batch, expected_version)
        if command == "PUBLISH" and batch.amount_budget is None and batch.quota is not None:
            batch.amount_budget = Decimal(str(project.amount)) * int(batch.quota)
        batch.status = target
        batch.version += 1
        _audit(db, batch.id, "BATCH_PUBLISH" if command == "PUBLISH" else "BATCH_CLOSE",
               "发布批次并按申请窗口开放" if command == "PUBLISH" else "关闭新申请；既有申请继续办理")
        db.commit()
        _drain_message_outbox()
        db.refresh(batch)
        application_count = int(db.scalar(select(func.count()).select_from(FundingApplication).where(
            FundingApplication.tenant_id == _tid(), FundingApplication.batch_id == batch.id,
            FundingApplication.is_deleted.is_(False))) or 0)
        return _batch_row(batch, project, user, application_count=application_count)


# ═══════════ 申请（含资格硬校验）═══════════

def require_application_batch(db, batch):
    """Validate new applications; existing records retain their own state machine."""
    from app.core.timeutil import utc_now_naive
    from app.models import FundingProject
    now = utc_now_naive()
    if batch.status != "OPEN":
        raise AppException("DATA_CONFLICT", "批次未开放或已截止")
    if batch.apply_start and batch.apply_start > now:
        raise AppException("DATA_CONFLICT", "该批次尚未开始申请，请在开放后提交")
    if batch.apply_end and batch.apply_end < now:
        raise AppException("DATA_CONFLICT", "该批次申请已截止")
    project = db.get(FundingProject, int(batch.project_id)) if batch.project_id else None
    if not project or project.is_deleted or project.tenant_id != _tid():
        raise not_found("资助项目不存在")
    if project.status != "ENABLED":
        raise AppException("DATA_CONFLICT", "该资助项目已停用，暂不能新建申请")
    if batch.project_type not in V1_TYPES or batch.project_type != project.project_type:
        raise AppException("DATA_CONFLICT", "该批次暂不支持奖学金或助学金申请，请联系学校核对项目")
    return project


def apply(body, user, *, skip_scope_check: bool = False) -> dict:
    student_id = _req_int(getattr(body, "studentId", None), "学生")
    with session() as db:
        from app.models import FundingApplication, FundingBatch, FundingProject, StudentProfile
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
        project = require_application_batch(db, b)
        # 同批次重复申请 → 409
        dup = db.scalars(select(FundingApplication).where(
            FundingApplication.tenant_id == _tid(), FundingApplication.batch_id == b.id,
            FundingApplication.student_id == student_id, FundingApplication.is_deleted.is_(False))).first()
        if dup and dup.status not in _TERMINAL:
            raise AppException("DATA_CONFLICT", "该生在本批次已有在途申请，不可重复提交")
        project_type = str(b.project_type or project.project_type or "").upper()
        # 资格硬校验链：学校有效配置 + 项目条件覆盖，并将规则版本冻结进申请快照。
        snap = (_check_grant(db, student_id, project) if project_type == "GRANT"
                else _check_scholarship(db, student_id, project))
        if not snap["ok"]:
            raise AppException("DATA_CONFLICT", _reject_reason(snap))
        amount = _validated_amount(project, getattr(body, "amount", None))
        first = FUND_NODES[0]
        x = FundingApplication(tenant_id=_tid(), batch_id=b.id, student_id=student_id,
                               apply_source=(body.applySource or "SELF"), project_type=project_type,
                               amount=amount, requested_amount=amount, statement=(body.statement or ""),
                               check_snapshot_json=json.dumps(snap, ensure_ascii=False), status=first)
        from app.services.affairs_funding_authority_service import freeze_application_amount
        amount_snapshot = freeze_application_amount(db, x)
        db.add(x)
        db.flush()
        _audit(db, x.id, "AMOUNT_RULE_FROZEN", f"project={amount_snapshot['projectId']};amount={amount_snapshot['amount']}")
        assignee = _assignee_for(db, first, student_id)
        inst = _open_wf(db, x.id, project_type, student_id, f"{s.real_name} {project_type}", first, assignee)
        x.workflow_instance_id = inst.id
        _todo_upsert(db, x.id, assignee, student_id, f"资助申请待审：{s.real_name}")
        _audit(db, x.id, "APPLY", f"{project_type};rule={snap.get('ruleVersion')};source={snap.get('ruleSource')}")
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
    s = tenant_get(db, StudentProfile, int(x.student_id)) if x.student_id else None
    return x, s


def _act_task(db, x, action, reason=""):
    from app.models import WorkflowInstance
    inst = tenant_get(db, WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
    task = _cur_task(db, inst.id, x.status) if inst else None
    if task:
        task.status, task.acted_at, task.action_reason = action, datetime.utcnow(), reason
        task.version += 1
    return inst


def review(app_id, user, action, reason="", expected_version=None) -> dict:
    action = (action or "").upper()
    with session() as db:
        from app.models import WorkflowTask
        x, s = _load(db, app_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in FUND_NODES:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请当前状态不可评审，请刷新")
        atomic_claim_version(db, x, expected_version)
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
        inst = tenant_get(db, WorkflowInstance, int(x.workflow_instance_id))
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
            FundingApplication.is_deleted.is_(False),
        ).order_by(FundingApplication.id).limit(200).with_for_update(skip_locked=True)).all()
        pending = _pending_appeal_ids(db, [row.id for row in rows])
        batch_ids = {int(row.batch_id) for row in rows if row.batch_id}
        batches = {
            int(batch.id): batch
            for batch in db.scalars(select(FundingBatch).where(
                FundingBatch.tenant_id == _tid(),
                FundingBatch.id.in_(batch_ids) if batch_ids else FundingBatch.id == -1,
                FundingBatch.is_deleted.is_(False),
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
            _grant_one(db, row)
            confirmed += 1
        db.commit()
    _drain_message_outbox()
    return {"count": confirmed, "skippedAppeal": skipped, "invalidBatch": invalid}


def publicity_window(application, batch, has_pending_appeal=False) -> dict:
    valid = bool(batch and not batch.is_deleted and application.publicity_at)
    end = (application.publicity_at + timedelta(days=max(1, int(batch.publicity_days if batch.publicity_days is not None else 5)))) if valid else None
    ready = bool(application.status == 'PUBLICITY' and end and end <= datetime.utcnow() and not has_pending_appeal)
    hint = ('公示批次或起始时间缺失，请核查' if not valid else
            '申诉待复核' if has_pending_appeal else '公示期尚未结束' if end > datetime.utcnow() else '可确认获资助')
    return {'publicityEnd': _iso(end), 'publicityReady': ready, 'publicityHint': hint}


def confirm_publicity(app_id, user, expected_version=None) -> dict:
    with session() as db:
        x, s = _load(db, app_id)
        _scope_or_403(db, x.student_id, user)
        if x.status != "PUBLICITY":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请不在公示状态")
        atomic_claim_version(db, x, expected_version)
        _assert_no_open_appeal(db, x.id)
        from app.models import FundingBatch
        batch = tenant_get(db, FundingBatch, int(x.batch_id))
        window = publicity_window(x, batch)
        if not window['publicityReady']:
            raise AppException("DATA_CONFLICT", window['publicityHint'])
        _grant_one(db, x)
        db.commit()
        _drain_message_outbox()
        db.refresh(x)
        return _app_row(x, user, s, has_pending_appeal=False)



# ═══════════ 查询 ═══════════

def _pending_conditions(db, user):
    from app.core.affairs_security import build_affairs_context
    from app.core.permissions import has_permission
    from app.models import FundingApplication, WorkflowTask
    from app.services.affairs_funding_scan_guard import _REVIEW_SCOPE

    if not has_permission(user, "studentAffairs.funding.approve"):
        return [FundingApplication.id == -1]
    scope = build_affairs_context(user, db).scope_type
    nodes = [node for node, required_scope in _REVIEW_SCOPE.items() if required_scope == scope]
    uid = _uid_int(user)
    latest_owner = select(WorkflowTask.assignee_id).where(
        WorkflowTask.tenant_id == _tid(),
        WorkflowTask.instance_id == FundingApplication.workflow_instance_id,
        WorkflowTask.node_code == FundingApplication.status,
        WorkflowTask.status == "PENDING", WorkflowTask.is_deleted.is_(False),
    ).order_by(WorkflowTask.id.desc()).limit(1).correlate(FundingApplication).scalar_subquery()
    return [FundingApplication.status.in_(nodes), FundingApplication.workflow_instance_id > 0,
            latest_owner == uid if uid > 0 else FundingApplication.id == -1]


def list_applications(user, batch_id=None, project_type=None, status=None, page=1, page_size=20,
                      student_id=None, *, pending_only=False, keyword=None):
    from app.models import FundingApplication, StudentProfile, FundingBatch
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.services.affairs_list_stats import status_counts_by_column
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        base_conds = [FundingApplication.tenant_id == _tid(), FundingApplication.is_deleted.is_(False)]
        if pending_only:
            base_conds.extend(_pending_conditions(db, user))
        if keyword and str(keyword).strip():
            from sqlalchemy import or_
            value = str(keyword).strip()
            base_conds.append(or_(StudentProfile.real_name.contains(value, autoescape=True),
                                  StudentProfile.student_no.contains(value, autoescape=True)))
        if batch_id:
            base_conds.append(FundingApplication.batch_id == int(batch_id))
        if project_type:
            base_conds.append(FundingApplication.project_type == project_type)
        if student_id:
            try:
                base_conds.append(FundingApplication.student_id == int(student_id))
            except (TypeError, ValueError):
                return [], 0, {"ALL": 0}
        conds = list(base_conds)
        if status:
            statuses = [item.strip() for item in status.split(",") if item.strip()]
            conds.append(FundingApplication.status.in_(statuses))
        student_conds = [
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ]
        status_counts = status_counts_by_column(
            db, FundingApplication, FundingApplication.status, [*base_conds, *student_conds],
            join_student=StudentProfile, allowed_class_ids=allowed,
        )
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        page, page_size = normalize_page(page, page_size)
        total = int(db.scalar(select(func.count()).select_from(FundingApplication)
                              .join(StudentProfile, StudentProfile.id == FundingApplication.student_id)
                              .where(*conds, *student_conds)) or 0)
        rows = db.scalars(select(FundingApplication)
                          .join(StudentProfile, StudentProfile.id == FundingApplication.student_id)
                          .where(*conds, *student_conds).order_by(FundingApplication.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        sids = {int(x.student_id) for x in rows if x.student_id}
        students = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_(sids))).all()} if sids else {}
        pending = _pending_appeal_ids(db, [x.id for x in rows])
        batch_ids = {x.batch_id for x in rows if x.status == 'PUBLICITY'}
        batches = {b.id: b for b in db.scalars(select(FundingBatch).where(
            FundingBatch.tenant_id == _tid(), FundingBatch.id.in_(batch_ids))).all()} if batch_ids else {}
        from app.core.permissions import has_permission
        can_confirm = has_permission(user, 'studentAffairs.funding.publicity.manage')
        windows = {x.id: publicity_window(x, batches.get(x.batch_id), x.id in pending)
                   for x in rows if x.status == 'PUBLICITY'}
        return [
            {**_app_row(x, user, students.get(int(x.student_id)) if x.student_id else None,
                     has_pending_appeal=int(x.id) in pending),
             **({**windows[x.id], 'allowedActions': ['PUBLICITY_CONFIRM'] if can_confirm and windows[x.id]['publicityReady'] else []} if x.id in windows else {}),
             **({"allowedActions": ["APPROVE", "RETURN", "REJECT"]} if pending_only else {})}
            for x in rows
        ], total, status_counts


def _stats_money(value) -> str:
    return format(Decimal(str(value or 0)).quantize(Decimal("0.01")), ".2f")


def _stats_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _mask_stats_name(value: str | None) -> str:
    name = (value or "").strip()
    if not name:
        return "—"
    if len(name) == 1:
        return "*"
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


def _mask_stats_student_no(value: str | None) -> str:
    """统计下钻即使遇到历史短学号也不回传原值。"""
    number = (value or "").strip()
    if not number:
        return "—"
    if len(number) <= 2:
        return "*" * len(number)
    if len(number) <= 4:
        return number[0] + "*" * (len(number) - 2) + number[-1]
    from app.services.stats_service import _mask_no
    return _mask_no(number)


def _stats_scope(db, user):
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids

    allowed, scope = _allowed_class_ids(db, user)
    student_conds = [
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ]
    if allowed is not None:
        student_conds.append(StudentProfile.class_id.in_(allowed or {-1}))
    return allowed, scope, student_conds


def funding_stats(user) -> dict:
    """资助统计：跨奖助、勤工、贷款与减免台账去重聚合，范围与业务列表一致。"""
    from app.models import (
        AidApply, FeeReduction, FundingApplication, FundingBatch, FundingDisbursement,
        StudentLoan, StudentProfile, WorkStudyRecord,
    )

    with session() as db:
        _allowed, scope, student_conds = _stats_scope(db, user)
        application_conds = [
            FundingApplication.tenant_id == _tid(),
            FundingApplication.is_deleted.is_(False),
            *student_conds,
        ]
        status_rows = db.execute(
            select(FundingApplication.status, func.count(FundingApplication.id))
            .join(StudentProfile, StudentProfile.id == FundingApplication.student_id)
            .where(*application_conds)
            .group_by(FundingApplication.status)
            .order_by(FundingApplication.status)
        ).all()
        type_rows = db.execute(
            select(
                FundingApplication.project_type,
                func.count(FundingApplication.id),
                func.coalesce(func.sum(case((FundingApplication.status == "GRANTED", 1), else_=0)), 0),
                func.coalesce(func.sum(case((
                    FundingApplication.status == "GRANTED",
                    func.coalesce(FundingApplication.approved_amount, FundingApplication.amount, 0),
                ), else_=0)), 0),
            )
            .join(StudentProfile, StudentProfile.id == FundingApplication.student_id)
            .where(*application_conds, FundingApplication.project_type.is_not(None))
            .group_by(FundingApplication.project_type)
            .order_by(FundingApplication.project_type)
        ).all()
        year_rows = db.execute(
            select(
                FundingBatch.year_code,
                func.count(FundingApplication.id),
                func.coalesce(func.sum(case((FundingApplication.status == "GRANTED", 1), else_=0)), 0),
            )
            .select_from(FundingApplication)
            .join(StudentProfile, StudentProfile.id == FundingApplication.student_id)
            .join(FundingBatch, and_(
                FundingBatch.id == FundingApplication.batch_id,
                FundingBatch.tenant_id == _tid(),
                FundingBatch.is_deleted.is_(False),
            ))
            .where(*application_conds)
            .group_by(FundingBatch.year_code)
            .order_by(FundingBatch.year_code.desc())
        ).all()
        by_status = {str(key or ""): int(count or 0) for key, count in status_rows}
        total_applications = sum(by_status.values())
        granted_applications = by_status.get("GRANTED", 0)
        in_progress_statuses = {"SUBMITTED", "COUNSELOR_REVIEW", "COLLEGE_REVIEW", "SCHOOL_REVIEW", "PUBLICITY", "RETURNED"}
        in_progress = sum(by_status.get(key, 0) for key in in_progress_statuses)
        applicant_students = int(db.scalar(
            select(func.count(func.distinct(FundingApplication.student_id)))
            .select_from(FundingApplication)
            .join(StudentProfile, StudentProfile.id == FundingApplication.student_id)
            .where(*application_conds)
        ) or 0)
        granted_students = int(db.scalar(
            select(func.count(func.distinct(FundingApplication.student_id)))
            .select_from(FundingApplication)
            .join(StudentProfile, StudentProfile.id == FundingApplication.student_id)
            .where(*application_conds, FundingApplication.status == "GRANTED")
        ) or 0)
        visible_students = int(db.scalar(
            select(func.count()).select_from(StudentProfile).where(*student_conds)
        ) or 0)

        latest_difficult = (
            select(AidApply.student_id.label("student_id"), func.max(AidApply.id).label("max_id"))
            .where(
                AidApply.tenant_id == _tid(),
                AidApply.is_deleted.is_(False),
                AidApply.status.in_(("APPROVED", "ADJUST_REVIEW")),
            )
            .group_by(AidApply.student_id)
            .subquery()
        )
        difficult_students = (
            select(AidApply.student_id.label("student_id"))
            .join(latest_difficult, AidApply.id == latest_difficult.c.max_id)
            .subquery()
        )
        difficult_count = int(db.scalar(
            select(func.count(func.distinct(difficult_students.c.student_id)))
            .select_from(difficult_students)
            .join(StudentProfile, StudentProfile.id == difficult_students.c.student_id)
            .where(*student_conds)
        ) or 0)

        funding_beneficiaries = select(FundingApplication.student_id.label("student_id")).join(
            StudentProfile, StudentProfile.id == FundingApplication.student_id
        ).where(*application_conds, FundingApplication.status == "GRANTED")
        work_beneficiaries = select(WorkStudyRecord.student_id.label("student_id")).join(
            StudentProfile, StudentProfile.id == WorkStudyRecord.student_id
        ).where(
            WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.is_deleted.is_(False),
            WorkStudyRecord.status == "ONBOARD", *student_conds,
        )
        loan_beneficiaries = select(StudentLoan.student_id.label("student_id")).join(
            StudentProfile, StudentProfile.id == StudentLoan.student_id
        ).where(
            StudentLoan.tenant_id == _tid(), StudentLoan.is_deleted.is_(False),
            StudentLoan.status == "CONFIRMED", *student_conds,
        )
        fee_beneficiaries = select(FeeReduction.student_id.label("student_id")).join(
            StudentProfile, StudentProfile.id == FeeReduction.student_id
        ).where(
            FeeReduction.tenant_id == _tid(), FeeReduction.is_deleted.is_(False),
            FeeReduction.status == "ISSUED", *student_conds,
        )
        beneficiary_rows = union_all(
            funding_beneficiaries, work_beneficiaries, loan_beneficiaries, fee_beneficiaries,
        ).subquery()
        beneficiary_students = int(db.scalar(
            select(func.count(func.distinct(beneficiary_rows.c.student_id))).select_from(beneficiary_rows)
        ) or 0)
        difficult_beneficiaries = int(db.scalar(
            select(func.count(func.distinct(beneficiary_rows.c.student_id)))
            .select_from(beneficiary_rows)
            .join(difficult_students, difficult_students.c.student_id == beneficiary_rows.c.student_id)
        ) or 0)

        work_onboard, work_subsidy = db.execute(
            select(
                func.coalesce(func.sum(case((WorkStudyRecord.status == "ONBOARD", 1), else_=0)), 0),
                func.coalesce(func.sum(WorkStudyRecord.subsidy_total), 0),
            )
            .select_from(WorkStudyRecord)
            .join(StudentProfile, StudentProfile.id == WorkStudyRecord.student_id)
            .where(WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.is_deleted.is_(False), *student_conds)
        ).one()
        loan_confirmed, loan_amount = db.execute(
            select(
                func.coalesce(func.sum(case((StudentLoan.status == "CONFIRMED", 1), else_=0)), 0),
                func.coalesce(func.sum(case((StudentLoan.status == "CONFIRMED", StudentLoan.amount), else_=0)), 0),
            )
            .select_from(StudentLoan)
            .join(StudentProfile, StudentProfile.id == StudentLoan.student_id)
            .where(StudentLoan.tenant_id == _tid(), StudentLoan.is_deleted.is_(False), *student_conds)
        ).one()
        fee_issued, fee_amount = db.execute(
            select(
                func.coalesce(func.sum(case((FeeReduction.status == "ISSUED", 1), else_=0)), 0),
                func.coalesce(func.sum(case((FeeReduction.status == "ISSUED", FeeReduction.amount), else_=0)), 0),
            )
            .select_from(FeeReduction)
            .join(StudentProfile, StudentProfile.id == FeeReduction.student_id)
            .where(FeeReduction.tenant_id == _tid(), FeeReduction.is_deleted.is_(False), *student_conds)
        ).one()

        ledger_rows = db.execute(
            select(
                FundingDisbursement.bank_status,
                func.count(FundingDisbursement.id),
                func.coalesce(func.sum(FundingDisbursement.amount), 0),
            )
            .select_from(FundingDisbursement)
            .join(StudentProfile, StudentProfile.id == FundingDisbursement.student_id)
            .where(
                FundingDisbursement.tenant_id == _tid(),
                FundingDisbursement.is_deleted.is_(False),
                *student_conds,
            )
            .group_by(FundingDisbursement.bank_status)
            .order_by(FundingDisbursement.bank_status)
        ).all()
        ledger_counts = {str(key or ""): int(count or 0) for key, count, _amount in ledger_rows}
        ledger_amounts = {str(key or ""): Decimal(str(amount or 0)) for key, _count, amount in ledger_rows}
        missing_ledger = int(db.scalar(
            select(func.count(FundingApplication.id))
            .select_from(FundingApplication)
            .join(StudentProfile, StudentProfile.id == FundingApplication.student_id)
            .outerjoin(FundingDisbursement, and_(
                FundingDisbursement.tenant_id == _tid(),
                FundingDisbursement.application_id == FundingApplication.id,
                FundingDisbursement.is_deleted.is_(False),
            ))
            .where(*application_conds, FundingApplication.status == "GRANTED", FundingDisbursement.id.is_(None))
        ) or 0)
        approved_amount = db.scalar(
            select(func.coalesce(func.sum(func.coalesce(
                FundingApplication.approved_amount, FundingApplication.amount, 0,
            )), 0))
            .select_from(FundingApplication)
            .join(StudentProfile, StudentProfile.id == FundingApplication.student_id)
            .where(*application_conds, FundingApplication.status == "GRANTED")
        ) or Decimal("0")
        amount_visible = (user or {}).get("currentRoleCode") in _AMOUNT_ROLES

        type_items = []
        for key, count, granted, amount in type_rows:
            item = {"key": str(key or ""), "count": int(count or 0), "granted": int(granted or 0)}
            if amount_visible:
                item["approvedAmount"] = _stats_money(amount)
            type_items.append(item)
        amount_summary = {"visible": amount_visible}
        if amount_visible:
            amount_summary.update({
                "approvedAmountTotal": _stats_money(approved_amount),
                "issuedAmountTotal": _stats_money(ledger_amounts.get("ISSUED", 0)),
                "workStudySubsidyTotal": _stats_money(work_subsidy),
                "confirmedLoanAmountTotal": _stats_money(loan_amount),
                "issuedReductionAmountTotal": _stats_money(fee_amount),
            })
        return {
            # 兼容已有驾驶舱和旧页面字段。
            "total": total_applications,
            "granted": granted_applications,
            "totalApplications": total_applications,
            "applicantStudents": applicant_students,
            "grantedApplications": granted_applications,
            "grantedStudents": granted_students,
            "inProgressApplications": in_progress,
            "visibleStudents": visible_students,
            "beneficiaryStudents": beneficiary_students,
            "coverageRate": _stats_ratio(beneficiary_students, visible_students),
            "difficultStudents": difficult_count,
            "difficultBeneficiaries": difficult_beneficiaries,
            "difficultCoverageRate": _stats_ratio(difficult_beneficiaries, difficult_count),
            "workStudyOnboard": int(work_onboard or 0),
            "confirmedLoans": int(loan_confirmed or 0),
            "issuedReductions": int(fee_issued or 0),
            "byStatus": [{"key": key, "count": count} for key, count in by_status.items()],
            "byType": type_items,
            "byYear": [
                {"key": str(year or "未标学年"), "count": int(count or 0), "granted": int(granted or 0)}
                for year, count, granted in year_rows
            ],
            "ledger": {
                "total": sum(ledger_counts.values()),
                "byStatus": [
                    {"key": key, "label": _L_BANK.get(key, key), "count": count}
                    for key, count in ledger_counts.items()
                ],
                "missing": missing_ledger,
                "attention": missing_ledger + ledger_counts.get("PENDING", 0)
                    + ledger_counts.get("FAILED", 0) + ledger_counts.get("RETURNED", 0),
            },
            "amounts": amount_summary,
            "scope": {
                "label": scope.get("scopeLabel") or "当前数据范围",
                "configured": bool(scope.get("isScopeConfigured")),
            },
            "definitions": {
                "coverage": "奖助获批、勤工在岗、贷款确认、减免或临补已落实的去重学生 / 当前可见学生",
                "granted": "奖助申请已获批；不等同于银行已到账",
                "loan": "助学贷款台账已确认",
            },
        }


_STATS_DRILL_METRICS = {
    "BENEFICIARY", "GRANTED", "DIFFICULT_BENEFICIARY", "WORK_STUDY_ONBOARD",
    "LOAN_CONFIRMED", "FEE_ISSUED", "DISBURSEMENT_ATTENTION",
}


def funding_stats_drill(user, metric: str, page=1, page_size=20) -> tuple[list[dict], int, dict]:
    """统计下钻只返回脱敏学生与业务来源，不授予业务写或金额明细权限。"""
    from app.models import (
        AidApply, FeeReduction, FundingApplication, FundingDisbursement, StudentLoan,
        StudentProfile, WorkStudyRecord,
    )
    metric = (metric or "").strip().upper()
    if metric not in _STATS_DRILL_METRICS:
        raise AppException("VALIDATION_ERROR", "请选择有效统计指标")
    page, page_size = normalize_page(page, page_size, default_size=20)
    with session() as db:
        _allowed, scope, student_conds = _stats_scope(db, user)
        award = exists(select(FundingApplication.id).where(
            FundingApplication.tenant_id == _tid(),
            FundingApplication.is_deleted.is_(False),
            FundingApplication.student_id == StudentProfile.id,
            FundingApplication.status == "GRANTED",
        ))
        difficult = exists(select(AidApply.id).where(
            AidApply.tenant_id == _tid(), AidApply.is_deleted.is_(False),
            AidApply.student_id == StudentProfile.id,
            AidApply.status.in_(("APPROVED", "ADJUST_REVIEW")),
        ))
        work = exists(select(WorkStudyRecord.id).where(
            WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.is_deleted.is_(False),
            WorkStudyRecord.student_id == StudentProfile.id, WorkStudyRecord.status == "ONBOARD",
        ))
        loan = exists(select(StudentLoan.id).where(
            StudentLoan.tenant_id == _tid(), StudentLoan.is_deleted.is_(False),
            StudentLoan.student_id == StudentProfile.id, StudentLoan.status == "CONFIRMED",
        ))
        fee = exists(select(FeeReduction.id).where(
            FeeReduction.tenant_id == _tid(), FeeReduction.is_deleted.is_(False),
            FeeReduction.student_id == StudentProfile.id, FeeReduction.status == "ISSUED",
        ))
        disbursement_attention = exists(select(FundingDisbursement.id).where(
            FundingDisbursement.tenant_id == _tid(), FundingDisbursement.is_deleted.is_(False),
            FundingDisbursement.student_id == StudentProfile.id,
            FundingDisbursement.bank_status.in_(("PENDING", "FAILED", "RETURNED")),
        ))
        missing_disbursement = exists(select(FundingApplication.id).where(
            FundingApplication.tenant_id == _tid(),
            FundingApplication.is_deleted.is_(False),
            FundingApplication.student_id == StudentProfile.id,
            FundingApplication.status == "GRANTED",
            ~exists(select(FundingDisbursement.id).where(
                FundingDisbursement.tenant_id == _tid(),
                FundingDisbursement.is_deleted.is_(False),
                FundingDisbursement.application_id == FundingApplication.id,
            )),
        ))
        beneficiary = or_(award, work, loan, fee)
        metric_cond = {
            "BENEFICIARY": beneficiary,
            "GRANTED": award,
            "DIFFICULT_BENEFICIARY": and_(beneficiary, difficult),
            "WORK_STUDY_ONBOARD": work,
            "LOAN_CONFIRMED": loan,
            "FEE_ISSUED": fee,
            "DISBURSEMENT_ATTENTION": or_(disbursement_attention, missing_disbursement),
        }[metric]
        total = int(db.scalar(
            select(func.count()).select_from(StudentProfile).where(*student_conds, metric_cond)
        ) or 0)
        students = db.scalars(
            select(StudentProfile).where(*student_conds, metric_cond)
            .order_by(StudentProfile.student_no, StudentProfile.id)
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        student_ids = {int(row.id) for row in students}

        def source_ids(model, status_column, statuses):
            if not student_ids:
                return set()
            return set(db.scalars(select(model.student_id).where(
                model.tenant_id == _tid(), model.is_deleted.is_(False),
                model.student_id.in_(student_ids), status_column.in_(statuses),
            )).all())

        award_ids = source_ids(FundingApplication, FundingApplication.status, ("GRANTED",))
        work_ids = source_ids(WorkStudyRecord, WorkStudyRecord.status, ("ONBOARD",))
        loan_ids = source_ids(StudentLoan, StudentLoan.status, ("CONFIRMED",))
        fee_ids = source_ids(FeeReduction, FeeReduction.status, ("ISSUED",))
        ledger_ids = source_ids(
            FundingDisbursement, FundingDisbursement.bank_status, ("PENDING", "FAILED", "RETURNED"),
        )
        missing_ids = set(db.scalars(
            select(FundingApplication.student_id)
            .outerjoin(FundingDisbursement, and_(
                FundingDisbursement.tenant_id == _tid(),
                FundingDisbursement.application_id == FundingApplication.id,
                FundingDisbursement.is_deleted.is_(False),
            ))
            .where(
                FundingApplication.tenant_id == _tid(), FundingApplication.is_deleted.is_(False),
                FundingApplication.student_id.in_(student_ids), FundingApplication.status == "GRANTED",
                FundingDisbursement.id.is_(None),
            )
        ).all()) if student_ids else set()
        labels = (
            (award_ids, "奖助获批"), (work_ids, "勤工在岗"), (loan_ids, "贷款确认"),
            (fee_ids, "减免/临补落实"), (missing_ids, "尚未建发放台账"), (ledger_ids, "发放待处理"),
        )
        items = []
        for student in students:
            sources = [label for ids, label in labels if int(student.id) in ids]
            items.append({
                "studentNo": _mask_stats_student_no(student.student_no),
                "realName": _mask_stats_name(student.real_name),
                "grade": student.grade or "",
                "sources": sources,
            })
        return items, total, {
            "metric": metric,
            "masked": True,
            "scopeLabel": scope.get("scopeLabel") or "当前数据范围",
        }

def get_application(app_id, user) -> dict:
    with session() as db:
        x, s = _load(db, app_id)
        _scope_or_403(db, x.student_id, user)
        d = _app_row(x, user, s, has_pending_appeal=int(x.id) in _pending_appeal_ids(db, [x.id]))
        d["checkSnapshot"] = json.loads(x.check_snapshot_json) if x.check_snapshot_json else {}
        d["statement"] = x.statement or ""
        from app.models import FundingDisbursement
        payments = db.scalars(select(FundingDisbursement).where(
            FundingDisbursement.tenant_id == _tid(), FundingDisbursement.application_id == x.id,
            FundingDisbursement.student_id == x.student_id, FundingDisbursement.is_deleted.is_(False),
        ).order_by(FundingDisbursement.id.desc())).all()
        d['disbursements'] = [{'disbursementId': str(p.id), 'status': p.bank_status,
            'statusLabel': _L_BANK.get(p.bank_status, '状态待核对'), 'amount': _amount_view(p.amount, user),
            'issuedAt': _iso(p.issued_at), 'failReason': (p.fail_reason or '') if p.bank_status in {'FAILED', 'RETURNED'} else ''}
            for p in payments]
        from app.core.permissions import has_permission
        d["allowedActions"] = []
        if has_permission(user, "studentAffairs.funding.approve"):
            try:
                _check_fund_review_node(db, x, user)
            except AppException:
                pass
            else:
                d["allowedActions"] = ["APPROVE", "RETURN", "REJECT"]
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
            "issuedAt": _iso(d.issued_at), "failReason": d.fail_reason or "",
            "version": int(d.version or 0)}


def generate_disbursements(batch_id, user) -> dict:
    """按批次为 GRANTED 且尚无发放记录的申请生成发放台账(PENDING)。幂等。返回 {generated}。"""
    from app.models import FundingApplication, FundingDisbursement
    with session() as db:
        apps = db.scalars(select(FundingApplication).where(
            FundingApplication.tenant_id == _tid(), FundingApplication.batch_id == int(batch_id),
            FundingApplication.status == "GRANTED", FundingApplication.is_deleted.is_(False))).all()
        application_ids = {int(application.id) for application in apps}
        existing_ids = set(db.scalars(select(FundingDisbursement.application_id).where(
            FundingDisbursement.tenant_id == _tid(),
            FundingDisbursement.application_id.in_(application_ids) if application_ids else FundingDisbursement.application_id == -1,
            FundingDisbursement.is_deleted.is_(False),
        )).all())
        made = 0
        for application in apps:
            if int(application.id) in existing_ids:
                continue
            db.add(FundingDisbursement(
                tenant_id=_tid(), application_id=application.id, batch_id=application.batch_id,
                student_id=application.student_id, project_type=application.project_type,
                amount=application.amount, bank_status="PENDING", created_by=_disb_uid(user),
            ))
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
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        student_conds = [
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ]
        page, page_size = normalize_page(page, page_size)
        total = int(db.scalar(select(func.count()).select_from(FundingDisbursement)
                              .join(StudentProfile, StudentProfile.id == FundingDisbursement.student_id)
                              .where(*conds, *student_conds)) or 0)
        rows = db.scalars(select(FundingDisbursement)
                          .join(StudentProfile, StudentProfile.id == FundingDisbursement.student_id)
                          .where(*conds, *student_conds).order_by(FundingDisbursement.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        students = {
            s.id: s for s in db.scalars(select(StudentProfile).where(
                StudentProfile.id.in_({int(d.student_id) for d in rows if d.student_id})
            )).all()
        } if rows else {}
        return [_disb_row(d, user, students.get(int(d.student_id)) if d.student_id else None)
                for d in rows], total


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
        atomic_claim_version(db, d, getattr(body, "version", None))
        d.bank_status, d.issued_at, d.fail_reason = "ISSUED", datetime.utcnow(), None
        d.disburse_no = getattr(body, "disburseNo", None) or d.disburse_no
        last4 = getattr(body, "bankLast4", None)
        if last4:
            d.bank_last4 = str(last4)[-4:]
        d.version += 1
        _audit(db, d.id, "FUNDING_DISBURSE_ISSUE", d.disburse_no or "")
        db.commit(); db.refresh(d)
        _drain_message_outbox()
        s = tenant_get(db, StudentProfile, int(d.student_id))
        return _disb_row(d, user, s)


def fail_disbursement(disbursement_id, user, reason="", expected_version=None) -> dict:
    """标记发放失败（原因≥5字；可再改发放）。"""
    from app.models import StudentProfile
    if len((reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "失败原因至少 5 字")
    with session() as db:
        d = _load_disb(db, disbursement_id)
        _scope_or_403(db, d.student_id, user)
        if d.bank_status == "ISSUED":
            raise AppException("DATA_CONFLICT", "已发放不可置失败")
        atomic_claim_version(db, d, expected_version)
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
        from decimal import Decimal
        issued_total = Decimal("0.00")
        role = (user or {}).get("currentRoleCode")
        for d in rows:
            by_status[d.bank_status] = by_status.get(d.bank_status, 0) + 1
            if d.bank_status == "ISSUED":
                issued_total += Decimal(str(d.amount or 0))
        out = {"total": len(rows),
               "byStatus": [{"key": k, "label": _L_BANK.get(k, k), "count": v} for k, v in by_status.items()]}
        if role in _AMOUNT_ROLES:
            out["issuedAmountTotal"] = format(issued_total.quantize(Decimal("0.01")), ".2f")
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
        "reviewedAt": _iso(o.reviewed_at), "version": int(o.version or 0),
        "createdAt": _iso(o.created_at),
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
        from app.services import affairs_appeal_todo_service as appeal_todo
        appeal_todo.require_submission_assignee(db, "FUNDING_APPEAL_REVIEW", int(x.student_id))
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
        s = tenant_get(db, StudentProfile, int(x.student_id)) if x.student_id else None
        result_row = _appeal_row(o, s)
        return appeal_todo.sync_after_submit("FUNDING_APPEAL_REVIEW", result_row, "appealId", "id")


def list_appeals(user, status=None, page=1, page_size=50, *, appeal_id=None, application_id=None):
    """资助申诉列表在数据库侧完成范围过滤、计数和分页。"""
    from app.models import FundingAppeal, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.core.permissions import has_permission

    page, page_size = normalize_page(page, page_size)
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        student_join = and_(
            StudentProfile.id == FundingAppeal.student_id,
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        conds = [FundingAppeal.tenant_id == _tid(), FundingAppeal.is_deleted.is_(False)]
        if status:
            conds.append(FundingAppeal.status == status)
        if appeal_id is not None:
            conds.append(FundingAppeal.id == int(appeal_id))
        if application_id is not None:
            conds.append(FundingAppeal.application_id == int(application_id))
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        total = int(db.scalar(
            select(func.count()).select_from(FundingAppeal)
            .outerjoin(StudentProfile, student_join).where(*conds)
        ) or 0)
        rows = db.execute(
            select(FundingAppeal, StudentProfile)
            .outerjoin(StudentProfile, student_join).where(*conds)
            .order_by(FundingAppeal.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        can_review = has_permission(user, 'studentAffairs.funding.publicity.manage')
        return [{**_appeal_row(appeal, student),
                 'allowedActions': ['REVIEW'] if can_review and student and appeal.status == 'SUBMITTED' else []}
                for appeal, student in rows], total


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
        expected_version = body.get("version") if isinstance(body, dict) else getattr(body, "version", None)
        atomic_claim_version(db, o, expected_version)
        if o.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "该申诉已复核")
        o.status, o.result = "CLOSED", result
        o.open_key = None
        o.review_opinion, o.reviewer = opinion, _op()[0]
        o.reviewed_at, o.version = datetime.utcnow(), o.version + 1
        if result == "SUSTAINED":
            x = tenant_get(db, FundingApplication, int(o.application_id))
            # 正常应仍为 PUBLICITY（授予前已拦截进行中申诉）；若竞态已 GRANTED 亦撤回为驳回
            if x and x.status in ("PUBLICITY", "GRANTED"):
                was_granted = x.status == "GRANTED"
                x.status, x.result_at = "REJECTED", datetime.utcnow()
                x.return_reason = (opinion[:200] if opinion else "公示申诉成立")
                x.version += 1
                if x.workflow_instance_id:
                    inst = tenant_get(db, WorkflowInstance, int(x.workflow_instance_id))
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
        s = tenant_get(db, StudentProfile, int(o.student_id)) if o.student_id else None
        result_row = _appeal_row(o, s)
        from app.services import affairs_appeal_todo_service as appeal_todo
        return appeal_todo.sync_after_review("FUNDING_APPEAL_REVIEW", int(appeal_id), result_row)
