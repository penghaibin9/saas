"""教务责任实时投影；只读组织、任职和授课关系，不授予任何业务权限。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select

from app.services.db_service import _tid


def _cached(cache, key, loader):
    """仅复用调用方显式传入的单次只读请求缓存；不持久化身份或权限。"""
    if cache is None:
        return loader()
    scoped_key = ("RESPONSIBILITY", _tid(), *key)
    if scoped_key not in cache:
        cache[scoped_key] = loader()
    return cache[scoped_key]


def _permission_holders(db, permission_code, cache):
    from .academic_affairs_grade_task_assignee_guard import _runtime_permission_holder_ids
    return set(_runtime_permission_holder_ids(db, permission_code, **({"cache": cache} if cache is not None else {})))


def _active_assignment(row, now):
    return (not row.is_deleted and row.status == "ACTIVE" and row.effective_at <= now
            and (row.expires_at is None or row.expires_at > now))


def _choose_assignees(assignments, users, assignment_types, secretary_id, now):
    """有任职历史的岗位不再从旧秘书字段复活已到期、撤销或禁用的账号。"""
    active_users = {int(row.id): row for row in users
                    if not row.is_deleted and row.status == "ACTIVE"}
    for kind in assignment_types:
        eligible = [row for row in assignments
                    if row.assignment_type == kind and _active_assignment(row, now)
                    and int(row.user_id) in active_users]
        if eligible:
            ids = sorted({int(row.user_id) for row in eligible})
            return [active_users[uid] for uid in ids], "STAFF_ASSIGNMENT", ""
    if secretary_id and "SECRETARY" in assignment_types:
        history = [row for row in assignments if row.assignment_type == "SECRETARY"]
        if not history and int(secretary_id) in active_users:
            return [active_users[int(secretary_id)]], "COLLEGE_SECRETARY", ""
    expired = any(row.expires_at is not None and row.expires_at <= now for row in assignments)
    return [], "UNRESOLVED", "ASSIGNMENT_EXPIRED" if expired else "RESPONSIBILITY_UNRESOLVED"


def _payload(org_type, org_id, org_name, assignment_types, users=(), *, source="UNRESOLVED",
             reason="", role_codes=()):
    return {
        "orgType": org_type, "orgId": str(org_id) if org_id is not None else None,
        "orgName": org_name, "assignmentTypes": list(assignment_types),
        "roleCodes": list(role_codes), "assigneeUserIds": [str(row.id) for row in users],
        "assigneeNames": [row.real_name for row in users], "resolved": bool(users),
        "source": source, "reason": reason,
    }


def resolve_organization(db, org_type, org_id, *, assignment_types=("SECRETARY", "LEADER"),
                         permission_code=None, now=None, cache=None):
    """任职为第一真值，学院秘书字段仅兼容无该岗位任职记录的旧学校。"""
    from app.models import College, Major, StaffAssignment, User

    now = now or datetime.utcnow()
    model = {"COLLEGE": College, "MAJOR": Major}.get(org_type)
    org = _cached(cache, ("ORG", org_type, int(org_id)), lambda: db.scalar(select(model).where(
        model.tenant_id == _tid(), model.id == int(org_id),
        model.is_deleted.is_(False), model.status == "ACTIVE",
    ))) if model and org_id else None
    name = (org.college_name if org_type == "COLLEGE" else org.major_name) if org else "责任组织未配置"
    if not org:
        return _payload(org_type, org_id, name, assignment_types,
                        reason="责任组织不存在、已停用或不属于当前学校")
    assignments = _cached(cache, ("APPOINTMENTS", org_type, int(org_id), tuple(assignment_types)), lambda: db.scalars(select(StaffAssignment).where(
        StaffAssignment.tenant_id == _tid(), StaffAssignment.org_type == org_type,
        StaffAssignment.org_node_id == int(org_id),
        StaffAssignment.assignment_type.in_(assignment_types),
    )).all())
    secretary_id = getattr(org, "secretary_id", None)
    user_ids = {int(row.user_id) for row in assignments}
    if secretary_id:
        user_ids.add(int(secretary_id))
    users = _cached(cache, ("USERS", tuple(sorted(user_ids))), lambda: db.scalars(select(User).where(
        User.tenant_id == _tid(), User.id.in_(user_ids or {-1}),
        User.status == "ACTIVE", User.is_deleted.is_(False),
    )).all())
    if permission_code:
        holders = _permission_holders(db, permission_code, cache)
        users = [row for row in users if int(row.id) in holders]
        users = _scoped_holders(db, users, org_type, org, permission_code, cache=cache)
    selected, source, reason_code = _choose_assignees(assignments, users, assignment_types, secretary_id, now)
    result = _payload(org_type, org_id, name, assignment_types, selected, source=source,
                      role_codes=("COLLEGE_ADMIN",) if org_type == "COLLEGE" else ())
    if not selected:
        result["reason"] = f"{name}未设置当前有效且可办理的责任岗位，请核对组织与任职"
        result["blockerCode"] = reason_code
    return result


def _scoped_holders(db, users, org_type, org, permission_code, *, cache=None):
    from app.core.affairs_security import build_affairs_context
    from app.core.permissions import _match
    from app.models import Role, RoleAssignmentScope, UserRole

    if not users:
        return []
    user_ids = {int(row.id) for row in users}
    # The permission guard has already read all active user-role pairs for this tenant
    # when its explicit request cache is present. Keep the original query otherwise.
    active_pair_key = ("active_role_pairs", _tid())
    if cache is not None and active_pair_key in cache:
        pairs = [(uid, role) for uid, role in cache[active_pair_key] if int(uid) in user_ids]
    else:
        from .academic_affairs_grade_task_assignee_guard import _active_role_pairs_statement
        pairs = _cached(cache, ("USER_ROLES", tuple(sorted(user_ids))), lambda: db.execute(
            _active_role_pairs_statement(_tid()).where(UserRole.user_id.in_(user_ids))
        ).all())
    allowed = set()
    college_id = int(org.id if org_type == "COLLEGE" else org.college_id) if org_type != "SCHOOL" else None
    by_id = {int(row.id): row for row in users}
    now = datetime.utcnow()
    for uid, role in pairs:
        account = by_id[int(uid)]
        ctx = _cached(cache, ("ROLE_CONTEXT", int(uid), int(role.id)), lambda: build_affairs_context({
            "userId": str(uid), "loginName": account.login_name, "tenantId": str(_tid()),
            "activeContextId": f"role:{role.id}", "currentRoleCode": role.role_code,
            "userType": account.user_type,
        }, db))
        if not _match(permission_code, ctx.permission_codes):
            continue
        if org_type == "SCHOOL" and ctx.scope_type == "TENANT_ALL":
            allowed.add(int(uid))
        elif org_type != "SCHOOL" and ctx.scope_type == "COLLEGE" and college_id in ctx.college_ids:
            allowed.add(int(uid))
        elif org_type == "MAJOR" and ctx.scope_type != "TENANT_ALL":
            explicit = _cached(cache, ("MAJOR_SCOPE", int(uid), role.role_code, int(org.id)), lambda: db.scalar(select(RoleAssignmentScope.id).where(
                RoleAssignmentScope.tenant_id == _tid(), RoleAssignmentScope.user_id == int(uid),
                RoleAssignmentScope.role_code == role.role_code, RoleAssignmentScope.scope_type == "MAJOR",
                RoleAssignmentScope.scope_id == int(org.id), RoleAssignmentScope.status == "ACTIVE",
                RoleAssignmentScope.is_deleted.is_(False), RoleAssignmentScope.effective_at <= now,
                or_(RoleAssignmentScope.expires_at.is_(None), RoleAssignmentScope.expires_at > now),
            ).limit(1)))
            if explicit:
                allowed.add(int(uid))
    return [row for row in users if int(row.id) in allowed]


def resolve_school(db, *, permission_code="academicAffairs.teachingTask.confirm", now=None, cache=None):
    from app.models import StaffAssignment, User
    from .academic_affairs_grade_correction_command import _college_bound_user_ids
    from .academic_affairs_grade_task_assignee_guard import (
        _preferred_role_candidates,
    )

    now = now or datetime.utcnow()
    holders = _permission_holders(db, permission_code, cache) - _cached(cache, ("COLLEGE_BOUND_USERS",), lambda: _college_bound_user_ids(db))
    appointments = _cached(cache, ("SCHOOL_APPOINTMENTS",), lambda: db.scalars(select(StaffAssignment).where(
        StaffAssignment.tenant_id == _tid(), StaffAssignment.org_type == "SCHOOL",
        StaffAssignment.org_node_id == _tid(), StaffAssignment.assignment_type == "ACADEMIC_REVIEWER",
    )).all())
    if appointments:
        candidates = {int(row.user_id) for row in appointments if _active_assignment(row, now)} & holders
        source = "STAFF_ASSIGNMENT"
    else:
        candidates = set(_cached(cache, ("PREFERRED_SCHOOL_USERS", tuple(sorted(holders))),
            lambda: _preferred_role_candidates(db, holders, "ACADEMIC_ADMIN")))
        source = "ROLE_AUTHORITY"
    users = _cached(cache, ("SCHOOL_USERS", tuple(sorted(candidates))), lambda: db.scalars(select(User).where(
        User.tenant_id == _tid(), User.id.in_(candidates or {-1}),
        User.status == "ACTIVE", User.is_deleted.is_(False),
    ).order_by(User.id)).all())
    users = _scoped_holders(db, users, "SCHOOL", None, permission_code, cache=cache)
    return _payload("SCHOOL", _tid(), "校教务处", ("ACADEMIC_REVIEWER",), users,
                    source=source if users else "UNRESOLVED", role_codes=("ACADEMIC_ADMIN",),
                    reason="" if users else "校级教务责任人未配置或当前没有办理权限")


def resolve_teacher(db, task, *, permission_code="academicAffairs.teachingTask.view", cache=None):
    return resolve_teachers(db, [task], permission_code=permission_code, cache=cache)[int(task.id)]


def resolve_teachers(db, tasks, *, permission_code="academicAffairs.teachingTask.view", cache=None):
    """教师身份使用稳定账号键，绝不按姓名或学生学院猜人。"""
    from app.models import AaTeachingClass, AaTeachingClassTeacher, User
    from .academic_affairs_teacher_relation_authority import class_authority_weeks, relation_covers_week

    tasks = list(tasks)
    if not tasks:
        return {}
    classes = db.scalars(select(AaTeachingClass).where(
        AaTeachingClass.tenant_id == _tid(), AaTeachingClass.teaching_task_id.in_([int(task.id) for task in tasks]),
        AaTeachingClass.is_deleted.is_(False),
    )).all()
    class_tasks = {int(row.id): int(row.teaching_task_id) for row in classes}
    formal_task_ids = set(class_tasks.values())
    keys_by_task = {int(task.id): set() if int(task.id) in formal_task_ids else
                    {str(getattr(task, "teacher_key", None) or "").strip()} - {""} for task in tasks}
    if classes:
        active = [row for row in classes if row.status == "ACTIVE"]
        weeks = class_authority_weeks(db, active)
        relations = db.scalars(select(AaTeachingClassTeacher).where(
            AaTeachingClassTeacher.tenant_id == _tid(),
            AaTeachingClassTeacher.teaching_class_id.in_([row.id for row in active] or [-1]),
            AaTeachingClassTeacher.status == "ACTIVE", AaTeachingClassTeacher.is_deleted.is_(False),
        )).all()
        for row in relations:
            if relation_covers_week(row, weeks.get(int(row.teaching_class_id))):
                key = str(row.teacher_key or "").strip()
                if key:
                    keys_by_task[class_tasks[int(row.teaching_class_id)]].add(key)
    keys = set().union(*keys_by_task.values())

    def stable_user_id(key):
        raw = str(key or "").strip()
        if raw.startswith("db-") and raw[3:].isdigit():
            return int(raw[3:])
        if raw.startswith("u_") and raw[2:].isdigit():
            return int(raw[2:])
        if raw.isdigit():
            return int(raw)
        return None

    key_ids = {key: stable_user_id(key) for key in keys}
    ids = {identity for identity in key_ids.values() if identity is not None}
    users = db.scalars(select(User).where(
        User.tenant_id == _tid(), or_(User.login_name.in_(keys), User.id.in_(ids or {-1})),
        User.status == "ACTIVE", User.is_deleted.is_(False),
    )).all() if keys else []
    holders = _permission_holders(db, permission_code, cache) if users else set()
    matches = {key: [row for row in users
                     if row.login_name == key or (key_ids[key] is not None and int(row.id) == key_ids[key])]
               for key in keys}
    result = {}
    for task in tasks:
        task_keys = keys_by_task[int(task.id)]
        people = {int(matches[key][0].id): matches[key][0] for key in task_keys
                  if len(matches[key]) == 1 and int(matches[key][0].id) in holders}
        if any(len(matches[key]) != 1 for key in task_keys):
            people = {}
        source = "TEACHING_CLASS_TEACHER" if int(task.id) in formal_task_ids else "TEACHING_TASK"
        result[int(task.id)] = _payload("TEACHING_TASK", task.id, "任课教师", ("TEACHER",), list(people.values()),
            source=source if people else "UNRESOLVED", role_codes=("ACADEMIC_TEACHER",),
            reason="" if people else "教学任务的教师工号未唯一关联当前有效账号或办理权限缺失")
    return result


def offering_college_id(course=None, batch=None, *, teaching_task=False):
    """教学任务以批次为责任域；排课/课程内容以课程开课学院优先。"""
    owner = getattr(course, "owner_college_id", None)
    batch_college = getattr(batch, "college_id", None)
    value = batch_college if teaching_task else (owner or batch_college)
    return int(value) if value else None


def resolve_program(db, program, *, college_id=None, cache=None):
    """培养方案编制、院审、校审沿同一个对象状态移交责任。"""
    from app.models import Major
    if program and program.status == "ACADEMIC_REVIEW":
        return resolve_school(db, permission_code="academicAffairs.program.review", cache=cache)
    if program and program.status in {"DRAFT", "RETURNED"}:
        return resolve_organization(db, "MAJOR", program.major_id,
            assignment_types=("LEADER", "SECRETARY"), permission_code="academicAffairs.program.manage", cache=cache)
    major = db.scalar(select(Major).where(Major.tenant_id == _tid(), Major.id == program.major_id,
        Major.is_deleted.is_(False))) if program and program.major_id else None
    return resolve_organization(db, "COLLEGE", major.college_id if major else college_id,
        permission_code="academicAffairs.program.review", cache=cache)


def offering_unit(course=None, batch=None):
    """候选单位可按既有链回退；缺课程开课单位仍明确阻断发布就绪。"""
    owner = getattr(course, "owner_college_id", None)
    college_id = offering_college_id(course, batch)
    return {"collegeId": str(college_id) if college_id else None,
            "source": "COURSE_OWNER" if owner else "TASK_BATCH" if college_id else "UNRESOLVED",
            "blockers": [] if owner else [{"code": "OFFERING_UNIT_UNRESOLVED",
                "message": "课程尚未配置开课单位；候选批次单位不能替代正式开课责任"}]}


def viewer_assignments(db, user_id, *, now=None):
    from app.models import StaffAssignment

    uid = str(user_id or "").removeprefix("db-")
    if not uid.isdigit():
        return []
    now = now or datetime.utcnow()
    rows = db.scalars(select(StaffAssignment).where(
        StaffAssignment.tenant_id == _tid(), StaffAssignment.user_id == int(uid),
        StaffAssignment.status == "ACTIVE", StaffAssignment.is_deleted.is_(False),
        StaffAssignment.effective_at <= now,
        or_(StaffAssignment.expires_at.is_(None), StaffAssignment.expires_at > now),
    )).all()
    return [{"orgType": row.org_type, "orgId": str(row.org_node_id),
             "assignmentType": row.assignment_type} for row in rows]



def _relation_rows(db, model, ids, cache, *, lock=False):
    """请求内按主键补齐事实；正式发布始终刷新并有序加锁。"""
    ids = {int(value) for value in ids if value is not None}
    key = ("OFFERING_RELATION_ROWS", _tid(), model.__tablename__)
    rows = {} if lock else cache.setdefault(key, {})
    missing = ids - rows.keys()
    if missing:
        statement = select(model).where(model.tenant_id == _tid(), model.id.in_(missing)).order_by(model.id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        loaded = db.scalars(statement).all()
        rows.update({value: None for value in missing})
        rows.update({int(row.id): row for row in loaded})
    return {value: row for value, row in rows.items() if value in ids and row and not row.is_deleted
            and int(row.tenant_id) == _tid()}


def _relation_program_colleges(db, term, openings, courses, cache, *, lock=False):
    """精确课程×行政班→同一当前/历史方案→本学期课程行→方案专业学院。"""
    from app.core.exceptions import AppException
    from app.models import AaProgram, AaProgramBinding, AaProgramCourse, College, Major, SchoolClass
    from .academic_affairs_archive_term_scope import cohort_term_scope
    from .academic_affairs_program_activation_service import _binding_time, _naive_utc, resolve_program_for_scope

    result = {key: None for key in openings}
    if not openings or not term or term.is_deleted or int(term.tenant_id) != _tid() or term.end_date is None:
        return result
    classes = _relation_rows(db, SchoolClass, [key[1] for key in openings], cache)
    major_ids = {int(row.major_id) for row in classes.values() if row.major_id is not None}
    scope_key = ("OFFERING_PROGRAM_FACTS", _tid(), tuple(sorted(major_ids)))
    if lock or scope_key not in cache:
        # 与正式绑定命令保持方案→行政班/专业→绑定锁序；不先锁绑定再回头锁方案。
        statement = select(AaProgram).where(AaProgram.tenant_id == _tid(),
            AaProgram.major_id.in_(major_ids)).order_by(AaProgram.id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        programs = {int(row.id): row for row in db.scalars(statement).all()}
        if lock:
            classes = _relation_rows(db, SchoolClass, [key[1] for key in openings], cache, lock=True)
            if any(row.major_id is None or int(row.major_id) not in major_ids for row in classes.values()):
                raise AppException("DATA_CONFLICT", "行政班专业关系已变化，请重新核对后发布", http_status=409)
        majors = _relation_rows(db, Major, major_ids, cache, lock=lock)
        statement = select(AaProgramBinding).where(AaProgramBinding.tenant_id == _tid(),
            AaProgramBinding.major_id.in_(major_ids), AaProgramBinding.is_deleted.is_(False),
            AaProgramBinding.status.in_(["ACTIVE", "SUPERSEDED"])).order_by(AaProgramBinding.id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        bindings = db.scalars(statement).all()
        if lock and any(int(row.program_id) not in programs for row in bindings):
            raise AppException("DATA_CONFLICT", "培养方案绑定关系已变化，请重新核对后发布", http_status=409)
        for major_id in major_ids:
            cache[("PROGRAM_SCOPE_BINDINGS", _tid(), major_id)] = tuple(
                row for row in bindings if int(row.major_id) == major_id)
        for row in bindings:
            cache[("PROGRAM_OBJECT", _tid(), int(row.program_id))] = programs.get(int(row.program_id))
        statement = select(AaProgramCourse).where(AaProgramCourse.tenant_id == _tid(),
            AaProgramCourse.program_id.in_(programs), AaProgramCourse.is_deleted.is_(False)).order_by(AaProgramCourse.id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        program_courses = db.scalars(statement).all()
        colleges = _relation_rows(db, College, [row.college_id for row in majors.values()], cache, lock=lock)
        cache[scope_key] = (majors, colleges, program_courses)
    majors, colleges, program_courses = cache[scope_key]
    by_course = {}
    for row in program_courses:
        if row.is_deleted or int(row.tenant_id) != _tid():
            continue
        key = (int(row.program_id), row.course_id, row.open_term_no)
        by_course.setdefault(key, []).append(row)
    now = datetime.utcnow()
    for key, source_id in openings.items():
        course_id, class_id = key
        clazz = classes.get(class_id)
        course = courses.get(course_id)
        if (not clazz or clazz.status != "ACTIVE" or clazz.class_status != "NORMAL" or not course
                or course.category == "PUBLIC_BASIC" or course.nature == "PUBLIC_ELECTIVE"):
            continue
        grade = str(clazz.grade or "").strip()
        scope = cohort_term_scope(term.year_code, term.term_no, grade)
        if scope["state"] != "IN_SCOPE":
            continue
        current = resolve_program_for_scope(db, tenant_id=_tid(), major_id=clazz.major_id,
            grade_year=grade, class_id=class_id, cache=cache)
        historical = resolve_program_for_scope(db, tenant_id=_tid(), major_id=clazz.major_id,
            grade_year=grade, class_id=class_id, as_of=term.end_date, cache=cache)
        if current.status != "RESOLVED" or historical.status != "RESOLVED":
            continue
        program, binding = current.program, current.binding
        selected_scope = [row for row in cache[("PROGRAM_SCOPE_BINDINGS", _tid(), int(clazz.major_id))]
                          if row.status == "ACTIVE" and not row.is_deleted and int(row.tenant_id) == _tid()
                          and row.class_id == binding.class_id
                          and (row.class_id is not None or str(row.grade_year or "").strip() == grade)]
        if len(selected_scope) != 1:
            continue
        if (int(program.id) != int(historical.program.id) or int(binding.id) != int(historical.binding.id)
                or program.major_id != clazz.major_id or binding.major_id != clazz.major_id
                or str(program.grade_year or "").strip() != grade
                or str(binding.grade_year or "").strip() != grade
                or _binding_time(binding) is None or _binding_time(binding) > now
                or _binding_time(binding) > _naive_utc(term.end_date)):
            continue
        matches = by_course.get((int(program.id), course_id, scope["planTerm"]), [])
        if len(matches) != 1 or (source_id is not None and int(matches[0].id) != source_id):
            continue
        major = majors.get(int(program.major_id))
        college = colleges.get(int(major.college_id)) if major else None
        if (major and not major.is_deleted and int(major.tenant_id) == _tid() and major.status == "ACTIVE"
                and college and not college.is_deleted and int(college.tenant_id) == _tid()
                and college.status == "ACTIVE"):
            result[key] = int(college.id)
            cache[("OFFERING_RELATION_SOURCE", _tid(), int(term.id), *key)] = int(matches[0].id)
    return result


def resolve_task_offering_colleges(db, tasks, *, cache=None, lock=False):
    """只读第三层：所有输入任务ID均返回键，无法解析为None；不授予批次调整权限。"""
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm

    cache = {} if lock or cache is None else cache
    task_ids = [int(getattr(task, "id", task)) for task in tasks]
    tasks = _relation_rows(db, AaTeachingTask, task_ids, cache, lock=lock)
    batches = _relation_rows(db, AaTeachingTaskBatch, [row.batch_id for row in tasks.values()], cache, lock=lock)
    courses = _relation_rows(db, AaCourse, [row.course_id for row in tasks.values()], cache, lock=lock)
    terms = _relation_rows(db, AaTerm, [row.term_id for row in batches.values()], cache, lock=lock)
    result = {task_id: None for task_id in task_ids}
    pending = {}
    for task_id, task in tasks.items():
        batch, course = batches.get(int(task.batch_id)), courses.get(int(task.course_id))
        if not batch or batch.status != "APPROVED" or not course or task.status == "MERGED":
            continue
        if course.owner_college_id is not None or batch.college_id is not None:
            continue  # 仅第三层；显式非空来源（包括失效来源）绝不回退。
        if (task.class_id is None or task.is_merged or task.formation_mode == "MERGED"
                or course.category == "PUBLIC_BASIC" or course.nature == "PUBLIC_ELECTIVE"):
            continue
        pending.setdefault(int(batch.term_id), []).append(task)
    for term_id, rows in pending.items():
        openings = {(int(row.course_id), int(row.class_id)): None for row in rows}
        resolved = _relation_program_colleges(db, terms.get(term_id), openings, courses, cache, lock=lock)
        for row in rows:
            key = (int(row.course_id), int(row.class_id))
            college_id = resolved.get(key)
            if (row.source_program_course_id is not None and int(row.source_program_course_id) !=
                    cache.get(("OFFERING_RELATION_SOURCE", _tid(), term_id, *key))):
                college_id = None
            result[int(row.id)] = college_id
    return result


def resolve_term_task_offering_colleges(db, term_id, *, cache=None):
    """学院编制投影只追加已批准共享批次的第三层精确任务；缓存限本次请求。"""
    from app.models import AaTeachingTask, AaTeachingTaskBatch
    from .academic_affairs_task_execution_authority import load_execution_handoffs

    cache = {} if cache is None else cache
    key = ("TERM_TASK_OFFERING_COLLEGES", _tid(), int(term_id))
    if key not in cache:
        tasks = db.scalars(select(AaTeachingTask).join(AaTeachingTaskBatch,
            AaTeachingTaskBatch.id == AaTeachingTask.batch_id).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.status != "MERGED",
            AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.is_deleted.is_(False),
            AaTeachingTaskBatch.term_id == int(term_id), AaTeachingTaskBatch.college_id.is_(None),
            AaTeachingTaskBatch.status == "APPROVED")).all()
        handoffs = load_execution_handoffs(db, [task.id for task in tasks])
        cache[key] = resolve_task_offering_colleges(db,
            [task for task in tasks if int(task.id) not in handoffs], cache=cache)
    return cache[key]


def resolve_opening_offering_colleges(db, term, openings, *, cache=None, lock=False):
    """只解第三层；已批准任务的非空批次学院不能被方案学院覆盖。"""
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm

    cache = {} if lock or cache is None else cache
    pairs = {}
    for row in openings:
        course_id = row.get("courseId", row.get("course_id"))
        class_id = row.get("classId", row.get("class_id"))
        if course_id is not None and class_id is not None:
            source = row.get("programCourseId", row.get("source_program_course_id"))
            pairs[(int(course_id), int(class_id))] = int(source) if source is not None else None
    term_id = int(term.id)
    term = _relation_rows(db, AaTerm, [term_id], cache, lock=lock).get(term_id)
    courses = _relation_rows(db, AaCourse, [key[0] for key in pairs], cache, lock=lock)
    result = {key: None for key in pairs}
    if not pairs or term is None:
        return result
    statement = select(AaTeachingTask).join(AaTeachingTaskBatch,
        AaTeachingTaskBatch.id == AaTeachingTask.batch_id).where(
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
        AaTeachingTask.status != "MERGED", AaTeachingTask.course_id.in_({key[0] for key in pairs}),
        AaTeachingTask.class_id.in_({key[1] for key in pairs}),
        AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.is_deleted.is_(False),
        AaTeachingTaskBatch.term_id == term_id, AaTeachingTaskBatch.status == "APPROVED")
    if lock:
        statement = statement.order_by(AaTeachingTask.id).with_for_update().execution_options(populate_existing=True)
    tasks = db.scalars(statement).all()
    batches = _relation_rows(db, AaTeachingTaskBatch, [row.batch_id for row in tasks], cache, lock=lock)
    explicit = {(int(row.course_id), int(row.class_id)) for row in tasks
                if batches.get(int(row.batch_id)) and batches[int(row.batch_id)].college_id is not None}
    pending = {key: source for key, source in pairs.items()
               if key[0] in courses and courses[key[0]].owner_college_id is None and key not in explicit}
    result.update(_relation_program_colleges(db, term, pending, courses, cache, lock=lock))
    return result
