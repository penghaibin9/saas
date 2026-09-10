"""Mobile teacher warning detail/follow-up: explicit responsibility scope.

Reuse canonical warning + intervention records and their parent-child receipt.
Do not expose PC warning management permissions to ordinary teachers.
"""
from sqlalchemy import and_, exists, false, func, or_, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import AppException, no_permission
from app.core.permissions import has_permission
from app.services.db_service import _tid, session
from . import academic_affairs_warning_service as canonical


def _staff(user):
    from app.services.mobile_teacher_service import _require_teacher
    u = _require_teacher(user)
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


def list_warnings(user, *, page=1, page_size=50, status=None, level=None):
    from app.models import AcademicWarning, AcademicStudent, UnifiedTodo
    from app.services.academic_service import _warn_row
    if not 1 <= int(page) or not 1 <= int(page_size) <= 100:
        raise AppException("VALIDATION_ERROR", "分页参数非法")
    if status is not None and status not in canonical.STATUS_LABELS:
        raise AppException("VALIDATION_ERROR", "预警状态非法")
    if level is not None and level not in canonical.LEVEL_LABELS:
        raise AppException("VALIDATION_ERROR", "预警等级非法")
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
        if level is not None:
            q = q.where(AcademicWarning.level == level)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.execute(q.order_by(AcademicWarning.id.desc())
                          .offset((int(page) - 1) * int(page_size)).limit(int(page_size))).all()
        items = [_warn_row(warning, student) for warning, student in rows]
        return {"hasData": total > 0, "list": items, "total": total, "module": "academic",
                "page": int(page), "pageSize": int(page_size),
                "hasMore": int(page) * int(page_size) < total}


def require_warning_scope(db, user, warning, *, writing=False):
    """Called inside canonical session; lock order Warning -> User -> assigned Todo."""
    from app.models import UnifiedTodo, AcademicStudent
    u, account = _account(db, user, writing=writing)
    if warning.tenant_id != _tid() or warning.is_deleted:
        raise no_data_scope("该预警不在当前学校")
    assigned_query = select(UnifiedTodo.id).where(
        *_assignment_conditions(int(warning.id), account.id),
    )
    if writing:
        assigned_query = assigned_query.with_for_update(read=True)
    if db.scalar(assigned_query.limit(1)) is not None:
        return
    if writing and not has_permission(u, "academicAffairs.warning.handle"):
        raise no_data_scope("当前预警未正式分配给本人跟进")
    # Stable scope resolver, NOT stats._resolve_scope's ACADEMIC_TEACHER all-school shortcut.
    ctx = build_affairs_context(u, db)
    student = db.scalar(select(AcademicStudent).where(
        AcademicStudent.id == int(warning.acad_student_id),
        AcademicStudent.tenant_id == _tid(), AcademicStudent.is_deleted.is_(False),
    ))
    if student is None or not student.student_id:
        raise no_data_scope("该预警未关联范围内正式学生")
    ctx.require_student(db, int(student.student_id))


def detail(user, warning_id):
    return canonical.get_warning_detail(_staff(user), warning_id, mobile_teacher_scope=True)


def add_intervention(user, warning_id, body):
    return canonical.add_intervention(
        _staff(user), warning_id, body.way, body.content,
        body.result or "", body.nextPlan or "", mobile_teacher_scope=True,
    )
