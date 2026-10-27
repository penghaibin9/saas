"""资助业务待办：与持锁业务命令同事务提交，不在查询时补写。"""
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.services.db_service import _tid

ROLE_PRIORITY = {'FUNDING_TEACHER': 0}
REDUCTION_TYPES = {'SUBMITTED': 'FEE_REDUCTION_REVIEW', 'APPROVED': 'FEE_REDUCTION_FULFILL',
                 'RETURNED': 'FEE_REDUCTION_CORRECTION'}
LOAN_TYPES = {'REGISTERED': 'STUDENT_LOAN_SUPPLEMENT', 'RETURNED': 'STUDENT_LOAN_SUPPLEMENT',
              'RECEIPT': 'STUDENT_LOAN_REVIEW', 'VERIFIED': 'STUDENT_LOAN_CONFIRM'}
WORK_STUDY_TYPES = {'APPLIED': 'WORK_STUDY_REVIEW', 'APPROVED': 'WORK_STUDY_ONBOARD'}
_WORKFLOWS = {
    'WORK_STUDY': ('recordId', WORK_STUDY_TYPES, set(), 'studentAffairs.funding.workstudy.manage'),
    'STUDENT_LOAN': ('loanId', LOAN_TYPES, {'REGISTERED', 'RETURNED'}, 'studentAffairs.funding.loan.manage'),
    'FEE_REDUCTION': ('feeId', REDUCTION_TYPES, {'RETURNED'}, 'studentAffairs.funding.reduction.manage'),
}


def _current_duty_allowed(db, user, permission):
    from app.core.permissions import has_permission
    from app.models import Role, UserRole
    from app.services.affairs_funding_service import _uid_int
    from app.services.role_assignment_scope_service import active_role_membership_query
    role_code = str((user or {}).get('currentRoleCode') or '').upper()
    if role_code not in ROLE_PRIORITY or not has_permission(user, permission):
        return False
    query = active_role_membership_query(_tid()).with_only_columns(UserRole.id).where(
        UserRole.user_id == _uid_int(user), Role.role_code == role_code,
    )
    context = str((user or {}).get('activeContextId') or '')
    if context.startswith('role:'):
        if not context[5:].isdigit():
            return False
        query = query.where(Role.id == int(context[5:]))
    return db.scalar(query.limit(1)) is not None


def require_current_receiver(db, row, user, biz_type):
    """业务行已持锁；先核验当前职责/唯一待办，再允许版本和状态写入。"""
    from app.models import UnifiedTodo
    from app.services.affairs_funding_service import _uid_int
    _key, types, student_states, permission = _WORKFLOWS[biz_type]
    if not _current_duty_allowed(db, user, permission):
        raise AppException('NO_PERMISSION', '请切换至有效的资助办理职责')
    pending_type = types.get(row.status)
    # 教师代补回执和在岗考核/终止保留原业务入口，不冒用学生待办或伪造新审批。
    if not pending_type or row.status in student_states:
        return
    todos = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == 'student-affairs',
        UnifiedTodo.source_biz_type == biz_type, UnifiedTodo.source_biz_id == row.id,
        UnifiedTodo.todo_type == pending_type, UnifiedTodo.status == 'PENDING',
        UnifiedTodo.is_deleted.is_(False),
    ).with_for_update()).all()
    if len(todos) != 1 or todos[0].student_id != row.student_id:
        raise AppException('DATA_CONFLICT', '当前办理任务缺失或存在冲突，请先核验受理人；原单已保留')
    if todos[0].assignee_id != _uid_int(user):
        raise AppException('NO_PERMISSION', '当前办理任务未分配给您，请由受理人办理或完成正式交接')


def project_staff_actions(db, user, biz_type, items):
    """批量投影与写门相同的受理边界；只读历史仍保留。"""
    from app.models import UnifiedTodo
    from app.services.affairs_funding_service import _uid_int
    key, types, student_states, permission = _WORKFLOWS[biz_type]
    eligible = _current_duty_allowed(db, user, permission)
    by_record = {}
    if eligible and items:
        for todo in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == 'student-affairs',
            UnifiedTodo.source_biz_type == biz_type,
            UnifiedTodo.source_biz_id.in_([int(item[key]) for item in items]),
            UnifiedTodo.todo_type.in_(set(types.values())), UnifiedTodo.status == 'PENDING',
            UnifiedTodo.is_deleted.is_(False),
        )).all():
            by_record.setdefault((todo.source_biz_id, todo.todo_type), []).append(todo)
    for item in items:
        pending_type = types.get(item['status'])
        allowed = eligible
        if allowed and pending_type and item['status'] not in student_states:
            todos = by_record.get((int(item[key]), pending_type), [])
            allowed = len(todos) == 1 and todos[0].assignee_id == _uid_int(user) and str(todos[0].student_id) == item['studentId']
        if not allowed and item.get('allowedActions'):
            item['allowedActions'] = []
            item['actionBlockReason'] = '当前职责不能办理，或该记录尚未分配给您，请核对受理安排'
    return items


def _eligible_assignees(db, student_id, permission):
    from app.models import User
    from app.core.permissions import has_permission
    from app.services.affairs_assignee_service import _active_user_ids_for_roles
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.services.auth_service_db import _claims, _role_contexts
    from app.models import StudentProfile

    student = db.scalar(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.id == student_id,
        StudentProfile.is_deleted.is_(False),
    ))
    if not student:
        raise AppException('DATA_NOT_FOUND', '申请学生不存在')
    ids = _active_user_ids_for_roles(db, set(ROLE_PRIORITY))
    eligible = {}
    for user in db.scalars(select(User).where(
        User.tenant_id == _tid(), User.id.in_(ids or {-1}),
        User.status == 'ACTIVE', User.is_deleted.is_(False), User.user_type != 'STUDENT',
    )).all():
        contexts = _role_contexts(db, user)
        for context in contexts:
            priority = ROLE_PRIORITY.get(context['roleCode'])
            if priority is None:
                continue
            claims = _claims(db, user, context, contexts, 'PC')
            if not has_permission(claims, permission):
                continue
            allowed, _ = _allowed_class_ids(db, claims)
            if allowed is None or student.class_id in allowed:
                eligible[int(user.id)] = min(priority, eligible.get(int(user.id), priority))
    return eligible


def _sync(db, row, *, biz_type, types, student_states, permission, title):
    """调用方已锁申请行（新建需 flush）；不 commit，失败回滚整个业务命令。"""
    from app.models import UnifiedTodo

    if int(row.tenant_id) != _tid():
        raise AppException('NO_PERMISSION', '申请不属于当前学校')
    todos = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == 'student-affairs',
        UnifiedTodo.source_biz_type == biz_type, UnifiedTodo.source_biz_id == row.id,
        UnifiedTodo.todo_type.in_(tuple(types.values())),
        UnifiedTodo.is_deleted.is_(False),
    ).with_for_update()).all()
    pending_type = types.get(row.status)
    assignee = None
    if row.status in student_states:
        from app.services.student_account_link_service import resolve_user_id_for_student
        assignee = resolve_user_id_for_student(db, tenant_id=_tid(), student_id=row.student_id)
        if not assignee:
            raise AppException('ASSIGNEE_NOT_CONFIGURED', '学生未绑定有效账号，无法接收补正待办，请先核对学生账号')
    elif pending_type:
        eligible = _eligible_assignees(db, row.student_id, permission)
        if not eligible:
            raise AppException('ASSIGNEE_NOT_CONFIGURED', '未配置可办理该学生业务的受理人，请检查资助或学工岗位权限与数据范围')
        # 同单仍由有效原受理人继续，避免退回重提或批准后无故换人。
        previous = next((t.assignee_id for t in todos if t.assignee_id in eligible), None)
        if previous:
            assignee = previous
        else:
            loads = dict(db.execute(select(UnifiedTodo.assignee_id, func.count()).where(
                UnifiedTodo.tenant_id == _tid(), UnifiedTodo.status == 'PENDING',
                UnifiedTodo.assignee_id.in_(eligible), UnifiedTodo.is_deleted.is_(False),
            ).group_by(UnifiedTodo.assignee_id)).all())
            assignee = min(eligible, key=lambda uid: (eligible[uid], loads.get(uid, 0), uid))
    now = datetime.utcnow()
    current = None
    for todo in todos:
        if todo.todo_type == pending_type:
            current = todo
            continue
        if todo.status == 'PENDING':
            todo.status = 'CANCELLED' if row.status == 'WITHDRAWN' else 'DONE'
            todo.completed_at = now if todo.status == 'DONE' else None
            todo.version = int(todo.version or 0) + 1
    if not pending_type:
        return
    if current is None:
        # The shared DATETIME column stores whole seconds. Truncate before insert:
        # MySQL rounding up would hide a fresh task behind the reader's asOf fence.
        db.add(UnifiedTodo(tenant_id=_tid(), source_module='student-affairs',
                          source_biz_type=biz_type, source_biz_id=row.id,
                          todo_type=pending_type, assignee_id=assignee, student_id=row.student_id,
                          title=title, status='PENDING', created_at=now.replace(microsecond=0)))
    elif current.status != 'PENDING' or current.assignee_id != assignee or current.title != title:
        current.assignee_id, current.title, current.status = assignee, title, 'PENDING'
        current.completed_at = None
        current.version = int(current.version or 0) + 1


def sync_reduction_todos(db, row):
    label = '学费减免' if row.item_type == 'REDUCTION' else '临时困难补助'
    suffix = {'SUBMITTED': '待审核', 'APPROVED': '待落实', 'RETURNED': '待补正'}.get(row.status, '')
    _sync(db, row, biz_type='FEE_REDUCTION', types=REDUCTION_TYPES, student_states={'RETURNED'},
          permission='studentAffairs.funding.reduction.manage', title=label + suffix)


def sync_loan_todos(db, row):
    suffix = {'REGISTERED': '待补回执', 'RETURNED': '待补正', 'RECEIPT': '待核验',
              'VERIFIED': '待确认台账'}.get(row.status, '')
    _sync(db, row, biz_type='STUDENT_LOAN', types=LOAN_TYPES, student_states={'REGISTERED', 'RETURNED'},
          permission='studentAffairs.funding.loan.manage', title='助学贷款' + suffix)


def sync_work_study_todos(db, row):
    # 月度考核尚无独立待办状态，不因上岗就伪造一条到期考核任务。
    types = WORK_STUDY_TYPES
    suffix = {'APPLIED': '待录用审核', 'APPROVED': '待核验协议并上岗'}.get(row.status, '')
    _sync(db, row, biz_type='WORK_STUDY', types=types, student_states=set(),
          permission='studentAffairs.funding.workstudy.manage', title='勤工助学' + suffix)
