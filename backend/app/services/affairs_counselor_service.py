"""班级辅导员责任关系：真实用户绑定、交接、历史与工作量汇总。

与 TeacherStudentScope 同源：PRIMARY 生效/结束/交接同步 CLASS scope；
TEMP 到期写路径结束；交接/主责变更迁移班级学生相关待办与风险责任人。
"""

from app.core.optimistic_lock import atomic_claim_version

from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException, check_version, not_found
from app.services.affairs_dashboard_service import _allowed_class_ids, _audit, _class_in_scope_or_403
from app.services.db_service import _iso, _tid, session

_DUTY_TYPES = {"PRIMARY", "CO", "TEMP"}
_STATUSES = {"ACTIVE", "ENDED"}


def _actor_id(user) -> int | None:
    try:
        return int((user or {}).get("userId") or 0) or None
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
    from app.models import User
    u = db.get(User, int(user_id))
    if not u or u.tenant_id != _tid() or u.is_deleted or u.status != "ACTIVE":
        raise AppException("VALIDATION_ERROR", "辅导员不存在、已离职或不在当前租户")
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
    from app.models import TeacherStudentScope, User
    notes = []
    if old_counselor_id:
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


def _migrate_class_work(db, class_id, from_user_id, to_user_id, reason: str) -> dict:
    """将班级学生相关 PENDING 待办/审批任务/风险责任人从原辅导迁到新辅导。"""
    from app.models import AffairsRiskRecord, UnifiedTodo, WorkflowTask

    from_uid, to_uid = int(from_user_id), int(to_user_id)
    if from_uid == to_uid:
        return {"todos": 0, "workflowTasks": 0, "risks": 0}
    student_ids = _class_student_ids(db, class_id)
    if not student_ids:
        return {"todos": 0, "workflowTasks": 0, "risks": 0}

    moved_todos = 0
    todos = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.assignee_id == from_uid,
        UnifiedTodo.status == "PENDING", UnifiedTodo.is_deleted.is_(False),
        UnifiedTodo.student_id.in_(student_ids))).all()
    for todo in todos:
        clash = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.source_module == todo.source_module,
            UnifiedTodo.source_biz_id == todo.source_biz_id,
            UnifiedTodo.todo_type == todo.todo_type,
            UnifiedTodo.assignee_id == to_uid,
            UnifiedTodo.is_deleted.is_(False))).first()
        if clash:
            if clash.status != "PENDING":
                clash.status = "PENDING"
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

    moved_tasks = 0
    from app.models import WorkflowInstance
    # 以学工 UnifiedTodo 的学生归属作为跨域权威映射，覆盖请假、奖助、处分、宿舍等。
    source_pairs = {
        (str(biz_type or "").upper(), str(biz_id or ""))
        for biz_type, biz_id in db.execute(
            select(UnifiedTodo.source_biz_type, UnifiedTodo.source_biz_id).where(
                UnifiedTodo.tenant_id == _tid(),
                UnifiedTodo.source_module == "student-affairs",
                UnifiedTodo.student_id.in_(student_ids),
                UnifiedTodo.is_deleted.is_(False),
            )
        ).all()
    }
    if source_pairs:
        task_rows = db.execute(
            select(WorkflowTask, WorkflowInstance)
            .join(WorkflowInstance, WorkflowInstance.id == WorkflowTask.instance_id)
            .where(
                WorkflowTask.tenant_id == _tid(),
                WorkflowTask.assignee_id == from_uid,
                WorkflowTask.status == "PENDING",
                WorkflowTask.is_deleted.is_(False),
                WorkflowInstance.tenant_id == _tid(),
                func.replace(WorkflowInstance.source_module, "_", "-") == "student-affairs",
                WorkflowInstance.is_deleted.is_(False),
            )
        ).all()
        for task, inst in task_rows:
            key = (str(inst.source_biz_type or "").upper(), str(inst.source_biz_id or ""))
            if key not in source_pairs:
                continue
            task.assignee_id = to_uid
            task.version = int(task.version or 0) + 1
            moved_tasks += 1

    moved_risks = 0
    for risk in db.scalars(select(AffairsRiskRecord).where(
            AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.owner_id == from_uid,
            AffairsRiskRecord.student_id.in_(student_ids),
            AffairsRiskRecord.status.notin_(["CLOSED"]),
            AffairsRiskRecord.is_deleted.is_(False))).all():
        risk.owner_id = to_uid
        risk.version = int(risk.version or 0) + 1
        moved_risks += 1

    return {"todos": moved_todos, "workflowTasks": moved_tasks, "risks": moved_risks}


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
    start, end = _dt(effective_from) or datetime.utcnow(), _dt(effective_to)
    if duty_type == "TEMP" and not end:
        raise AppException("VALIDATION_ERROR", "临时代班必须填写有效截止时间")
    if end and end < start:
        raise AppException("VALIDATION_ERROR", "有效截止时间不能早于开始时间")
    with session() as db:
        _expire_due_temps(db, actor_id=_actor_id(user))
        c = _class_in_scope_or_403(db, class_id, user)
        _active_user(db, user_id)
        actor = _actor_id(user)
        migrated = {"todos": 0, "workflowTasks": 0, "risks": 0}
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
        return _row(db, x)


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
        current = next((x for x in from_rows if x.duty_type == "PRIMARY"), from_rows[0])
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
            duty_type="PRIMARY", status="ACTIVE", effective_from=datetime.utcnow(), reason=reason.strip(),
            handover_from_user_id=int(from_user_id), created_by=actor, updated_by=actor)
        c.counselor_id, c.updated_by = int(to_user_id), actor
        db.add(x); db.flush()
        scope_note = _sync_primary_scope(db, c, old_counselor_id or from_user_id, int(to_user_id))
        migrated = _migrate_class_work(db, c.id, from_user_id, to_user_id, reason.strip())
        _audit(db, "COUNSELOR_ASSIGN", x.id, "HANDOVER",
               f"class={c.id},from={from_user_id},to={to_user_id},reason={reason.strip()};"
               f"{scope_note};migrate={migrated}")
        db.commit(); db.refresh(x)
        return _row(db, x)


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
