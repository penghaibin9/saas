"""Mobile teacher warning detail/follow-up: explicit responsibility scope.

Reuse canonical warning + intervention records and their parent-child receipt.
Do not expose PC warning management permissions to ordinary teachers.
"""
from sqlalchemy import and_, exists, false, func, or_, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import AppException, no_permission
from app.core.permissions import has_permission
from app.core.security import require_mobile_staff
from app.services.db_service import _tid, session
from . import academic_affairs_warning_service as canonical

# The mobile queue, teacher home count and student-360 projection must agree on
# what remains actionable.  `ACTIVE` is a historical status still present in
# older rows, so keep it readable/actionable without letting a CLOSED row leak
# back into a "待处理" page merely because its record_status stays ACTIVE.
_OPEN_WARNING_STATUSES = frozenset({"PENDING_HANDLE", "PROCESSING", "ESCALATED", "ACTIVE"})
_ACTIVE_WRITE_STATUSES = frozenset({"PENDING_HANDLE", "PROCESSING", "ACTIVE"})
_LEGACY_TYPE_LABELS = {
    "MULTI_FAIL": "多门挂科",
    "CREDIT_GAP": "学分不足",
    "GRADE_DROP": "成绩持续下滑",
    "ATTENDANCE": "出勤异常",
    "GRAD_RISK": "毕业资格风险",
}


def _staff(user):
    u = require_mobile_staff(user)
    if not (has_permission(u, "academicAffairs.process.view")
            or has_permission(u, "academicAffairs.warning.view")):
        raise no_permission("当前身份无权办理移动学业预警")
    return u


def _account(db, user, *, writing=False):
    from app.models import User
    u = _staff(user)
    raw = str(u.get("userId") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    elif raw.startswith("u_"):
        raw = raw[2:]
    if not raw.isdigit():
        raise no_permission("当前账号缺少可核验的正式用户身份")
    account_query = select(User).where(
        User.id == int(raw), User.tenant_id == _tid(),
        User.is_deleted.is_(False), User.status == "ACTIVE",
    )
    if writing:
        account_query = account_query.with_for_update(read=True)
    account = db.scalar(account_query)
    from app.core.security import MOBILE_STAFF_USER_TYPES
    if not account or str(account.user_type or "").upper() not in MOBILE_STAFF_USER_TYPES:
        raise no_permission("当前教职工账号不可用")
    return u, account


def _assignment_conditions(warning_id, account_id):
    from app.models import UnifiedTodo
    return (
        UnifiedTodo.tenant_id == _tid(),
        UnifiedTodo.source_module == "academic-affairs",
        # Canonical assign_warning historically omitted this optional column.
        # Full authoritative unique key below remains mandatory; other types deny.
        or_(UnifiedTodo.source_biz_type == "ACAD_WARNING", UnifiedTodo.source_biz_type.is_(None)),
        UnifiedTodo.source_biz_id == warning_id,
        UnifiedTodo.todo_type == canonical.TODO_TYPE,
        UnifiedTodo.assignee_id == int(account_id),
        UnifiedTodo.status == "PENDING", UnifiedTodo.is_deleted.is_(False),
    )


def _profile_scope_ids(db, user):
    from app.models import StudentProfile
    ctx = build_affairs_context(user, db)
    q = select(StudentProfile.id).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
    )
    if ctx.scope_type == "TENANT_ALL":
        return q
    if ctx.scope_type == "STUDENT":
        return q.where(StudentProfile.id.in_(ctx.student_ids | ctx.psychology_student_ids))
    if ctx.scope_type in {"NONE", "SELF", "DORM_BUILDING"}:
        return q.where(false())
    return q.where(StudentProfile.class_id.in_(ctx.allowed_class_ids(db) or set()))


def _present_list_item(item):
    """Never pass a legacy enum through to the mobile UI as customer text."""
    result = dict(item or {})
    type_code = str(result.get("type") or "").upper()
    source_code = str(result.get("sourceCode") or "").upper()
    result["typeLabel"] = (
        canonical.SOURCE_LABELS.get(source_code)
        or canonical.SOURCE_LABELS.get(type_code)
        or _LEGACY_TYPE_LABELS.get(type_code)
        or "学业预警"
    )
    result["levelLabel"] = canonical.LEVEL_LABELS.get(
        str(result.get("level") or "").upper(), "风险等级待确认",
    )
    result["statusLabel"] = canonical.STATUS_LABELS.get(
        str(result.get("status") or "").upper(), "状态待确认",
    )
    return result


def list_warnings(user, *, page=1, page_size=50, status=None, level=None, pending_only=False):
    from app.models import AcademicWarning, AcademicStudent, UnifiedTodo
    from app.services.academic_service import _warn_row
    if not 1 <= int(page) or not 1 <= int(page_size) <= 100:
        raise AppException("VALIDATION_ERROR", "分页参数非法")
    if status is not None and status not in canonical.STATUS_LABELS:
        raise AppException("VALIDATION_ERROR", "预警状态非法")
    if level is not None and level not in canonical.LEVEL_LABELS:
        raise AppException("VALIDATION_ERROR", "预警等级非法")
    if pending_only and status is not None:
        raise AppException("VALIDATION_ERROR", "待处理筛选不能同时指定单一预警状态")
    with session() as db:
        u, account = _account(db, user)
        assigned = exists(select(UnifiedTodo.id).where(
            *_assignment_conditions(AcademicWarning.id, account.id),
        ))
        scope_student_ids = _profile_scope_ids(db, u)
        visible = or_(assigned, AcademicStudent.student_id.in_(scope_student_ids))
        q = select(AcademicWarning, AcademicStudent).outerjoin(
            AcademicStudent, and_(
                AcademicStudent.id == AcademicWarning.acad_student_id,
                AcademicStudent.tenant_id == AcademicWarning.tenant_id,
                AcademicStudent.is_deleted.is_(False),
            ),
        ).where(
            AcademicWarning.tenant_id == _tid(),
            AcademicWarning.is_deleted.is_(False),
            AcademicWarning.record_status == "ACTIVE", visible,
        )
        if status is not None:
            q = q.where(AcademicWarning.status == status)
        elif pending_only:
            q = q.where(AcademicWarning.status.in_(_OPEN_WARNING_STATUSES))
        if level is not None:
            q = q.where(AcademicWarning.level == level)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.execute(q.order_by(AcademicWarning.id.desc())
                          .offset((int(page) - 1) * int(page_size)).limit(int(page_size))).all()
        items = [_present_list_item(_warn_row(warning, student)) for warning, student in rows]
        return {"hasData": total > 0, "list": items, "total": total, "module": "academic",
                "page": int(page), "pageSize": int(page_size),
                "hasMore": int(page) * int(page_size) < total}


def pending_summary(user):
    """One bounded, scope-safe queue query for the teacher workbench.

    The client gets the authoritative total and only the first actionable target;
    it must not fetch a broad page then locally decide which records are pending.
    """
    queue = list_warnings(user, page=1, page_size=1, pending_only=True)
    first = (queue.get("list") or [None])[0]
    return {
        "total": int(queue.get("total") or 0),
        "first": first,
        "hasData": bool(queue.get("hasData")),
    }


def require_warning_scope(db, user, warning, *, writing=False):
    """Called inside canonical session; lock order Warning -> User -> assigned Todo."""
    from app.models import UnifiedTodo, AcademicStudent
    u, account = _account(db, user, writing=writing)
    if warning.tenant_id != _tid() or warning.is_deleted:
        raise no_data_scope("该预警不在当前学校")
    # A pending todo proves responsibility only.  It must never grant a read-only
    # teacher the warning handling capability.
    if writing and not has_permission(u, "academicAffairs.warning.handle"):
        raise no_permission("当前身份仅可查看，不能办理学业预警")
    assigned_query = select(UnifiedTodo.id).where(
        *_assignment_conditions(int(warning.id), account.id),
    )
    if writing:
        assigned_query = assigned_query.with_for_update(read=True)
    if db.scalar(assigned_query.limit(1)) is not None:
        return
    # Stable scope resolver, NOT stats._resolve_scope's ACADEMIC_TEACHER all-school shortcut.
    ctx = build_affairs_context(u, db)
    student = db.scalar(select(AcademicStudent).where(
        AcademicStudent.id == int(warning.acad_student_id),
        AcademicStudent.tenant_id == _tid(), AcademicStudent.is_deleted.is_(False),
    ))
    if student is None or not student.student_id:
        raise no_data_scope("该预警未关联范围内正式学生")
    ctx.require_student(db, int(student.student_id))


def _write_actions(user, warning_id):
    """Return server-authoritative mobile actions for one already-readable warning."""
    u = _staff(user)
    if not has_permission(u, "academicAffairs.warning.handle"):
        return []
    with session() as db:
        warning = canonical._warning_or_404(db, warning_id)
        require_warning_scope(db, u, warning, writing=True)
        if str(warning.record_status or "").upper() == "VOIDED":
            return []
        if str(warning.status or "").upper() not in _ACTIVE_WRITE_STATUSES:
            return []
    return ["FOLLOW_UP", "CLOSE", "ESCALATE"]


def _present_detail(payload, actions):
    """Keep the mobile DTO Chinese and self-contained without changing the canonical model."""
    result = dict(payload or {})
    warning = dict(result.get("warning") or {})
    student = dict(result.get("student") or {})
    source_code = str(warning.get("sourceCode") or "").upper()
    warn_type = str(warning.get("warnType") or warning.get("type") or "").upper()
    warning["studentName"] = student.get("studentName") or warning.get("studentName") or warning.get("name") or "学生信息待核对"
    warning["name"] = warning["studentName"]
    warning["className"] = student.get("className") or warning.get("className") or "班级待核对"
    # `sourceLabel` from historical projections may equal an unrecognised
    # machine code.  Mobile must never render that code as a user-facing type.
    warning["typeLabel"] = (canonical.SOURCE_LABELS.get(source_code)
                            or _LEGACY_TYPE_LABELS.get(warn_type)
                            or "学业预警")
    warning["levelLabel"] = canonical.LEVEL_LABELS.get(
        str(warning.get("level") or "").upper(), "风险等级待确认")
    warning["statusLabel"] = canonical.STATUS_LABELS.get(
        str(warning.get("status") or "").upper(), "状态待确认")
    warning["allowedActions"] = list(actions)
    result["warning"] = warning
    result["allowedActions"] = list(actions)
    for item in result.get("interventions") or []:
        item["wayLabel"] = {
            "TALK": "当面谈话", "PHONE": "电话联系", "FAMILY": "家校联系", "PLAN": "帮扶计划",
        }.get(str(item.get("way") or "").upper(), "跟进记录")
    return result


def detail(user, warning_id, *, intervention_page=1, intervention_page_size=20):
    payload = canonical.get_warning_detail(_staff(user), warning_id, mobile_teacher_scope=True,
                                           intervention_page=intervention_page, intervention_page_size=intervention_page_size)
    return _present_detail(payload, _write_actions(user, warning_id))


def add_intervention(user, warning_id, body, command_key=None):
    return canonical.add_intervention(
        _staff(user), warning_id, body.way, body.content,
        body.result or "", body.nextPlan or "", mobile_teacher_scope=True, command_key=command_key,
    )


def handle(user, warning_id, action, note=""):
    action = str(action or "").upper()
    u = _staff(user)
    if action == "CLOSE":
        return canonical.close_warning(u, warning_id, note, mobile_teacher_scope=True)
    if action == "ESCALATE":
        return canonical.escalate_warning(u, warning_id, note, mobile_teacher_scope=True)
    raise AppException("VALIDATION_ERROR", "action 必须是 CLOSE/ESCALATE")
