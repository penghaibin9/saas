"""包 5：学籍异动详情、学期和工作流受理人安全层。

本模块先关闭三个可独立止血的问题：
1. 详情读取必须按目标学生做对象级范围裁决；
2. 新异动创建时在同一 ORM flush 中冻结学期编码，审批必须校验异动所属学期，
   不再用“当前学期”替代历史事实；
3. 工作流任务禁止 assignee_id=0。学院节点优先使用学院教学秘书，其他节点按
   有效权限成员解析；没有唯一真实受理人时 fail-closed，禁止生成无人任务。

完整的 expectedVersion、最终状态条件更新和并发终审 MySQL 证明仍由包 5 后续施工完成。
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime
from functools import wraps

from sqlalchemy import event, or_, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_change_service as change_service


_ORIGINAL_SUBMIT = getattr(change_service, "_package5_original_submit", change_service.submit)
_ORIGINAL_REVIEW = getattr(change_service, "_package5_original_review", change_service.review)
_ORIGINAL_ASSIGNEE = getattr(
    change_service,
    "_package5_original_assignee_for",
    change_service._assignee_for,
)

_SELECTED_TERM_CODE: ContextVar[str | None] = ContextVar(
    "aa_status_change_selected_term_code",
    default=None,
)
_CHANGE_CONTEXT: ContextVar[dict | None] = ContextVar(
    "aa_status_change_assignee_context",
    default=None,
)


def _canonical_term_code(term) -> str:
    year = str(getattr(term, "year_code", "") or "").strip()
    number = getattr(term, "term_no", None)
    if not year or number is None:
        raise AppException(
            "TERM_IDENTITY_INVALID",
            "学期缺少年份或学期序号，无法冻结异动所属学期",
            http_status=409,
        )
    return f"{year}-{int(number)}"


def _current_writable_term(db, requested_code=None):
    from app.models import AaTerm

    rows = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == _tid(),
        AaTerm.is_current.is_(True),
        AaTerm.is_deleted.is_(False),
    ).with_for_update()).all()
    if len(rows) != 1:
        raise AppException(
            "CURRENT_TERM_NOT_UNIQUE",
            "当前学期必须且只能配置一条，禁止创建无法归属学期的异动",
            details={"count": len(rows)},
            http_status=409,
        )
    term = rows[0]
    code = _canonical_term_code(term)
    requested = str(requested_code or "").strip()
    if requested and requested != code:
        raise AppException(
            "TERM_MISMATCH",
            "异动申请学期与学校当前学期不一致",
            details={"requestedTermCode": requested, "currentTermCode": code},
            http_status=409,
        )
    if str(term.status or "").upper() == "ARCHIVED":
        raise AppException("TERM_ARCHIVED", "当前学期已归档封存，禁止新建异动", http_status=409)
    return term


def _term_for_change(db, term_code):
    from app.models import AaTerm

    code = str(term_code or "").strip()
    if not code:
        raise AppException(
            "STATUS_CHANGE_TERM_MISSING",
            "异动单未冻结所属学期，禁止继续审批；请先执行历史数据补录",
            http_status=409,
        )
    rows = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    )).all()
    matches = [row for row in rows if _canonical_term_code(row) == code]
    if len(matches) != 1:
        raise AppException(
            "STATUS_CHANGE_TERM_INVALID",
            "异动单所属学期不存在或不唯一，禁止继续审批",
            details={"termCode": code, "count": len(matches)},
            http_status=409,
        )
    term = matches[0]
    if str(term.status or "").upper() == "ARCHIVED":
        raise AppException("TERM_ARCHIVED", "该异动所属学期已归档封存，禁止继续审批", http_status=409)
    return term


def _freeze_term_code(_mapper, _connection, target) -> None:
    selected = _SELECTED_TERM_CODE.get()
    if not selected:
        return
    existing = str(getattr(target, "term_code", "") or "").strip()
    if existing and existing != selected:
        raise AppException(
            "TERM_MISMATCH",
            "异动单学期在写入过程中发生冲突",
            details={"rowTermCode": existing, "selectedTermCode": selected},
            http_status=409,
        )
    target.term_code = selected


def require_change_scope(db, user: dict | None, change) -> None:
    current = user or {}
    context = build_affairs_context(current, db)
    if context.scope_type == "SELF":
        own_student_id = current.get("studentId") or current.get("student_id")
        try:
            allowed = int(own_student_id) == int(change.student_id)
        except (TypeError, ValueError):
            allowed = False
        if not allowed:
            raise no_data_scope("该学籍异动不属于当前学生本人")
        return
    context.require_student(db, int(change.student_id))


def _permission_candidate_ids(db, permission_code: str) -> list[int]:
    from app.models import Permission, Role, RolePermission, User, UserRole

    stmt = (
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            User.tenant_id == _tid(),
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
            UserRole.tenant_id == _tid(),
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
            Role.tenant_id == _tid(),
            Role.status == "ACTIVE",
            Role.is_deleted.is_(False),
            RolePermission.tenant_id == _tid(),
            RolePermission.status == "ACTIVE",
            RolePermission.is_deleted.is_(False),
            Permission.permission_code == permission_code,
        )
        .distinct()
        .order_by(User.id)
    )
    return [int(value) for value in db.scalars(stmt).all()]


def _active_user(db, user_id: int | None):
    from app.models import User

    if not user_id:
        return None
    user = db.get(User, int(user_id))
    if not user or user.tenant_id != _tid() or user.is_deleted or user.status != "ACTIVE":
        return None
    return user


def _pick_unique_assignee(candidates: list[int], node: str) -> int:
    unique = sorted({int(value) for value in candidates if int(value) > 0})
    if len(unique) != 1:
        raise AppException(
            "WORKFLOW_ASSIGNEE_UNRESOLVED",
            "审批节点没有配置唯一真实受理人，禁止生成无人或随机任务",
            details={"node": node, "candidateUserIds": unique},
            http_status=409,
        )
    return unique[0]


def _target_college_id(db, node: str, student_id: int | None) -> int | None:
    ctx = _CHANGE_CONTEXT.get() or {}
    if node == "IN_COLLEGE_REVIEW":
        value = ctx.get("to_college_id")
    else:
        value = ctx.get("from_college_id")
    if value:
        return int(value)

    from app.models import StudentProfile
    student = db.get(StudentProfile, int(student_id)) if student_id else None
    if student and student.tenant_id == _tid() and not student.is_deleted and student.college_id:
        return int(student.college_id)
    return None


def strict_assignee_for(db, node, student_id):
    """解析稳定受理人；任何节点都不允许返回 0。"""
    if node == "COUNSELOR_REVIEW":
        assignee = int(_ORIGINAL_ASSIGNEE(db, node, student_id) or 0)
        if assignee > 0 and _active_user(db, assignee):
            return assignee
        raise AppException(
            "WORKFLOW_ASSIGNEE_UNRESOLVED",
            "学生行政班未配置有效辅导员，禁止发起无人审批任务",
            details={"node": node, "studentId": str(student_id or "")},
            http_status=409,
        )

    permission_code = change_service._NODE_PERM.get(node)
    if not permission_code:
        raise AppException(
            "WORKFLOW_NODE_INVALID",
            "学籍异动审批节点未配置权限合同",
            details={"node": node},
            http_status=409,
        )
    candidates = _permission_candidate_ids(db, permission_code)

    if node != "AA_OFFICE_FINAL":
        from app.models import College, StaffAssignment

        college_id = _target_college_id(db, node, student_id)
        if not college_id:
            raise AppException(
                "WORKFLOW_ASSIGNEE_UNRESOLVED",
                "异动单未绑定审批学院，禁止生成学院审批任务",
                details={"node": node},
                http_status=409,
            )
        college = db.get(College, int(college_id))
        if not college or college.tenant_id != _tid() or college.is_deleted:
            raise AppException("DATA_CONFLICT", "异动审批学院不存在或已停用", http_status=409)

        if college.secretary_id and int(college.secretary_id) in candidates:
            if _active_user(db, int(college.secretary_id)):
                return int(college.secretary_id)

        now = datetime.utcnow()
        assignment_ids = db.scalars(select(StaffAssignment.user_id).where(
            StaffAssignment.tenant_id == _tid(),
            StaffAssignment.org_type == "COLLEGE",
            StaffAssignment.org_node_id == int(college_id),
            StaffAssignment.assignment_type.in_(("SECRETARY", "LEADER")),
            StaffAssignment.status == "ACTIVE",
            StaffAssignment.is_deleted.is_(False),
            StaffAssignment.effective_at <= now,
            or_(StaffAssignment.expires_at.is_(None), StaffAssignment.expires_at > now),
        ).order_by(StaffAssignment.is_primary.desc(), StaffAssignment.user_id)).all()
        allowed = [int(uid) for uid in assignment_ids if int(uid) in candidates and _active_user(db, int(uid))]
        return _pick_unique_assignee(allowed, node)

    return _pick_unique_assignee(candidates, node)


def _change_snapshot(change) -> dict:
    return {
        "student_id": int(change.student_id),
        "from_college_id": int(change.from_college_id) if change.from_college_id else None,
        "to_college_id": int(change.to_college_id) if change.to_college_id else None,
    }


def _current_user_id(user: dict | None) -> int:
    current = user or get_current_user_ctx() or {}
    value = current.get("userId") or current.get("id")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise no_permission("当前登录身份缺少稳定 userId，禁止审批") from exc
    if parsed <= 0:
        raise no_permission("当前登录身份缺少稳定 userId，禁止审批")
    return parsed


def _claim_or_validate_pending_task(db, change, user: dict | None) -> None:
    from app.models import UnifiedTodo, WorkflowInstance, WorkflowTask

    if not change.workflow_instance_id:
        raise AppException("WORKFLOW_INSTANCE_MISSING", "异动单缺少工作流实例", http_status=409)
    instance = db.get(WorkflowInstance, int(change.workflow_instance_id))
    if not instance or instance.tenant_id != _tid() or instance.is_deleted:
        raise AppException("WORKFLOW_INSTANCE_MISSING", "异动工作流实例不存在", http_status=409)

    task = db.scalars(select(WorkflowTask).where(
        WorkflowTask.tenant_id == _tid(),
        WorkflowTask.instance_id == instance.id,
        WorkflowTask.node_code == change.current_node,
        WorkflowTask.status == "PENDING",
        WorkflowTask.is_deleted.is_(False),
    ).with_for_update()).first()
    if not task:
        raise AppException("APPROVAL_VERSION_CONFLICT", "当前审批任务不存在或已被处理", http_status=409)

    uid = _current_user_id(user)
    assignee = int(task.assignee_id or 0)
    if assignee <= 0:
        token = _CHANGE_CONTEXT.set(_change_snapshot(change))
        try:
            assignee = strict_assignee_for(db, change.current_node, change.student_id)
        finally:
            _CHANGE_CONTEXT.reset(token)
        task.assignee_id = assignee
        for todo in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.source_module == "academic-affairs",
            UnifiedTodo.source_biz_id == int(change.id),
            UnifiedTodo.todo_type == "AA_STATUS_APPROVAL",
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.is_deleted.is_(False),
        ).with_for_update()).all():
            if int(todo.assignee_id or 0) <= 0:
                todo.assignee_id = assignee
                todo.version = int(todo.version or 0) + 1

    if assignee != uid:
        raise no_permission("当前审批任务已明确分配给其他受理人")


@wraps(_ORIGINAL_SUBMIT)
def strict_submit(body, user) -> dict:
    requested_code = getattr(body, "termCode", None)
    with session() as db:
        term = _current_writable_term(db, requested_code)
        term_code = _canonical_term_code(term)
    token = _SELECTED_TERM_CODE.set(term_code)
    try:
        return _ORIGINAL_SUBMIT(body, user)
    finally:
        _SELECTED_TERM_CODE.reset(token)


@wraps(_ORIGINAL_REVIEW)
def strict_review(sc_id, user, action, reason="") -> dict:
    with session() as db:
        change, _student = change_service._load(db, sc_id)
        _term_for_change(db, change.term_code)
        _claim_or_validate_pending_task(db, change, user)
        snapshot = _change_snapshot(change)
        db.commit()
    token = _CHANGE_CONTEXT.set(snapshot)
    try:
        return _ORIGINAL_REVIEW(sc_id, user, action, reason)
    finally:
        _CHANGE_CONTEXT.reset(token)


def strict_get_change(sc_id, user) -> dict:
    with session() as db:
        change, student = change_service._load(db, sc_id)
        require_change_scope(db, user, change)
        return change_service._row(change, student)


strict_submit._status_change_safety_guard = True
strict_review._status_change_safety_guard = True
strict_get_change._status_change_safety_guard = True
strict_assignee_for._status_change_safety_guard = True


def install() -> None:
    """幂等安装到学籍异动公开服务。"""
    from app.models import AaStatusChange

    if not event.contains(AaStatusChange, "before_insert", _freeze_term_code):
        event.listen(AaStatusChange, "before_insert", _freeze_term_code)

    if not hasattr(change_service, "_package5_original_submit"):
        change_service._package5_original_submit = change_service.submit
    if not hasattr(change_service, "_package5_original_review"):
        change_service._package5_original_review = change_service.review
    if not hasattr(change_service, "_package5_original_assignee_for"):
        change_service._package5_original_assignee_for = change_service._assignee_for

    if not getattr(change_service.submit, "_status_change_safety_guard", False):
        change_service.submit = strict_submit
    if not getattr(change_service.review, "_status_change_safety_guard", False):
        change_service.review = strict_review
    if not getattr(change_service.get_change, "_status_change_safety_guard", False):
        change_service.get_change = strict_get_change
    if not getattr(change_service._assignee_for, "_status_change_safety_guard", False):
        change_service._assignee_for = strict_assignee_for
