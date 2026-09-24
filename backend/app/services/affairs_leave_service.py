"""13A-P2 请假销假闭环（范式样板：状态机 + workflow + 待办/消息 + 360 + 统计 + 双状态列）。

在既有 t_cs_leave 上做（加列扩展，非平行表，P0 §4.2 集成①）：
- affairs_status = 13A 14 态真相列；旧 status = 投影列（老 campus-service 读端点零改动全绿）。
- 审批走真 WorkflowInstance/Task + UnifiedTodo；终态写 StudentStageEvent 进 360。
后 5 个域（认定/处分/风险/调宿/归档）的"范式五件套"照抄本文件。
"""

from app.core.optimistic_lock import atomic_claim_version

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, case, func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.core.pagination import normalize_page
from app.core.tenant_scoped import tenant_get
from app.core.timeutil import parse_api_datetime, local_day_bounds_utc
from app.services.db_service import _iso, _tid, session
from app.services.affairs_sla import (
    get_leave_sla,
    leave_approval_deadline,
    leave_is_pending_approval_overdue,
)


log = logging.getLogger(__name__)

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

# 请假材料只绑定同一张既有 CsLeave；不增加小程序专用业务表或第二套请假模型。
LEAVE_FILE_BIZ_TYPE = "AFFAIRS_LEAVE"
LEAVE_FILE_RELATION_TYPE = "BUSINESS_EVIDENCE"
LEAVE_FILE_MAX_COUNT = 3

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
    return parse_api_datetime(v)


def _date_filters(start_value, end_value):
    start, end = _parse_dt(start_value), _parse_dt(end_value)
    end_exclusive = isinstance(end_value, str) and len(end_value.strip()) == 10 and end is not None
    if end_exclusive:
        _, end = local_day_bounds_utc(end_value.strip())
    return start, end, end_exclusive


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
    from app.services.affairs_assignee_service import require_assignee_id
    return require_assignee_id(db, node, student_id=student_id)


def _open_wf(db, wf_code, leave_id, applicant_id, title, first_node, assignee_id):
    from app.models import WorkflowInstance, WorkflowTask
    from app.services.runtime_preset_install_service import ensure_workflow_enabled
    ensure_workflow_enabled(db, _tid(), wf_code)
    if int(assignee_id or 0) <= 0:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", f"未配置受理人：{first_node}")
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
    if int(assignee_id or 0) <= 0:
        raise AppException("ASSIGNEE_NOT_CONFIGURED", "请假待办没有具体受理人")
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


def _student_return_todo_upsert(db, leave_id, student, title):
    """将“退回补正”显式交给学生本人，而不是把教师审批待办泄漏给学生。

    ``UnifiedTodo.student_id`` 只是业务对象主体，不能作为学生收件人判断；学生端的
    可见性严格按 ``assignee_id == StudentAccountLink.user_id``。因此退回时要新建一条
    独立的学生待办，并在学生重交时由同一状态机关闭它。
    """
    from app.models import UnifiedTodo
    from app.services.student_account_link_service import resolve_user_id_for_student

    student_id = int(getattr(student, "id", 0) or 0)
    if student_id <= 0:
        return
    student_user_id = resolve_user_id_for_student(
        db,
        tenant_id=_tid(),
        student_id=student_id,
        student_no=getattr(student, "student_no", None),
    )
    # 没有有效学生账号时不能把任务塞给 0 或教师；消息/业务状态仍照常落库，
    # 待该生完成正式账号绑定后由下一次真实业务推进生成对应待办。
    if not student_user_id:
        return
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(),
        UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_id == int(leave_id),
        UnifiedTodo.todo_type == "LEAVE_STUDENT_RESUBMIT",
        UnifiedTodo.assignee_id == int(student_user_id),
        UnifiedTodo.is_deleted.is_(False),
    ).with_for_update()).first()
    if row is None:
        db.add(UnifiedTodo(
            tenant_id=_tid(), source_module="student-affairs", source_biz_type="LEAVE",
            source_biz_id=int(leave_id), todo_type="LEAVE_STUDENT_RESUBMIT",
            assignee_id=int(student_user_id), student_id=student_id, title=title,
            status="PENDING",
        ))
        return
    row.title = title
    row.status = "PENDING"
    row.completed_at = None
    row.version = int(row.version or 0) + 1


def _invalidate_student_home(student_id, *projections):
    """提交后让该学生的 Home 投影立即丢弃缓存，而不依赖 20 秒 TTL。

    这不是业务状态的一部分：业务和审计已提交后，缓存设施短暂不可用不能把已成功
    的请假命令改报失败。下次读会自然回源；正常情况下同时 bump projectionVersion。
    """
    if int(student_id or 0) <= 0:
        return
    try:
        from app.services.mobile_student_service import invalidate_home_cache
        invalidate_home_cache(
            {"tenantId": _tid(), "studentId": int(student_id)},
            *projections,
        )
    except Exception:  # noqa: BLE001
        log.warning("leave_home_invalidation_failed student_id=%s", student_id, exc_info=True)


def _msg(db, receiver_id, title, content, mtype, leave_id, *, event_code: str | None = None):
    """请假结果通知：同事务写 outbox，由调度异步生成 UnifiedMessage。"""
    rid = int(receiver_id or 0)
    if rid <= 0:
        return None
    _MTYPE_TO_EVENT = {
        "WORKFLOW_RESULT": "LEAVE.APPROVED",
        "RETURNED_NOTICE": "LEAVE.RETURNED",
        "STATUS_CHANGED": "LEAVE.CLOSED",
        "DEADLINE_REMINDER": "LEAVE.OVERDUE",
    }
    code = (event_code or _MTYPE_TO_EVENT.get(mtype) or "LEAVE.CLOSED").strip().upper()
    from app.services.message_event_outbox_service import emit_message_event
    outbox = emit_message_event(
        db,
        event_code=code,
        source_module="student-affairs",
        source_biz_type="leave_request",
        source_biz_id=int(leave_id),
        recipient_refs=[{"studentId": rid}],
        content=content,
        title=title,
        action_key="student.leave.detail",
        action_params={"leaveId": int(leave_id)},
        dedup_key=f"{code}:leave:{int(leave_id)}:{mtype}:{title[:20]}",
    )
    # ``emit_message_event`` 已在嵌套事务中 flush，ID 可在外层业务提交后作为
    # 精确投递目标。绝不能用“处理本租户前 20 条”替代当前学生刚产生的结果通知。
    return int(getattr(outbox, "id", 0) or 0) or None


def _drain_message_outbox(outbox_ids=None):
    """业务提交后尽力同步消费本租户 outbox（失败由调度重试，不回滚业务）。"""
    # 使用统一的可观测包装：即时投递失败时业务状态不回滚，但必须留下日志，
    # 由独立 scheduler 继续消费，不能静默把事件永久留在 PENDING。
    from app.services.message_event_outbox_service import try_process_pending_outbox

    ids = []
    for value in outbox_ids or []:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            continue
        if normalized > 0:
            ids.append(normalized)
    # 有本次事务的事件时只领这些事件：历史积压不能延迟学生眼前的退回/通过结果。
    try_process_pending_outbox(
        limit=max(20, len(ids)),
        worker_id="leave-inline",
        outbox_ids=ids or None,
    )


def _verified_actor_id(user) -> int:
    """Return the authenticated database user key used by workflow assignments.

    WorkflowTask/UnifiedTodo assignees are database identities.  A non-numeric
    demo identity must never be treated as an implicit wildcard: when an active
    task has a named assignee, an unverifiable actor is denied rather than
    silently bypassing the assignee check.
    """
    raw = str((user or {}).get("userId") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    try:
        actor_id = int(raw)
    except (TypeError, ValueError):
        return 0
    return actor_id if actor_id > 0 else 0


def _check_leave_action_assignee(db, x, user, *, todo_type: str, node: str = "COUNSELOR_REVIEW"):
    """销假确认/续假审批：按辅导员节点可见性 + 待办指派人收敛（与审批链一致）。"""
    from app.core.affairs_security import build_affairs_context
    from app.models import UnifiedTodo
    ctx = build_affairs_context(user, db)
    if not _node_visible(ctx, node):
        raise AppException("NO_PERMISSION",
                           f"无权操作当前环节（{L_AFF.get(node, node)}）")
    if ctx.scope_type == "TENANT_ALL":
        return
    todo = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_id == int(x.id), UnifiedTodo.todo_type == todo_type,
        UnifiedTodo.status == "PENDING", UnifiedTodo.is_deleted.is_(False)
    ).order_by(UnifiedTodo.id.desc())).first()
    if not todo or not todo.assignee_id:
        return
    uid = _verified_actor_id(user)
    if uid <= 0:
        raise AppException("NO_PERMISSION", "当前账号缺少可核验的受理人身份")
    if int(todo.assignee_id) != uid:
        raise AppException("NO_PERMISSION", "当前待办未指派给您")


def _allowed_actions(status: str | None) -> list[str]:
    state = str(status or "")
    if state in _REVIEW_NODES:
        return ["APPROVE", "RETURN", "REJECT"]
    if state == "APPROVED":
        return ["SUBMIT_CANCEL", "SUBMIT_EXTENSION", "PROXY_CANCEL"]
    if state == "WAIT_CANCEL_LEAVE":
        return ["CONFIRM_CANCEL", "RETURN_CANCEL"]
    if state == "EXTENSION_REVIEW":
        return ["APPROVE_EXTENSION", "REJECT_EXTENSION"]
    if state == "OVERDUE":
        return ["SUBMIT_CANCEL", "SUBMIT_EXTENSION", "HANDLE_OVERDUE"]
    if state == "RETURNED":
        return ["EDIT_RETURNED", "RESUBMIT"]
    return []


def _leave_attachment_ids(value) -> list[str]:
    if value in (None, []):
        return []
    if not isinstance(value, (list, tuple)):
        raise AppException("VALIDATION_ERROR", "证明材料编号格式不正确")
    ids: list[str] = []
    for item in value:
        normalized = str(item or "").strip()
        if not normalized.isdigit():
            raise AppException("VALIDATION_ERROR", "证明材料编号非法")
        if normalized not in ids:
            ids.append(normalized)
    if len(ids) > LEAVE_FILE_MAX_COUNT:
        raise AppException("VALIDATION_ERROR", f"证明材料最多{LEAVE_FILE_MAX_COUNT}份")
    return ids


def leave_evidence(db, leave_id) -> list[dict]:
    """只在详情读取材料，列表不做逐行文件查询，避免 N+1。"""
    from app.models.file import FileBinding
    from app.services import file_service

    file_ids = db.scalars(select(FileBinding.file_id).where(
        FileBinding.tenant_id == _tid(),
        FileBinding.biz_type == LEAVE_FILE_BIZ_TYPE,
        FileBinding.biz_id == str(leave_id),
        FileBinding.relation_type == LEAVE_FILE_RELATION_TYPE,
        FileBinding.status == "ACTIVE",
        FileBinding.is_current.is_(True),
        FileBinding.is_deleted.is_(False),
    ).order_by(FileBinding.id.asc())).all()
    return [view for view in (file_service.attachment_view(str(file_id)) for file_id in file_ids) if view]


def bind_leave_evidence(db, row, file_ids, student, actor: dict) -> None:
    """在请假写事务中绑定本次新增材料；历史材料不可被客户端静默解绑。"""
    requested = _leave_attachment_ids(file_ids)
    if not requested:
        return
    from app.models.file import FileBinding
    from app.services import file_business_binding_service as binding_service

    current = {str(value) for value in db.scalars(select(FileBinding.file_id).where(
        FileBinding.tenant_id == _tid(),
        FileBinding.biz_type == LEAVE_FILE_BIZ_TYPE,
        FileBinding.biz_id == str(row.id),
        FileBinding.relation_type == LEAVE_FILE_RELATION_TYPE,
        FileBinding.status == "ACTIVE",
        FileBinding.is_current.is_(True),
        FileBinding.is_deleted.is_(False),
    )).all()}
    if len(current.union(requested)) > LEAVE_FILE_MAX_COUNT:
        raise AppException("VALIDATION_ERROR", f"同一请假最多保留{LEAVE_FILE_MAX_COUNT}份证明材料")
    for file_id in requested:
        binding_service.bind_file_to_business(
            db,
            file_id=file_id,
            biz_type=LEAVE_FILE_BIZ_TYPE,
            biz_id=row.id,
            actor=actor,
            subject_type="STUDENT",
            subject_id=student.id,
            relation_type=LEAVE_FILE_RELATION_TYPE,
            module_code="STUDENT_AFFAIRS",
            student_id=student.id,
            college_id=getattr(student, "college_id", None),
            class_id=getattr(student, "class_id", None),
            scope={
                "studentId": str(student.id),
                "classId": str(getattr(student, "class_id", "") or ""),
                "leaveId": str(row.id),
            },
        )


def _row(x, s=None, *, include_attachments: bool = False, db=None) -> dict:
    approval_deadline = leave_approval_deadline(getattr(x, "created_at", None))
    result = {
        "id": str(x.id), "studentId": str(x.student_id or ""),
        "version": int(x.version or 0), "allowedActions": _allowed_actions(x.affairs_status),
        "studentNo": (s.student_no if s else "") or "",
        "studentName": s.real_name if s else "", "className": str(s.class_id or "") if s else "",
        "leaveType": x.leave_type, "leaveTypeLabel": L_TYPE.get(x.leave_type or "", x.leave_type or ""),
        "days": float(x.days or 0),
        "startTime": _iso(x.start_time), "endTime": _iso(x.end_time), "reason": x.reason or "",
        "returnReason": getattr(x, "return_reason", None) or "",
        "affairsStatus": x.affairs_status,
        "affairsStatusLabel": L_AFF.get(x.affairs_status or "", x.affairs_status or ""),
        "legacyStatus": x.status,  # 投影列（老端点读这个，双状态列一致性）
        "workflowInstanceId": str(x.workflow_instance_id or ""),
        "expectedReturnAt": _iso(x.expected_return_at), "actualReturnAt": _iso(x.actual_return_at),
        "slaOverdue": leave_is_pending_approval_overdue(x),
        "sla": {
            "approvalDeadline": _iso(approval_deadline) if approval_deadline else None,
            "approvalHours": get_leave_sla()["approvalHours"],
        },
    }
    if include_attachments:
        # 详情路径在事务提交后调用；File Center 会再次做当前用户、租户和业务范围授权。
        result["attachments"] = leave_evidence(db, x.id) if db is not None else []
    return result


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
    x = tenant_get(db, CsLeave, int(leave_id))
    if not x or x.is_deleted or x.tenant_id != _tid() or x.affairs_status is None:
        raise not_found("请假申请不存在")
    s = tenant_get(db, StudentProfile, int(x.student_id)) if x.student_id else None
    return x, s


def _scope_or_403(db, x, user):
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.models import StudentProfile
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is None:
        return
    s = tenant_get(db, StudentProfile, int(x.student_id)) if x.student_id else None
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
    # 有明确审批人时：非全域角色必须是当前 PENDING 任务的 assignee（避免同节点多人互批）。
    if ctx.scope_type == "TENANT_ALL" or not x.workflow_instance_id:
        return
    from app.models import WorkflowTask
    task = db.scalars(select(WorkflowTask).where(
        WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == int(x.workflow_instance_id),
        WorkflowTask.node_code == x.affairs_status, WorkflowTask.status == "PENDING",
        WorkflowTask.is_deleted.is_(False)).order_by(WorkflowTask.id.desc())).first()
    if not task or not task.assignee_id:
        return
    uid = _verified_actor_id(user)
    if uid <= 0:
        raise AppException("NO_PERMISSION", "当前账号缺少可核验的受理人身份")
    if int(task.assignee_id) != uid:
        raise AppException("NO_PERMISSION", "当前审批任务未指派给您")


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
        # 同一学生的请假创建共享一把主档行锁。若只做“查询重叠→insert”，
        # 两个首次请求会同时看到空集合并各自落单；行锁使第二个事务在首单
        # 提交后再检查正式记录，从数据库层兜住双击和网络重试。
        s = db.scalars(select(StudentProfile).where(StudentProfile.id == student_id, StudentProfile.tenant_id == _tid()).with_for_update()).first()
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
        x = CsLeave(tenant_id=_tid(), cs_student_id=None, student_id=student_id,
                    leave_type=(body.leaveType or "PERSONAL"), start_time=start, end_time=end,
                    reason=body.reason, days=days, duration=f"{days}天",
                    affairs_status=first, status=_project(first), apply_time=datetime.utcnow(),
                    expected_return_at=end)
        db.add(x)
        db.flush()
        bind_leave_evidence(db, x, getattr(body, "fileIds", None), s, user)
        assignee = _assignee_for(db, first, student_id)
        inst = _open_wf(db, wf, x.id, student_id, f"{s.real_name} 请假 {days} 天", first, assignee)
        x.workflow_instance_id = inst.id
        _todo_upsert(db, x.id, assignee, student_id, f"请假待审批：{s.real_name} {days}天")
        _audit(db, x.id, "APPLY", f"days={days},wf={wf}")
        db.commit()
        db.refresh(x)
        out = _resolve_class_names(db, [_row(x, s)])[0]
    _invalidate_student_home(student_id, "case")
    return out


# ═══════════ 审批（多级） ═══════════

def _act_task(db, x, action, reason=""):
    from app.models import WorkflowInstance
    inst = tenant_get(db, WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
    task = _cur_task(db, inst.id, x.affairs_status) if inst else None
    if task:
        task.status = action
        task.acted_at = datetime.utcnow()
        task.action_reason = reason
        task.version += 1
    return inst


def approve(leave_id, user, comment="", expected_version=None) -> dict:
    message_outbox_id = None
    with session() as db:
        from app.models import WorkflowTask
        x, s = _load(db, leave_id)
        student_id = int(x.student_id or 0)
        _scope_or_403(db, x, user)
        aff = x.affairs_status
        if aff not in _REVIEW_NODES:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该请假当前状态不可审批，请刷新")
        atomic_claim_version(db, x, expected_version)
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
            message_outbox_id = _msg(
                db, x.student_id, "请假已通过", f"你的请假（{x.days}天）已通过审批",
                "WORKFLOW_RESULT", x.id, event_code="LEAVE.APPROVED",
            )
            _audit(db, x.id, "APPROVED", comment)
            from app.modules.platform.document_lifecycle.fact_hooks import affairs_leave_approved
            from app.services.message_identity import resolve_message_user_id

            affairs_leave_approved(
                db, leave=x, actor_id=resolve_message_user_id(user or {}) or None,
            )
        db.commit()
        db.refresh(x)
        out = _resolve_class_names(db, [_row(x, s)])[0]
    if message_outbox_id:
        _drain_message_outbox([message_outbox_id])
    _invalidate_student_home(student_id, "todo", "message", "case")
    return out


def reject(leave_id, user, reason, expected_version=None) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    message_outbox_id = None
    with session() as db:
        x, s = _load(db, leave_id)
        student_id = int(x.student_id or 0)
        _scope_or_403(db, x, user)
        if x.affairs_status not in _REVIEW_NODES:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该请假当前状态不可驳回，请刷新")
        atomic_claim_version(db, x, expected_version)
        _check_review_node(db, x, user)
        inst = _act_task(db, x, "REJECTED", reason.strip())
        x.affairs_status, x.status, x.return_reason = "REJECTED", "RETURNED", reason.strip()
        x.version += 1
        if inst:
            inst.status = "REJECTED"
        _todo_done(db, x.id)
        message_outbox_id = _msg(
            db, x.student_id, "请假被驳回", reason.strip(), "RETURNED_NOTICE", x.id,
            event_code="LEAVE.REJECTED",
        )
        _audit(db, x.id, "REJECTED", reason.strip())
        db.commit()
        db.refresh(x)
        out = _resolve_class_names(db, [_row(x, s)])[0]
    if message_outbox_id:
        _drain_message_outbox([message_outbox_id])
    _invalidate_student_home(student_id, "todo", "message", "case")
    return out


def return_leave(leave_id, user, reason, expected_version=None) -> dict:
    """退回申请人重提（区别于 reject 终态）。"""
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    message_outbox_id = None
    with session() as db:
        x, s = _load(db, leave_id)
        student_id = int(x.student_id or 0)
        _scope_or_403(db, x, user)
        if x.affairs_status not in _REVIEW_NODES:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该请假当前状态不可退回，请刷新")
        atomic_claim_version(db, x, expected_version)
        _check_review_node(db, x, user)
        inst = _act_task(db, x, "TRANSFERRED", reason.strip())
        x.affairs_status, x.status, x.return_reason = "RETURNED", "RETURNED", reason.strip()
        x.version += 1
        if inst:
            inst.status = "RETURNED"
        _todo_done(db, x.id)
        _student_return_todo_upsert(
            db,
            x.id,
            s,
            "请假已退回，请补充材料后重新提交",
        )
        message_outbox_id = _msg(
            db, x.student_id, "请假被退回", reason.strip(), "RETURNED_NOTICE", x.id,
            event_code="LEAVE.RETURNED",
        )
        _audit(db, x.id, "RETURNED", reason.strip())
        db.commit()
        db.refresh(x)
        out = _resolve_class_names(db, [_row(x, s)])[0]
    if message_outbox_id:
        _drain_message_outbox([message_outbox_id])
    _invalidate_student_home(student_id, "todo", "message", "case")
    return out


def resubmit(leave_id, user, expected_version=None, *, self_only: bool = False, reason: str | None = None) -> dict:
    """退回后重新提交 → 回到首个审批节点（新审批周期）。

    self_only=True：学生自助入口，仅允许本人对自己的 RETURNED 请假重交；
    不走教职工班级数据范围（学生无班级管理范围）。
    reason：可选补充事由（≥5 字），与状态推进同一事务写入，避免二次开库无租户校验。
    """
    reason_clean = str(reason or "").strip()
    if reason_clean and len(reason_clean) < 5:
        raise AppException("VALIDATION_ERROR", "补充事由不少于 5 字")
    with session() as db:
        from app.models import WorkflowInstance, WorkflowTask
        x, s = _load(db, leave_id)
        student_id = int(x.student_id or 0)
        if x.affairs_status != "RETURNED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅被退回的请假可重新提交")
        atomic_claim_version(db, x, expected_version)
        if self_only:
            from app.services.mobile_student_service import resolve_student
            me = resolve_student(db, user or {})
            if not me or int(me.id) != int(x.student_id or 0):
                raise AppException("NO_DATA_SCOPE", "只能重新提交本人的请假")
        else:
            _scope_or_403(db, x, user)
        wf = _wf_code(float(x.days or 1))
        first = NODE_SEQ[wf][0]
        x.affairs_status, x.status, x.return_reason = first, _project(first), None
        if reason_clean:
            x.reason = reason_clean
        x.version += 1
        inst = tenant_get(db, WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
        if inst:
            inst.status, inst.current_node = "RUNNING", first
        assignee = _assignee_for(db, first, x.student_id)
        db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id if inst else 0, node_code=first,
                            assignee_id=assignee, status="PENDING"))
        _todo_upsert(db, x.id, assignee, x.student_id, f"请假重新提交待审批：{s.real_name if s else ''}")
        _todo_done(db, x.id, todo_type="LEAVE_STUDENT_RESUBMIT")
        _audit(db, x.id, "RESUBMIT", reason_clean or "")
        db.commit()
        db.refresh(x)
        out = _resolve_class_names(db, [_row(x, s)])[0]
    _invalidate_student_home(student_id, "todo", "case")
    return out


# ═══════════ 销假 ═══════════

def submit_cancel(leave_id, user, proof_note="", expected_version=None, *, self_only: bool = False) -> dict:
    with session() as db:
        from app.models import AffairsLeaveCancelRecord
        x, s = _load(db, leave_id)
        if self_only:
            from app.services.mobile_student_service import resolve_student
            me = resolve_student(db, user or {})
            if not me or int(me.id) != int(x.student_id or 0):
                raise AppException("NO_DATA_SCOPE", "只能对本人数假发起销假")
        else:
            _scope_or_403(db, x, user)
        if x.affairs_status not in ("APPROVED", "OVERDUE"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已通过/逾期的请假可发起销假")
        atomic_claim_version(db, x, expected_version)
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


def confirm_cancel(leave_id, user, action="CONFIRM", actual_return_at=None, reason="", note="",
                   expected_version=None) -> dict:
    """销假确认(CONFIRM→CLOSED进360) / 销假退回(RETURN→APPROVED，证明不符重新销假)。契约 #23。"""
    action = (action or "CONFIRM").upper()
    if action not in ("CONFIRM", "RETURN"):
        raise AppException("VALIDATION_ERROR", "action 仅支持 CONFIRM / RETURN")
    if action == "RETURN" and (not reason or len(reason.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "销假退回原因必填且不少于 5 字")
    message_outbox_id = None
    with session() as db:
        from app.models import AffairsLeaveCancelRecord, StudentStageEvent
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status != "WAIT_CANCEL_LEAVE":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该请假不在待销假确认状态")
        atomic_claim_version(db, x, expected_version)
        _check_leave_action_assignee(db, x, user, todo_type="LEAVE_CANCEL")
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
            message_outbox_id = _msg(
                db, x.student_id, "销假被退回", reason.strip(), "RETURNED_NOTICE", x.id,
                event_code="LEAVE.RETURN_REJECTED",
            )
            _audit(db, x.id, "CANCEL_RETURN", reason.strip())
            db.commit()
            db.refresh(x)
            out = _resolve_class_names(db, [_row(x, s)])[0]
            if message_outbox_id:
                _drain_message_outbox([message_outbox_id])
            return out
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
        message_outbox_id = _msg(
            db, x.student_id, "销假完成", "你的请假已销假归档", "STATUS_CHANGED", x.id,
            event_code="LEAVE.RETURN_DONE",
        )
        _audit(db, x.id, "CLOSED", note)
        db.commit()
        db.refresh(x)
        out = _resolve_class_names(db, [_row(x, s)])[0]
    if message_outbox_id:
        _drain_message_outbox([message_outbox_id])
    return out


# ═══════════ 续假 ═══════════

def apply_extension(leave_id, user, new_end, reason="", expected_version=None, *, self_only: bool = False) -> dict:
    with session() as db:
        from app.models import AffairsLeaveExtension
        x, s = _load(db, leave_id)
        if self_only:
            from app.services.mobile_student_service import resolve_student
            stu = resolve_student(db, user)
            if not stu or int(x.student_id or 0) != int(stu.id):
                raise AppException("NO_PERMISSION", "只能为自己的请假申请续假")
        else:
            _scope_or_403(db, x, user)
        if x.affairs_status not in ("APPROVED", "OVERDUE"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已通过的请假可续假")
        atomic_claim_version(db, x, expected_version)
        from app.services.affairs_leave_date_contract import _parse as parse_leave_date
        ne = parse_leave_date(new_end, end_of_day=True)
        if not ne or (x.end_time and ne <= x.end_time):
            raise AppException("VALIDATION_ERROR", "续假结束时间必须晚于原结束时间")
        if not reason or len(str(reason).strip()) < 5:
            raise AppException("VALIDATION_ERROR", "续假事由必填且不少于 5 字")
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


def approve_extension(leave_id, user, action="APPROVE", reason="", expected_version=None) -> dict:
    """续假审批：APPROVE（更新结束时间→APPROVED）/ REJECT（维持原假期与原到期日）。契约 #24。"""
    action = (action or "APPROVE").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 仅支持 APPROVE / REJECT")
    if action == "REJECT" and (not reason or len(reason.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "续假驳回原因必填且不少于 5 字")
    message_outbox_id = None
    with session() as db:
        from app.models import AffairsLeaveExtension
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status != "EXTENSION_REVIEW":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该请假不在续假审批状态")
        atomic_claim_version(db, x, expected_version)
        _check_leave_action_assignee(db, x, user, todo_type="LEAVE_EXTENSION")
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
            message_outbox_id = _msg(
                db, x.student_id, "续假被驳回", reason.strip(), "WORKFLOW_RESULT", x.id,
                event_code="LEAVE.EXTEND_REJECTED",
            )
            _audit(db, x.id, "EXTENSION_REJECTED", reason.strip())
            db.commit()
            db.refresh(x)
            out = _resolve_class_names(db, [_row(x, s)])[0]
            if message_outbox_id:
                _drain_message_outbox([message_outbox_id])
            return out
        if ext:
            ext.status = "APPROVED"
            ext.version += 1
            x.end_time = ext.new_end_time
            x.expected_return_at = ext.new_end_time
            x.days = _days(x.start_time, ext.new_end_time)
        x.affairs_status, x.status, x.overdue_pushed_at = "APPROVED", "APPROVED", None
        x.version += 1
        _todo_done(db, x.id, todo_type="LEAVE_EXTENSION")
        message_outbox_id = _msg(
            db, x.student_id, "续假已通过", f"续假已通过，新结束时间 {_iso(x.end_time)}", "WORKFLOW_RESULT", x.id,
            event_code="LEAVE.EXTEND_APPROVED",
        )
        _audit(db, x.id, "EXTENSION_APPROVED")
        db.commit()
        db.refresh(x)
        out = _resolve_class_names(db, [_row(x, s)])[0]
    if message_outbox_id:
        _drain_message_outbox([message_outbox_id])
    return out


# ═══════════ 代登记销假 + 逾期处置 ═══════════

def proxy_cancel(leave_id, user, actual_return_at, note="", expected_version=None) -> dict:
    """辅导员代登记销假（学生无法操作时）→ WAIT_CANCEL_LEAVE。契约 #26。"""
    with session() as db:
        from app.models import AffairsLeaveCancelRecord
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status not in ("APPROVED", "OVERDUE"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已通过/逾期的请假可代登记销假")
        atomic_claim_version(db, x, expected_version)
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


def handle_overdue(leave_id, user, handle_type, note="", expected_version=None) -> dict:
    """逾期处置登记：CONTACT/TO_HOME_SCHOOL 留痕不改状态；CLOSE→CLOSED 进360。契约 #25 / 状态机 §1 OVERDUE 分支。"""
    handle_type = (handle_type or "").upper()
    if handle_type not in OVERDUE_HANDLE_TYPES:
        raise AppException("VALIDATION_ERROR", "handleType 仅支持 CONTACT / TO_HOME_SCHOOL / CLOSE")
    if not note or len(note.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处置说明必填且不少于 5 字")
    message_outbox_id = None
    with session() as db:
        from app.models import StudentStageEvent
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        if x.affairs_status != "OVERDUE":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅逾期未销假的请假可登记逾期处置")
        atomic_claim_version(db, x, expected_version)
        if handle_type == "CLOSE":
            x.affairs_status, x.status = "CLOSED", "APPROVED"
            x.version += 1
            if x.student_id:
                db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(x.student_id), from_stage=None,
                                         to_stage="LEAVE_CLOSED", reason=f"逾期请假处置关闭（{x.days}天）",
                                         source_module="student-affairs"))
            _todo_done(db, x.id, todo_type="LEAVE_OVERDUE")
            message_outbox_id = _msg(
                db, x.student_id, "逾期请假已处置关闭", note.strip(), "STATUS_CHANGED", x.id,
                event_code="LEAVE.CLOSED",
            )
            _audit(db, x.id, "OVERDUE_CLOSED", note.strip())
        else:
            _audit(db, x.id, f"OVERDUE_{handle_type}", note.strip())
        db.commit()
        db.refresh(x)
        out = _resolve_class_names(db, [_row(x, s)])[0]
    if message_outbox_id:
        _drain_message_outbox([message_outbox_id])
    return out

def scan_overdue() -> dict:
    from app.models import CsLeave
    now = datetime.utcnow()
    message_outbox_ids = []
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
            message_outbox_id = _msg(
                db, x.student_id, "请假已逾期", "你的请假已到期未销假，请尽快销假", "DEADLINE_REMINDER", x.id,
                event_code="LEAVE.OVERDUE",
            )
            if message_outbox_id:
                message_outbox_ids.append(message_outbox_id)
            _audit(db, x.id, "OVERDUE")
            cnt += 1
        db.commit()
    if message_outbox_ids:
        _drain_message_outbox(message_outbox_ids)
    return {"count": cnt}


# ═══════════ 查询 ═══════════

def _leave_progress(db, record, result, *, staff=False):
    from app.models import AffairsLeaveCancelRecord, AffairsLeaveExtension
    from app.services.affairs_student_contract_service import _workflow_context
    context = _workflow_context(db, biz_type='LEAVE', biz_id=record.id, workflow_id=record.workflow_instance_id)
    active = record.affairs_status in (*_REVIEW_NODES, 'EXTENSION_REVIEW', 'WAIT_CANCEL_LEAVE', 'OVERDUE')
    result['handler'] = context['handler'] if active else ''
    result['dueAt'] = context['dueAt'] if active else ''
    result['currentNodeLabel'] = L_AFF.get(record.affairs_status, '状态待确认')
    result['extensions'] = [{
        'id': str(e.id), 'oldEndTime': _iso(e.old_end_time), 'newEndTime': _iso(e.new_end_time),
        'extendDays': float(e.extend_days or 0), 'reason': e.reason or '', 'status': e.status,
    } for e in db.scalars(select(AffairsLeaveExtension).where(
        AffairsLeaveExtension.tenant_id == _tid(), AffairsLeaveExtension.leave_id == record.id,
        AffairsLeaveExtension.is_deleted.is_(False),
    ).order_by(AffairsLeaveExtension.id.desc()))]
    result['cancelRecords'] = [{
        'id': str(c.id), 'actualReturnAt': _iso(c.actual_return_at), 'proofNote': c.proof_note or '',
        'status': c.status, 'confirmAt': _iso(c.confirm_at), 'confirmNote': c.confirm_note or '',
        **({'confirmBy': c.confirm_by or ''} if staff else {}),
    } for c in db.scalars(select(AffairsLeaveCancelRecord).where(
        AffairsLeaveCancelRecord.tenant_id == _tid(), AffairsLeaveCancelRecord.leave_id == record.id,
        AffairsLeaveCancelRecord.is_deleted.is_(False),
    ).order_by(AffairsLeaveCancelRecord.id.desc()))]


def _staff_detail_actions(db, record, user):
    from app.core.permissions import has_permission
    permissions = {
        'APPROVE': 'studentAffairs.leave.approve', 'RETURN': 'studentAffairs.leave.approve',
        'REJECT': 'studentAffairs.leave.approve', 'PROXY_CANCEL': 'studentAffairs.leave.cancelLeaveConfirm',
        'CONFIRM_CANCEL': 'studentAffairs.leave.cancelLeaveConfirm', 'RETURN_CANCEL': 'studentAffairs.leave.cancelLeaveConfirm',
        'APPROVE_EXTENSION': 'studentAffairs.leave.extension.approve', 'REJECT_EXTENSION': 'studentAffairs.leave.extension.approve',
        'SUBMIT_EXTENSION': 'studentAffairs.leave.create', 'HANDLE_OVERDUE': 'studentAffairs.leave.overdue.handle',
    }
    try:
        if record.affairs_status in _REVIEW_NODES:
            _check_review_node(db, record, user)
        elif record.affairs_status in ('WAIT_CANCEL_LEAVE', 'EXTENSION_REVIEW'):
            _check_leave_action_assignee(db, record, user, todo_type='LEAVE_CANCEL' if record.affairs_status == 'WAIT_CANCEL_LEAVE' else 'LEAVE_EXTENSION')
    except AppException:
        return []
    candidates = _allowed_actions(record.affairs_status)
    if record.affairs_status == 'OVERDUE':
        candidates = [*candidates, 'PROXY_CANCEL']
    return [action for action in candidates
            if action in permissions and has_permission(user, permissions[action])]

def get_detail(leave_id, user) -> dict:
    with session() as db:
        from app.models import AffairsAuditTrail
        x, s = _load(db, leave_id)
        _scope_or_403(db, x, user)
        row = _resolve_class_names(db, [_row(x, s, include_attachments=True, db=db)])[0]
        trail = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == _tid(), AffairsAuditTrail.biz_type == "LEAVE",
            AffairsAuditTrail.biz_id == x.id).order_by(AffairsAuditTrail.id.asc())).all()
        row["auditTrail"] = [{
            "action": t.action, "operator": t.operator or "", "roleName": t.role_name or "",
            "detail": t.detail or "", "occurredAt": _iso(t.occurred_at),
        } for t in trail]
        _leave_progress(db, x, row, staff=True)
        row['allowedActions'] = _staff_detail_actions(db, x, user)
        from app.core.permissions import has_permission
        row['canManageMaterials'] = has_permission(user, 'studentAffairs.leave.approve')
        return row


# ═══════════ 请假台账 / 统计 / 导出（本模块新增：13A-05 台账 + 统计口径）═══════════

def list_leaves(user, status=None, leave_type=None, class_id=None, keyword=None,
                date_start=None, date_end=None, followup_only=False, page=1, page_size=20,
                student_id=None):
    """请假台账/后续处理列表：全状态可筛，数据范围裁剪。followup_only=只取延期销假可处理的活动态。"""
    from app.models import CsLeave, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    want_sid = None
    if student_id:
        try:
            want_sid = int(student_id)
        except (TypeError, ValueError):
            return [], 0
    want_class_id = None
    if class_id:
        try:
            want_class_id = int(class_id)
        except (TypeError, ValueError):
            return [], 0
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        ds, de, end_exclusive = _date_filters(date_start, date_end)
        conds = [CsLeave.tenant_id == _tid(), CsLeave.is_deleted.is_(False),
                 CsLeave.affairs_status.is_not(None), StudentProfile.tenant_id == _tid(),
                 StudentProfile.is_deleted.is_(False)]
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        if want_sid is not None:
            conds.append(CsLeave.student_id == want_sid)
        if followup_only:
            conds.append(CsLeave.affairs_status.in_(FOLLOWUP_STATES))
        if status == "PENDING":
            conds.append(CsLeave.affairs_status.in_(_REVIEW_NODES))
        elif status == "CANCEL_PENDING":
            conds.append(CsLeave.affairs_status == "WAIT_CANCEL_LEAVE")
        elif status == "OPEN":
            conds.append(CsLeave.affairs_status.in_(
                (*_REVIEW_NODES, "APPROVED", "OVERDUE", "WAIT_CANCEL_LEAVE", "EXTENSION_REVIEW")))
        elif status == "DONE":
            conds.append(CsLeave.affairs_status.in_(("CLOSED", "REJECTED", "CANCELLED")))
        elif status:
            conds.append(CsLeave.affairs_status == status)
        if leave_type:
            conds.append(CsLeave.leave_type == leave_type)
        if want_class_id is not None:
            conds.append(StudentProfile.class_id == want_class_id)
        if keyword:
            k = str(keyword)
            conds.append(or_(StudentProfile.real_name.contains(k), StudentProfile.student_no.contains(k)))
        if ds:
            conds.append(or_(CsLeave.start_time.is_(None), CsLeave.start_time >= ds))
        if de:
            conds.append(or_(CsLeave.start_time.is_(None), CsLeave.start_time < de if end_exclusive else CsLeave.start_time <= de))
        page, page_size = normalize_page(page, page_size)
        total = int(db.scalar(select(func.count()).select_from(CsLeave)
                              .join(StudentProfile, StudentProfile.id == CsLeave.student_id)
                              .where(*conds)) or 0)
        q_rows = db.scalars(select(CsLeave).join(StudentProfile, StudentProfile.id == CsLeave.student_id)
                            .where(*conds).order_by(CsLeave.id.desc())
                            .offset((page - 1) * page_size).limit(page_size)).all()
        students = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_({int(x.student_id) for x in q_rows if x.student_id})
        )).all()} if q_rows else {}
        out = [_row(x, students.get(int(x.student_id)) if x.student_id else None) for x in q_rows]
        _resolve_class_names(db, out)
        return out, total


def leave_stats(user, group_by="CLASS", date_start=None, date_end=None) -> dict:
    """请假统计：数据库聚合，SQL 数量不随记录数增长。"""
    from app.models import CsLeave, SchoolClass, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids

    gb = (group_by or "CLASS").upper()
    if gb not in ("CLASS", "TYPE", "STATUS"):
        gb = "CLASS"
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        ds, de, end_exclusive = _date_filters(date_start, date_end)
        now = datetime.utcnow()
        leave_sla = get_leave_sla()
        conds = [
            CsLeave.tenant_id == _tid(),
            CsLeave.is_deleted.is_(False),
            CsLeave.affairs_status.is_not(None),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        ]
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        if ds:
            conds.append(or_(CsLeave.start_time.is_(None), CsLeave.start_time >= ds))
        if de:
            conds.append(or_(CsLeave.start_time.is_(None), CsLeave.start_time < de if end_exclusive else CsLeave.start_time <= de))

        active_day_states = (
            "APPROVED", "CLOSED", "ARCHIVED", "OVERDUE",
            "WAIT_CANCEL_LEAVE", "EXTENSION_REVIEW",
        )
        overdue_before = now - timedelta(hours=leave_sla["approvalHours"])
        near_due_until = now + timedelta(hours=leave_sla["nearDueHours"])
        metric_row = db.execute(select(
            func.count(func.distinct(CsLeave.student_id)),
            func.coalesce(func.sum(case(
                (CsLeave.affairs_status.in_(active_day_states), CsLeave.days), else_=0,
            )), 0),
            func.coalesce(func.sum(case((and_(
                CsLeave.affairs_status == "APPROVED",
                CsLeave.start_time <= now, CsLeave.end_time >= now,
            ), 1), else_=0)), 0),
            func.coalesce(func.sum(case((CsLeave.affairs_status.in_(_REVIEW_NODES), 1), else_=0)), 0),
            func.coalesce(func.sum(case((and_(
                CsLeave.affairs_status.in_(_REVIEW_NODES),
                CsLeave.created_at <= overdue_before,
            ), 1), else_=0)), 0),
            func.coalesce(func.sum(case((and_(
                CsLeave.affairs_status.in_(("APPROVED", "WAIT_CANCEL_LEAVE")),
                CsLeave.expected_return_at >= now,
                CsLeave.expected_return_at <= near_due_until,
            ), 1), else_=0)), 0),
            func.coalesce(func.sum(case((CsLeave.affairs_status == "WAIT_CANCEL_LEAVE", 1), else_=0)), 0),
            func.coalesce(func.sum(case((CsLeave.affairs_status == "OVERDUE", 1), else_=0)), 0),
            func.coalesce(func.sum(case((CsLeave.affairs_status == "CLOSED", 1), else_=0)), 0),
        ).select_from(CsLeave).join(
            StudentProfile, StudentProfile.id == CsLeave.student_id,
        ).where(*conds)).one()

        if gb == "CLASS":
            key_expr = StudentProfile.class_id
        elif gb == "TYPE":
            key_expr = CsLeave.leave_type
        else:
            key_expr = CsLeave.affairs_status
        grouped = db.execute(select(
            key_expr.label("bucket"),
            func.count(CsLeave.id),
            func.coalesce(func.sum(CsLeave.days), 0),
            func.count(func.distinct(CsLeave.student_id)),
        ).select_from(CsLeave).join(
            StudentProfile, StudentProfile.id == CsLeave.student_id,
        ).where(*conds).group_by(key_expr).order_by(func.count(CsLeave.id).desc())).all()

        class_names = {}
        if gb == "CLASS":
            class_ids = [int(row.bucket) for row in grouped if row.bucket]
            if class_ids:
                class_names = dict(db.execute(select(
                    SchoolClass.id, SchoolClass.class_name,
                ).where(
                    SchoolClass.tenant_id == _tid(),
                    SchoolClass.id.in_(class_ids),
                    SchoolClass.is_deleted.is_(False),
                )).all())

        def _label(key):
            if gb == "CLASS":
                return class_names.get(int(key), f"班级{key}") if key else "未分班"
            if gb == "TYPE":
                return L_TYPE.get(str(key or "OTHER"), str(key or "其他"))
            return L_AFF.get(str(key or ""), str(key or ""))

        breakdown = [{
            "key": str(row.bucket or ""),
            "label": _label(row.bucket),
            "count": int(row[1] or 0),
            "days": round(float(row[2] or 0), 1),
            "studentCount": int(row[3] or 0),
        } for row in grouped]
        values = [int(metric_row[0] or 0), round(float(metric_row[1] or 0), 1)] + [
            int(value or 0) for value in metric_row[2:]
        ]
        keys = (
            ("leaveStudentCount", "请假人数", "人"),
            ("totalDays", "请假总天数", "天"),
            ("onLeave", "当前在假", "人次"),
            ("pendingReview", "待审批", "件"),
            ("pendingApprovalOverdue", "审批超时", "件"),
            ("nearDue", "临近返校", "件"),
            ("waitCancel", "待销假", "件"),
            ("overdue", "逾期未销", "件"),
            ("closed", "已销假", "件"),
        )
        return {
            "groupBy": gb,
            "metrics": [
                {"key": key, "label": label, "value": value, "unit": unit}
                for (key, label, unit), value in zip(keys, values)
            ],
            "breakdown": breakdown,
        }


def export_leaves(user, status=None, leave_type=None, class_id=None, keyword=None,
                  date_start=None, date_end=None, followup_only=False, student_id=None) -> dict:
    """兼容入口：创建正式异步导出任务，不在 Web 请求内生成百万行 XLSX。"""
    from app.services.affairs_leave_export_service import create_job

    return create_job(
        user, status, leave_type, class_id, keyword, date_start, date_end,
        followup_only=followup_only, student_id=student_id,
    )


def list_pending(user, page=1, page_size=20, keyword=None):
    """待审批队列：仅返回调用者数据范围内、且当前节点确实轮到其身份审批的请假
    （修复越权配套：避免辅导员在列表里看到无权处理的学院/学工处环节数据）。

    keyword 按姓名/学号在服务端过滤。必须落在 tenant/数据范围/审批节点条件之后、
    COUNT/OFFSET/LIMIT 之前：待审量 >100 时前端本地过滤会漏掉真实存在的记录（结果不真实），
    而放在范围条件之前则会让关键词变成绕过数据范围的口子。"""
    from app.models import CsLeave, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.core.affairs_security import build_affairs_context
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        ctx = build_affairs_context(user, db)
        visible_nodes = [node for node in _REVIEW_NODES if _node_visible(ctx, node)]
        conds = [CsLeave.tenant_id == _tid(), CsLeave.is_deleted.is_(False),
                 CsLeave.affairs_status.in_(visible_nodes or ("__NO_VISIBLE_NODE__",)),
                 StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)]
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        # 数据范围只说明“能看到这个学生”，并不说明当前审批任务轮到该教师。
        # 真实工作流已有明确 assignee 时，辅导员/学院管理员的待办队列必须与
        # approve() 里的 _check_review_node 保持同一事实源；否则会出现列表有单、
        # 详情却没有操作按钮的假待办。没有 workflow_instance_id 的历史请假仍按
        # 既有数据范围规则展示，避免把迁移前的可处理记录静默藏掉。
        if ctx.scope_type != "TENANT_ALL":
            actor_id = _verified_actor_id(user)
            if actor_id:
                from app.models import WorkflowTask
                assigned_current_task = select(WorkflowTask.id).where(
                    WorkflowTask.tenant_id == _tid(),
                    WorkflowTask.instance_id == CsLeave.workflow_instance_id,
                    WorkflowTask.node_code == CsLeave.affairs_status,
                    WorkflowTask.assignee_id == actor_id,
                    WorkflowTask.status == "PENDING",
                    WorkflowTask.is_deleted.is_(False),
                ).exists()
                conds.append(or_(CsLeave.workflow_instance_id.is_(None), assigned_current_task))
            else:
                conds.append(CsLeave.workflow_instance_id.is_(None))
        k = str(keyword or "").strip()
        if k:
            conds.append(or_(StudentProfile.real_name.contains(k),
                             StudentProfile.student_no.contains(k)))
        page, page_size = normalize_page(page, page_size)
        total = int(db.scalar(select(func.count()).select_from(CsLeave)
                              .join(StudentProfile, StudentProfile.id == CsLeave.student_id)
                              .where(*conds)) or 0)
        rows = db.scalars(select(CsLeave).join(StudentProfile, StudentProfile.id == CsLeave.student_id)
                          .where(*conds).order_by(CsLeave.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        students = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_({int(x.student_id) for x in rows if x.student_id})
        )).all()} if rows else {}
        out = [_row(x, students.get(int(x.student_id)) if x.student_id else None) for x in rows]
        _resolve_class_names(db, out)  # list_leaves 已有此转换，list_pending 此前遗漏（className 一直回数字 class_id）
        return out, total
