"""班级辅导员责任关系：真实用户绑定、交接、历史与工作量汇总。

与 TeacherStudentScope 同源：PRIMARY 生效/结束/交接同步 CLASS scope；
TEMP 到期写路径结束；交接/主责变更迁移班级学生相关待办与风险责任人。
"""

from app.core.optimistic_lock import atomic_claim_version
from app.core.timeutil import utc_now_naive

from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException, check_version, not_found
from app.services.affairs_dashboard_service import _allowed_class_ids, _audit, _class_in_scope_or_403
from app.services.db_service import _iso, _tid, session

_DUTY_TYPES = {"PRIMARY", "CO", "TEMP"}
_STATUSES = {"ACTIVE", "ENDED"}


def _actor_id(user) -> int | None:
    try:
        return int(str((user or {}).get("userId") or "0").removeprefix("db-")) or None
    except (TypeError, ValueError):
        return None


def _dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            pass
    raise AppException("VALIDATION_ERROR", "日期格式应为 YYYY-MM-DD 或 ISO 日期时间")


def _active_user(db, user_id):
    from app.models import Role, User, UserRole
    u = db.get(User, int(user_id))
    if not u or u.tenant_id != _tid() or u.is_deleted or u.status != "ACTIVE":
        raise AppException("VALIDATION_ERROR", "辅导员不存在、已离职或不在当前租户")
    from app.services.role_assignment_scope_service import active_role_membership_query
    member = db.scalar(active_role_membership_query(_tid()).where(
        Role.role_code == "COUNSELOR", UserRole.user_id == int(user_id),
    ).limit(1))
    if not member:
        raise AppException("VALIDATION_ERROR", "接任人员没有当前有效的辅导员任职，请先核验任职和有效期")
    from app.core.permissions import has_permission
    if not has_permission({"userId": f"db-{u.id}", "tenantId": str(_tid()),
            "currentRoleCode": "COUNSELOR", "activeContextId": f"role:{member.role_id}"}, "studentAffairs.student.view"):
        raise AppException("VALIDATION_ERROR", "接任人员没有辅导员学生查看能力，请先核验授权")
    return u


def _row(db, x, classes=None, users=None, student_counts=None):
    from app.models import SchoolClass, StudentProfile, User
    classes = classes if classes is not None else {}
    users = users if users is not None else {}
    student_counts = student_counts if student_counts is not None else {}
    c = classes.get(x.class_id)
    if c is None:
        c = db.get(SchoolClass, x.class_id)
    u = users.get(x.user_id)
    if u is None:
        u = db.get(User, x.user_id)
    count = student_counts.get(x.class_id)
    if count is None:
        count = db.scalar(select(func.count()).select_from(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.class_id == x.class_id,
            StudentProfile.is_deleted.is_(False))) or 0
    is_expired_temp = (
        x.status == "ACTIVE" and x.duty_type == "TEMP"
        and x.effective_to is not None and x.effective_to <= datetime.utcnow()
    )
    return {
        "id": str(x.id), "classId": str(x.class_id), "className": c.class_name if c else "",
        # loginName 供列表副标题显示（同名老师靠工号区分）；页面不再展示裸用户 ID
        "userId": str(x.user_id), "counselorName": u.real_name if u else "",
        "loginName": (u.login_name or "") if u else "",
        "studentCount": count, "dutyType": x.duty_type,
        "status": "ENDED" if is_expired_temp else x.status,
        "effectiveFrom": _iso(x.effective_from), "effectiveTo": _iso(x.effective_to),
        "reason": x.reason or "", "handoverFromUserId": str(x.handover_from_user_id or ""),
        "version": x.version, "createdAt": _iso(x.created_at), "updatedAt": _iso(x.updated_at),
    }


def _visible_classes(db, user):
    allowed, scope = _allowed_class_ids(db, user)
    return allowed, scope


def _sync_primary_scope(db, class_row, old_counselor_id, new_counselor_id) -> str:
    """PRIMARY 变更后同步 t_teacher_student_scope（与教务班级改绑口径一致）。

    teacher_key=登录名、role_code=COUNSELOR、scope_type=CLASS、ref_value=班级名。
    撤旧兼容 teacher_key=登录名或 userId；新辅导员不存在时不写 scope。
    """
    from app.models import RoleAssignmentScope, TeacherStudentScope, User
    notes = []
    if old_counselor_id:
        for scope in db.scalars(select(RoleAssignmentScope).where(
            RoleAssignmentScope.tenant_id == _tid(), RoleAssignmentScope.user_id == int(old_counselor_id),
            RoleAssignmentScope.role_code == "COUNSELOR", RoleAssignmentScope.scope_type == "CLASS",
            RoleAssignmentScope.scope_id == class_row.id, RoleAssignmentScope.status == "ACTIVE",
            RoleAssignmentScope.is_deleted.is_(False),
        )).all():
            scope.status = "REVOKED"
            scope.version = int(scope.version or 0) + 1
        old_u = db.get(User, int(old_counselor_id))
        old_keys = [str(old_counselor_id)] + ([old_u.login_name] if old_u and old_u.login_name else [])
        for row in db.scalars(select(TeacherStudentScope).where(
                TeacherStudentScope.tenant_id == _tid(),
                TeacherStudentScope.teacher_key.in_(old_keys),
                TeacherStudentScope.role_code == "COUNSELOR",
                TeacherStudentScope.scope_type == "CLASS",
                TeacherStudentScope.ref_value == class_row.class_name,
                TeacherStudentScope.status == "ACTIVE",
                TeacherStudentScope.is_deleted.is_(False))).all():
            row.status = "INACTIVE"
            row.version = int(row.version or 0) + 1
            notes.append(f"撤旧scope:{row.teacher_key}")
    if new_counselor_id:
        new_u = db.get(User, int(new_counselor_id))
        if new_u and not new_u.is_deleted and new_u.tenant_id == _tid() and new_u.login_name:
            existing = db.scalars(select(TeacherStudentScope).where(
                TeacherStudentScope.tenant_id == _tid(),
                TeacherStudentScope.teacher_key == new_u.login_name,
                TeacherStudentScope.role_code == "COUNSELOR",
                TeacherStudentScope.scope_type == "CLASS",
                TeacherStudentScope.ref_value == class_row.class_name)).first()
            if existing:
                existing.is_deleted, existing.status = False, "ACTIVE"
                existing.teacher_name = new_u.real_name
                existing.version = int(existing.version or 0) + 1
            else:
                db.add(TeacherStudentScope(
                    tenant_id=_tid(), teacher_key=new_u.login_name,
                    teacher_name=new_u.real_name, role_code="COUNSELOR",
                    scope_type="CLASS", ref_value=class_row.class_name, status="ACTIVE"))
            notes.append(f"立新scope:{new_u.login_name}")
        else:
            notes.append(f"新辅导员user_id={new_counselor_id}不存在,未写scope")
    return ";".join(notes)


def _class_student_ids(db, class_id) -> set[int]:
    from app.models import StudentProfile
    return set(db.scalars(select(StudentProfile.id).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.class_id == int(class_id),
        StudentProfile.is_deleted.is_(False))).all())


def _counselor_pending_sources(db, student_ids):
    """只取真实源单当前辅导员节点，不按兼岗账号或待办标题推断职责。"""
    from app.models import AidApply, CsLeave, DisciplineRemoveApply, DormTransfer, FundingApplication, WorkflowInstance, WorkflowTask
    expected, origins, records = {}, {}, {}
    for model, biz_type, todo_type, status_attr in (
        (CsLeave, "LEAVE", "LEAVE_APPROVAL", "affairs_status"),
        (AidApply, "AID", "AID_APPROVAL", "status"),
        (FundingApplication, "FUNDING", "FUNDING_APPROVAL", "status"),
        (DisciplineRemoveApply, "DISCIPLINE", "DISCIPLINE_REMOVE", "current_node"),
    ):
        for row in db.scalars(select(model).where(
            model.tenant_id == _tid(), model.student_id.in_(student_ids), model.is_deleted.is_(False),
            getattr(model, status_attr).in_(("CLASS_REVIEW", "COUNSELOR_REVIEW")),
        ).with_for_update()).all():
            if row.workflow_instance_id:
                expected[(int(row.workflow_instance_id), getattr(row, status_attr))] = (
                    biz_type, int(row.case_id if model is DisciplineRemoveApply else row.id), todo_type)
                origins[int(row.workflow_instance_id)] = ("DISCIPLINE_REMOVE" if model is DisciplineRemoveApply else biz_type, int(row.id))
                records[expected[(int(row.workflow_instance_id), getattr(row, status_attr))]] = row
    sources, tasks, seen = set(), [], set()
    for task, flow in db.execute(select(WorkflowTask, WorkflowInstance).join(
        WorkflowInstance, WorkflowInstance.id == WorkflowTask.instance_id).where(
        WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id.in_({key[0] for key in expected} or {-1}),
        WorkflowTask.status == "PENDING", WorkflowTask.is_deleted.is_(False),
        WorkflowInstance.tenant_id == _tid(), WorkflowInstance.is_deleted.is_(False),
        WorkflowInstance.status == "RUNNING", WorkflowInstance.source_module == "student-affairs",
        WorkflowInstance.current_node == WorkflowTask.node_code,
    ).order_by(WorkflowTask.id.desc()).with_for_update()).all():
        key = (int(task.instance_id), task.node_code)
        if key in seen:
            continue
        seen.add(key)
        if key in expected and origins.get(int(flow.id)) == (str(flow.source_biz_type or "").upper(), int(flow.source_biz_id)):
            tasks.append(task)
    for row in db.scalars(select(CsLeave).where(
        CsLeave.tenant_id == _tid(), CsLeave.student_id.in_(student_ids), CsLeave.is_deleted.is_(False),
        CsLeave.affairs_status.in_(("WAIT_CANCEL_LEAVE", "EXTENSION_REVIEW", "OVERDUE")),
    ).with_for_update()).all():
        kind = {"WAIT_CANCEL_LEAVE": "LEAVE_CANCEL", "EXTENSION_REVIEW": "LEAVE_EXTENSION", "OVERDUE": "LEAVE_OVERDUE"}[row.affairs_status]
        sources.add(("LEAVE", int(row.id), kind))
        records[("LEAVE", int(row.id), kind)] = row
    for row in db.scalars(select(DormTransfer).where(
        DormTransfer.tenant_id == _tid(), DormTransfer.student_id.in_(student_ids),
        DormTransfer.is_deleted.is_(False), DormTransfer.status == "COUNSELOR_REVIEW",
        DormTransfer.current_node == "COUNSELOR_REVIEW",
    ).with_for_update()).all():
        sources.add(("DORM_TRANSFER", int(row.id), "DORM_TRANSFER"))
        records[("DORM_TRANSFER", int(row.id), "DORM_TRANSFER")] = row
    return expected, sources, tasks, records


def _migrate_class_work(db, class_id, from_user_id, to_user_id, reason: str) -> dict:
    """将班级学生相关 PENDING 待办/审批任务/风险责任人从原辅导迁到新辅导。"""
    from app.models import AffairsRiskRecord, UnifiedTodo, WorkflowTask

    from_uid, to_uid = int(from_user_id), int(to_user_id)
    if from_uid == to_uid:
        return {"todos": 0, "workflowTasks": 0, "risks": 0, "retained": 0}
    student_ids = _class_student_ids(db, class_id)
    if not student_ids:
        return {"todos": 0, "workflowTasks": 0, "risks": 0, "retained": 0}

    expected, sources, tasks, records = _counselor_pending_sources(db, student_ids)
    tasks = [task for task in tasks if int(task.assignee_id or 0) == from_uid]
    sources.update(expected[(int(task.instance_id), task.node_code)] for task in tasks)
    risks = db.scalars(select(AffairsRiskRecord).where(
        AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.owner_id == from_uid,
        AffairsRiskRecord.student_id.in_(student_ids), AffairsRiskRecord.status != "CLOSED",
        AffairsRiskRecord.is_deleted.is_(False),
    ).with_for_update()).all()
    sources.update(("RISK", int(risk.id), "RISK_HANDLE") for risk in risks)

    moved_todos = 0
    candidates = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.assignee_id == from_uid,
        UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.status == "PENDING", UnifiedTodo.is_deleted.is_(False),
        UnifiedTodo.student_id.in_(student_ids)).with_for_update()).all()
    todos = [todo for todo in candidates if (str(todo.source_biz_type or "").upper(),
             int(todo.source_biz_id or 0), todo.todo_type) in sources]
    from app.core.permissions import has_permission
    from app.models import Role, UserRole
    from app.services.role_assignment_scope_service import active_role_membership_query
    member = db.scalar(active_role_membership_query(_tid()).where(
        Role.role_code == "COUNSELOR", UserRole.user_id == to_uid).limit(1))
    target = {"userId": f"db-{to_uid}", "tenantId": str(_tid()), "currentRoleCode": "COUNSELOR",
              "activeContextId": f"role:{member.role_id}"} if member else {}
    permissions = {
        "LEAVE_APPROVAL": ("studentAffairs.leave.approve",),
        "AID_APPROVAL": ("studentAffairs.aid.approve", "studentAffairs.aid.counselorReview"),
        "FUNDING_APPROVAL": ("studentAffairs.funding.approve",),
        "DISCIPLINE_REMOVE": ("studentAffairs.discipline.remove.approve",),
        "DORM_TRANSFER": ("studentAffairs.dorm.transfer.approve",),
        "LEAVE_CANCEL": ("studentAffairs.leave.cancelLeaveConfirm",),
        "LEAVE_EXTENSION": ("studentAffairs.leave.extension.approve",),
        "LEAVE_OVERDUE": ("studentAffairs.leave.overdue.handle",),
        "RISK_HANDLE": ("studentAffairs.risk.handle",),
    }
    required_types = {todo.todo_type for todo in todos} | {expected[(int(t.instance_id), t.node_code)][2] for t in tasks}
    if not member or any(not any(has_permission(target, code) for code in permissions[kind]) for kind in required_types):
        raise AppException("NO_PERMISSION", "接任人员缺少当前辅导员办理能力，交接未执行，请先核验授权")
    source_biz_ids = {int(todo.source_biz_id) for todo in todos if todo.source_biz_id} | {int(r.id) for r in risks}
    target_rows = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.assignee_id == to_uid,
        UnifiedTodo.source_biz_id.in_(source_biz_ids) if source_biz_ids else UnifiedTodo.source_biz_id == -1,
        UnifiedTodo.is_deleted.is_(False),
    )).all()
    target_map = {
        (row.source_module, int(row.source_biz_id or 0), row.todo_type): row
        for row in target_rows
    }
    for todo in todos:
        clash = target_map.get((todo.source_module, int(todo.source_biz_id or 0), todo.todo_type))
        if clash:
            if clash.status != "PENDING":
                raise AppException("DATA_CONFLICT", "接任者有同一事项的已办历史，交接未执行，请先核验；原记录已保留")
            clash.title = todo.title
            clash.version = int(clash.version or 0) + 1
            todo.status = "CANCELLED"
            todo.remark = (todo.remark or "")[:400] + f"|交接取消→{to_uid}"
            todo.version = int(todo.version or 0) + 1
        else:
            todo.assignee_id = to_uid
            todo.remark = ((todo.remark or "") + f"|交接自{from_uid}:{reason}")[:500]
            todo.version = int(todo.version or 0) + 1
        moved_todos += 1

    for task in tasks:
        task.assignee_id = to_uid
        task.version = int(task.version or 0) + 1
        _audit(db, "WORKFLOW_TASK", task.id, "COUNSELOR_HANDOVER",
               f"instance={task.instance_id},node={task.node_code},from={from_uid},to={to_uid},reason={reason}")
    changed = {(str(t.source_biz_type or "").upper(), int(t.source_biz_id), t.todo_type) for t in todos}
    changed.update(expected[(int(t.instance_id), t.node_code)] for t in tasks)
    for row in {id(records[key]): records[key] for key in changed if key in records}.values():
        row.version = int(row.version or 0) + 1
    for biz_type, biz_id, _kind in changed:
        if biz_type != "RISK":
            _audit(db, biz_type, biz_id, "COUNSELOR_HANDOVER", f"from={from_uid},to={to_uid},reason={reason}")
    from app.models import DisciplineCase, DisciplineRemoveApply
    for row in (records[key] for key in changed if key in records and isinstance(records[key], DisciplineRemoveApply)):
        case = db.get(DisciplineCase, int(row.case_id))
        if case and case.tenant_id == _tid():
            case.version = int(case.version or 0) + 1

    moved_risks = 0
    migrated_risk_ids = {int(todo.source_biz_id) for todo in todos if todo.todo_type == "RISK_HANDLE"}
    for risk in risks:
        if not has_permission(target, "studentAffairs.risk.handle"):
            raise AppException("NO_PERMISSION", "接任人员缺少风险跟进能力，交接未执行，请先核验授权")
        risk.owner_id = to_uid
        risk.version = int(risk.version or 0) + 1
        if int(risk.id) not in migrated_risk_ids:
            clash = target_map.get(("student-affairs", int(risk.id), "RISK_HANDLE"))
            if clash and clash.status != "PENDING":
                raise AppException("DATA_CONFLICT", "接任者有该风险的已办历史，交接未执行，请先核验")
            from app.services.affairs_risk_service import _todo_upsert
            _todo_upsert(db, risk.id, to_uid, risk.student_id, f"风险交接待跟进：{risk.title or '学生风险'}")
        _audit(db, "RISK", risk.id, "COUNSELOR_HANDOVER", f"from={from_uid},to={to_uid},reason={reason}")
        moved_risks += 1

    return {"todos": moved_todos, "workflowTasks": len(tasks), "risks": moved_risks,
            "retained": len(candidates) - len(todos)}


def _expire_due_temps(db, *, now: datetime | None = None, actor_id: int | None = None) -> int:
    """将已过 effective_to 的 TEMP ACTIVE 关系写为 ENDED。"""
    from app.models import AffairsCounselorAssignment
    now = now or datetime.utcnow()
    rows = db.scalars(select(AffairsCounselorAssignment).where(
        AffairsCounselorAssignment.tenant_id == _tid(),
        AffairsCounselorAssignment.is_deleted.is_(False),
        AffairsCounselorAssignment.status == "ACTIVE",
        AffairsCounselorAssignment.duty_type == "TEMP",
        AffairsCounselorAssignment.effective_to.is_not(None),
        AffairsCounselorAssignment.effective_to <= now)).all()
    for x in rows:
        _end(db, x, "临时代班到期自动结束", actor_id)
        _audit(db, "COUNSELOR_ASSIGN", x.id, "TEMP_EXPIRE", f"class={x.class_id},user={x.user_id}")
    return len(rows)


def scan_expired_temps() -> dict:
    """定时/手动扫描到期临时代班。"""
    with session() as db:
        n = _expire_due_temps(db)
        db.commit()
        return {"ended": n}


def list_assignments(user, class_id=None, user_id=None, status=None, vacancy_only=False,
                     page=1, page_size=20):
    from app.models import AffairsCounselorAssignment, SchoolClass, StudentProfile, User
    if status and status not in _STATUSES:
        raise AppException("VALIDATION_ERROR", "状态仅支持 ACTIVE 或 ENDED")
    with session() as db:
        allowed, _ = _visible_classes(db, user)
        if class_id:
            _class_in_scope_or_403(db, class_id, user)
        if vacancy_only:
            return _vacancy_rows(db, allowed, page, page_size)
        q = select(AffairsCounselorAssignment).where(
            AffairsCounselorAssignment.tenant_id == _tid(),
            AffairsCounselorAssignment.is_deleted.is_(False))
        if allowed is not None:
            q = q.where(AffairsCounselorAssignment.class_id.in_(allowed or {-1}))
        if class_id:
            q = q.where(AffairsCounselorAssignment.class_id == int(class_id))
        if user_id:
            q = q.where(AffairsCounselorAssignment.user_id == int(user_id))
        expired_temp = and_(
            AffairsCounselorAssignment.status == "ACTIVE",
            AffairsCounselorAssignment.duty_type == "TEMP",
            AffairsCounselorAssignment.effective_to.is_not(None),
            AffairsCounselorAssignment.effective_to <= datetime.utcnow(),
        )
        if status == "ACTIVE":
            q = q.where(
                AffairsCounselorAssignment.status == "ACTIVE",
                ~expired_temp,
            )
        elif status == "ENDED":
            q = q.where(or_(
                AffairsCounselorAssignment.status == "ENDED",
                expired_temp,
            ))
        rows = db.scalars(q.order_by(AffairsCounselorAssignment.class_id,
                                     AffairsCounselorAssignment.status,
                                     AffairsCounselorAssignment.id.desc())).all()
        class_ids, user_ids = {x.class_id for x in rows}, {x.user_id for x in rows}
        classes = {x.id: x for x in db.scalars(select(SchoolClass).where(SchoolClass.id.in_(class_ids))).all()} if class_ids else {}
        users = {x.id: x for x in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
        counts = dict(db.execute(select(StudentProfile.class_id, func.count()).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            StudentProfile.class_id.in_(class_ids or {-1})).group_by(StudentProfile.class_id)).all())
        out = [_row(db, x, classes, users, counts) for x in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def _vacancy_rows(db, allowed, page, page_size):
    from app.models import AffairsCounselorAssignment, SchoolClass, StudentProfile
    q = select(SchoolClass).where(SchoolClass.tenant_id == _tid(),
                                  SchoolClass.is_deleted.is_(False),
                                  SchoolClass.status == "ACTIVE")
    if allowed is not None:
        q = q.where(SchoolClass.id.in_(allowed or {-1}))
    classes = db.scalars(q.order_by(SchoolClass.class_name)).all()
    primary_ids = set(db.scalars(select(AffairsCounselorAssignment.class_id).where(
        AffairsCounselorAssignment.tenant_id == _tid(), AffairsCounselorAssignment.is_deleted.is_(False),
        AffairsCounselorAssignment.status == "ACTIVE", AffairsCounselorAssignment.duty_type == "PRIMARY")).all())
    vacant = [c for c in classes if c.id not in primary_ids]
    ids = {c.id for c in vacant}
    counts = dict(db.execute(select(StudentProfile.class_id, func.count()).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        StudentProfile.class_id.in_(ids or {-1})).group_by(StudentProfile.class_id)).all())
    out = [{"classId": str(c.id), "className": c.class_name, "studentCount": counts.get(c.id, 0),
            "status": "VACANT"} for c in vacant]
    total, start = len(out), (max(1, page) - 1) * page_size
    return out[start:start + page_size], total


def vacancies(user):
    with session() as db:
        allowed, _ = _visible_classes(db, user)
        items, total = _vacancy_rows(db, allowed, 1, 10000)
        return {"items": items, "total": total}


def list_counselor_ledger(user, page=1, page_size=20):
    from app.models import AffairsCounselorAssignment, StudentProfile, User
    with session() as db:
        allowed, _ = _visible_classes(db, user)
        q = select(AffairsCounselorAssignment).where(
            AffairsCounselorAssignment.tenant_id == _tid(), AffairsCounselorAssignment.is_deleted.is_(False),
            AffairsCounselorAssignment.status == "ACTIVE",
            or_(
                AffairsCounselorAssignment.duty_type != "TEMP",
                AffairsCounselorAssignment.effective_to.is_(None),
                AffairsCounselorAssignment.effective_to > datetime.utcnow(),
            ))
        if allowed is not None:
            q = q.where(AffairsCounselorAssignment.class_id.in_(allowed or {-1}))
        assignments = db.scalars(q).all()
        class_ids = {x.class_id for x in assignments}
        counts = dict(db.execute(select(StudentProfile.class_id, func.count()).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            StudentProfile.class_id.in_(class_ids or {-1})).group_by(StudentProfile.class_id)).all())
        users = {u.id: u for u in db.scalars(select(User).where(
            User.tenant_id == _tid(), User.id.in_({x.user_id for x in assignments} or {-1}))).all()}
        grouped = {}
        for x in assignments:
            item = grouped.setdefault(x.user_id, {"userId": str(x.user_id),
                "name": users.get(x.user_id).real_name if users.get(x.user_id) else "",
                "classIds": set(), "studentCount": 0, "primaryCount": 0, "tempCount": 0})
            if x.class_id not in item["classIds"]:
                item["classIds"].add(x.class_id)
                item["studentCount"] += counts.get(x.class_id, 0)
            item["primaryCount"] += int(x.duty_type == "PRIMARY")
            item["tempCount"] += int(x.duty_type == "TEMP")
        out = [{"userId": x["userId"], "name": x["name"], "classCount": len(x["classIds"]),
                "studentCount": x["studentCount"], "primaryCount": x["primaryCount"],
                "tempCount": x["tempCount"]} for x in grouped.values()]
        out.sort(key=lambda x: (-x["studentCount"], x["name"]))
        total, start = len(out), (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def _end(db, assignment, reason, actor_id):
    assignment.status = "ENDED"
    # TEMP 已有截止日时保留原值，便于台账核对；其余结束时刻写 effective_to
    if not assignment.effective_to or assignment.effective_to > datetime.utcnow():
        assignment.effective_to = datetime.utcnow()
    assignment.reason = reason or assignment.reason
    assignment.updated_by, assignment.version = actor_id, assignment.version + 1


def assign(user, class_id, user_id, duty_type, effective_from=None, effective_to=None, reason=""):
    from app.models import AffairsCounselorAssignment
    duty_type = (duty_type or "").upper()
    if duty_type not in _DUTY_TYPES:
        raise AppException("VALIDATION_ERROR", "责任类型仅支持 PRIMARY、CO、TEMP")
    # 现有数据库按秒存任期；避免微秒被进位为未来一秒，导致刚交接却暂无范围。
    start, end = _dt(effective_from) or utc_now_naive().replace(microsecond=0), _dt(effective_to)
    if duty_type == "TEMP" and not end:
        raise AppException("VALIDATION_ERROR", "临时代班必须填写有效截止时间")
    if end and end < start:
        raise AppException("VALIDATION_ERROR", "有效截止时间不能早于开始时间")
    with session() as db:
        _expire_due_temps(db, actor_id=_actor_id(user))
        c = _class_in_scope_or_403(db, class_id, user)
        _active_user(db, user_id)
        actor = _actor_id(user)
        migrated = {"todos": 0, "workflowTasks": 0, "risks": 0, "retained": 0}
        scope_note = ""
        if duty_type == "PRIMARY":
            old_counselor_id = c.counselor_id
            old = db.scalars(select(AffairsCounselorAssignment).where(
                AffairsCounselorAssignment.tenant_id == _tid(), AffairsCounselorAssignment.class_id == c.id,
                AffairsCounselorAssignment.duty_type == "PRIMARY", AffairsCounselorAssignment.status == "ACTIVE",
                AffairsCounselorAssignment.is_deleted.is_(False))).all()
            old_user_ids = {int(item.user_id) for item in old}
            for item in old:
                _end(db, item, reason or "主辅导员调整", actor)
            c.counselor_id, c.updated_by = int(user_id), actor
            scope_note = _sync_primary_scope(db, c, old_counselor_id, int(user_id))
            migrate_from = set(old_user_ids)
            if old_counselor_id:
                migrate_from.add(int(old_counselor_id))
            migrate_from.discard(int(user_id))
            for from_uid in migrate_from:
                part = _migrate_class_work(
                    db, c.id, from_uid, user_id, reason or "主辅导员调整")
                for k in migrated:
                    migrated[k] += part.get(k, 0)
        x = AffairsCounselorAssignment(tenant_id=_tid(), class_id=c.id, user_id=int(user_id),
            duty_type=duty_type, status="ACTIVE", effective_from=start, effective_to=end,
            reason=(reason or None), created_by=actor, updated_by=actor)
        db.add(x); db.flush()
        # 创建时已过期的临时代班立即结束，避免短暂 ACTIVE 脏数据
        if duty_type == "TEMP" and end and end <= datetime.utcnow():
            _end(db, x, "临时代班创建时已过期", actor)
        detail = f"class={c.id},user={user_id},duty={duty_type},status={x.status}"
        if scope_note:
            detail += f";{scope_note}"
        if migrated.get("todos") or migrated.get("workflowTasks") or migrated.get("risks"):
            detail += f";migrate={migrated}"
        _audit(db, "COUNSELOR_ASSIGN", x.id, "ASSIGN", detail)
        db.commit(); db.refresh(x)
        result = _row(db, x)
        result["handoverWork"] = migrated
        return result


def handover(user, class_id, from_user_id, to_user_id, reason, version):
    from app.models import AffairsCounselorAssignment
    if not (reason or "").strip():
        raise AppException("VALIDATION_ERROR", "交接原因必填")
    if int(from_user_id) == int(to_user_id):
        raise AppException("VALIDATION_ERROR", "交接双方不能是同一辅导员")
    with session() as db:
        _expire_due_temps(db, actor_id=_actor_id(user))
        c = _class_in_scope_or_403(db, class_id, user)
        _active_user(db, to_user_id)
        from_rows = db.scalars(select(AffairsCounselorAssignment).where(
            AffairsCounselorAssignment.tenant_id == _tid(), AffairsCounselorAssignment.class_id == c.id,
            AffairsCounselorAssignment.user_id == int(from_user_id), AffairsCounselorAssignment.status == "ACTIVE",
            AffairsCounselorAssignment.is_deleted.is_(False)).order_by(
                AffairsCounselorAssignment.duty_type == "PRIMARY")).all()
        if not from_rows:
            raise not_found("原辅导员没有有效责任关系")
        current = next((x for x in from_rows if x.duty_type == "PRIMARY"), None)
        if current is None:
            raise AppException("DATA_CONFLICT", "原辅导员不是该班主辅导员，不能发起主责交接")
        atomic_claim_version(db, current, version)
        actor = _actor_id(user)
        old_counselor_id = c.counselor_id
        for x in from_rows:
            _end(db, x, reason, actor)
        for x in db.scalars(select(AffairsCounselorAssignment).where(
            AffairsCounselorAssignment.tenant_id == _tid(), AffairsCounselorAssignment.class_id == c.id,
            AffairsCounselorAssignment.duty_type == "PRIMARY", AffairsCounselorAssignment.status == "ACTIVE",
            AffairsCounselorAssignment.user_id != int(from_user_id),
            AffairsCounselorAssignment.is_deleted.is_(False))).all():
            _end(db, x, "主辅导员交接", actor)
        x = AffairsCounselorAssignment(tenant_id=_tid(), class_id=c.id, user_id=int(to_user_id),
            duty_type="PRIMARY", status="ACTIVE", effective_from=utc_now_naive().replace(microsecond=0), reason=reason.strip(),
            handover_from_user_id=int(from_user_id), created_by=actor, updated_by=actor)
        c.counselor_id, c.updated_by = int(to_user_id), actor
        db.add(x); db.flush()
        scope_note = _sync_primary_scope(db, c, old_counselor_id or from_user_id, int(to_user_id))
        migrated = _migrate_class_work(db, c.id, from_user_id, to_user_id, reason.strip())
        _audit(db, "COUNSELOR_ASSIGN", x.id, "HANDOVER",
               f"class={c.id},from={from_user_id},to={to_user_id},reason={reason.strip()};"
               f"{scope_note};migrate={migrated}")
        db.commit(); db.refresh(x)
        result = _row(db, x)
        result["handoverWork"] = migrated
        result["handoverNotice"] = (
            f"主责交接已完成；另有{migrated['retained']}项其他职责或尚未核实的待办保留原受理人，请核验交接清单。"
            if migrated["retained"] else "辅导员主责和可核验的班级待办已交接，历史审批与附件保留。")
        return result


def end_assignment(user, assignment_id, reason, version):
    from app.models import AffairsCounselorAssignment
    if not (reason or "").strip():
        raise AppException("VALIDATION_ERROR", "结束责任关系必须填写原因")
    with session() as db:
        _expire_due_temps(db, actor_id=_actor_id(user))
        x = db.get(AffairsCounselorAssignment, int(assignment_id))
        if not x or x.tenant_id != _tid() or x.is_deleted:
            raise not_found("辅导员责任关系不存在")
        c = _class_in_scope_or_403(db, x.class_id, user)
        if x.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "责任关系已结束")
        atomic_claim_version(db, x, version)
        actor = _actor_id(user)
        was_primary = x.duty_type == "PRIMARY"
        old_counselor_id = x.user_id if was_primary else None
        _end(db, x, reason.strip(), actor)
        scope_note = ""
        if was_primary and c.counselor_id == x.user_id:
            c.counselor_id, c.updated_by = None, actor
            scope_note = _sync_primary_scope(db, c, old_counselor_id, None)
        detail = reason.strip()
        if scope_note:
            detail = f"{detail};{scope_note}"
        _audit(db, "COUNSELOR_ASSIGN", x.id, "END", detail)
        db.commit(); db.refresh(x)
        return _row(db, x)
