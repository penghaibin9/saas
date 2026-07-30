"""微信小程序高频链路：真分页、单请求工作台、批量已读。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, case, func, literal, or_, select, union_all, update as sql_update

from app.core.exceptions import AppException
from app.services import message_center_service as message_svc
from app.services import workbench_snapshot_service as snapshot_svc
from app.services import workbench_todo_service as todo_svc
from app.services.db_service import _iso, _tid, session


FILTERS = (
    ("all", "全部"), ("soon", "24小时到期"), ("approve", "待审批"),
    ("review", "待批阅"), ("risk", "风险"), ("confirm", "待确认"),
    ("done", "已处理"),
)


def _require_teacher(user):
    if str((user or {}).get("userType") or "").upper() == "STUDENT":
        raise AppException("NO_PERMISSION", "该接口仅教师端可用")
    return user or {}


def _require_student(user):
    if str((user or {}).get("userType") or "").upper() != "STUDENT":
        raise AppException("NO_PERMISSION", "该接口仅学生本人可用")
    return user or {}


def _group_value(todo_type):
    value = str(todo_type or "").upper()
    if any(x in value for x in ("RISK", "WARNING", "EXCEPTION", "OVERDUE")):
        return "risk"
    if any(x in value for x in ("REVIEW", "REPORT", "PROPOSAL", "SCORE")):
        return "review"
    if any(x in value for x in ("CONFIRM", "ACK", "RECEIPT")):
        return "confirm"
    return "approve"


def _group_expr():
    from app.models import UnifiedTodo
    value = func.upper(func.coalesce(UnifiedTodo.todo_type, ""))
    return case(
        (or_(value.like("%RISK%"), value.like("%WARNING%"),
             value.like("%EXCEPTION%"), value.like("%OVERDUE%")), "risk"),
        (or_(value.like("%REVIEW%"), value.like("%REPORT%"),
             value.like("%PROPOSAL%"), value.like("%SCORE%")), "review"),
        (or_(value.like("%CONFIRM%"), value.like("%ACK%"),
             value.like("%RECEIPT%")), "confirm"),
        else_="approve",
    )


def _todo_item(item):
    return {
        "id": item.get("todoId"),
        "group": _group_value(item.get("todoType")),
        "title": item.get("title") or "待办事项",
        "student": "",
        "module": item.get("sourceModule") or "",
        "status": "COMPLETED" if item.get("status") == "DONE" else item.get("status"),
        "level": "high" if item.get("priority") == "HIGH" else "normal",
        "deadline": item.get("dueAt") or "",
        "todoType": item.get("todoType"),
    }


def teacher_todos_page(user, group="all", page=1, page_size=20):
    """直接查询 t_unified_todo；禁止先构造完整移动聚合再切片。"""
    current = _require_teacher(user)
    requested = str(group or "all").lower()
    if requested not in {key for key, _ in FILTERS}:
        raise AppException("VALIDATION_ERROR", "group 不合法")
    page = max(1, int(page or 1))
    size = max(1, min(50, int(page_size or 20)))
    now = todo_svc._utc_now()
    soon = now + timedelta(hours=24)
    group_expr = _group_expr()

    with session() as db:
        visibility = todo_svc._visibility_cond(db, current)
        if visibility is None:
            return {
                "filters": [{"key": k, "label": label, "badge": 0} for k, label in FILTERS],
                "list": [], "page": page, "pageSize": size, "total": 0,
                "pendingCount": 0, "hasMore": False, "scopeMode": "FAIL_CLOSED",
            }

        from app.models import UnifiedTodo
        base = [UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False), visibility]
        pending = UnifiedTodo.status == "PENDING"
        counts = {key: 0 for key, _ in FILTERS}
        rows = db.execute(
            select(UnifiedTodo.todo_type, func.count())
            .where(*base, pending).group_by(UnifiedTodo.todo_type)
        ).all()
        for todo_type, amount in rows:
            n = int(amount or 0)
            counts["all"] += n
            counts[_group_value(todo_type)] += n
        counts["done"] = int(db.scalar(
            select(func.count()).select_from(UnifiedTodo)
            .where(*base, UnifiedTodo.status == "DONE")
        ) or 0)
        counts["soon"] = int(db.scalar(
            select(func.count()).select_from(UnifiedTodo).where(
                *base, pending, UnifiedTodo.due_at.is_not(None),
                UnifiedTodo.due_at >= now, UnifiedTodo.due_at <= soon,
            )
        ) or 0)

        conds = list(base)
        if requested == "done":
            conds.append(UnifiedTodo.status == "DONE")
        else:
            conds.append(pending)
            if requested == "soon":
                conds += [UnifiedTodo.due_at.is_not(None),
                          UnifiedTodo.due_at >= now, UnifiedTodo.due_at <= soon]
            elif requested != "all":
                conds.append(group_expr == requested)

        total = int(db.scalar(
            select(func.count()).select_from(UnifiedTodo).where(*conds)
        ) or 0)
        todo_rows = db.scalars(
            select(UnifiedTodo).where(*conds)
            .order_by(UnifiedTodo.due_at.is_(None).asc(),
                      UnifiedTodo.due_at.asc(), UnifiedTodo.id.desc())
            .offset((page - 1) * size).limit(size)
        ).all()
        items = [_todo_item(todo_svc._todo_dict(row)) for row in todo_rows]

    return {
        "filters": [{"key": k, "label": label, "badge": counts[k]} for k, label in FILTERS],
        "list": items, "page": page, "pageSize": size, "total": total,
        "pendingCount": counts["all"], "hasMore": page * size < total,
        "scopeMode": "WORKBENCH_VISIBILITY",
    }


def _risk_level_expr():
    from app.models import UnifiedTodo
    value = func.upper(func.coalesce(UnifiedTodo.todo_type, ""))
    title = func.upper(func.coalesce(UnifiedTodo.title, ""))
    return case(
        (or_(value.like("%OVERDUE%"), title.like("%高风险%"),
             title.like("%紧急%"), title.like("%URGENT%")), "HIGH"),
        else_="MEDIUM",
    )


def teacher_risk_students_page(user, level="all", page=1, page_size=20):
    """按最新风险待办去重后由数据库 offset/limit。"""
    current = _require_teacher(user)
    requested = str(level or "all").upper()
    if requested not in {"ALL", "HIGH", "MEDIUM"}:
        raise AppException("VALIDATION_ERROR", "level 必须是 all/HIGH/MEDIUM")
    page = max(1, int(page or 1))
    size = max(1, min(50, int(page_size or 20)))

    from app.models import SchoolClass, StudentProfile, UnifiedTodo
    group_expr = _group_expr()
    risk_level = _risk_level_expr()
    with session() as db:
        visibility = todo_svc._visibility_cond(db, current)
        if visibility is None:
            return {"list": [], "page": page, "pageSize": size, "total": 0,
                    "counts": {"HIGH": 0, "MEDIUM": 0}, "hasMore": False,
                    "scopeMode": "FAIL_CLOSED"}
        base = [
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False),
            UnifiedTodo.status == "PENDING", UnifiedTodo.student_id.is_not(None),
            visibility, group_expr == "risk",
        ]
        latest = (
            select(UnifiedTodo.student_id.label("student_id"),
                   func.max(UnifiedTodo.id).label("todo_id"))
            .where(*base).group_by(UnifiedTodo.student_id).subquery()
        )
        counts = {"HIGH": 0, "MEDIUM": 0}
        for risk, amount in db.execute(
            select(risk_level, func.count()).select_from(UnifiedTodo)
            .join(latest, latest.c.todo_id == UnifiedTodo.id)
            .group_by(risk_level)
        ).all():
            counts[str(risk or "MEDIUM")] = int(amount or 0)
        total = counts["HIGH"] + counts["MEDIUM"]
        query = (
            select(UnifiedTodo, StudentProfile, SchoolClass.class_name, risk_level)
            .join(latest, latest.c.todo_id == UnifiedTodo.id)
            .join(StudentProfile, and_(
                StudentProfile.id == latest.c.student_id,
                StudentProfile.tenant_id == _tid(),
                StudentProfile.is_deleted.is_(False),
            ))
            .outerjoin(SchoolClass, and_(
                SchoolClass.id == StudentProfile.class_id,
                SchoolClass.tenant_id == _tid(),
                SchoolClass.is_deleted.is_(False),
            ))
        )
        if requested != "ALL":
            query = query.where(risk_level == requested)
            total = counts[requested]
        result = db.execute(
            query.order_by(case((risk_level == "HIGH", 0), else_=1),
                           UnifiedTodo.id.desc())
            .offset((page - 1) * size).limit(size)
        ).all()

    items = []
    for todo, student, class_name, risk in result:
        value = str(risk or "MEDIUM")
        items.append({
            "id": str(student.id), "studentId": str(student.id),
            "studentNo": student.student_no or "", "name": student.real_name or "",
            "className": class_name or "", "risk": value, "riskLevel": value,
            "riskType": todo.todo_type or "风险事项",
            "task": todo.title or "风险事项待处理", "reason": todo.title or "",
            "pending": 1, "last": _iso(todo.updated_at or todo.created_at),
            "latestTime": _iso(todo.updated_at or todo.created_at),
            "stage": todo.source_module or "",
        })
    return {
        "list": items, "page": page, "pageSize": size, "total": total,
        "counts": counts, "hasMore": page * size < total,
        "scopeMode": "WORKBENCH_VISIBILITY",
    }


def _progress_page(user, page, size):
    from app.models import CsLeave, CsServiceStudent, CsWorkOrder
    from app.services import mobile_student_service as student_svc

    with session() as db:
        student = student_svc.resolve_student(db, user)
        if not student:
            return [], 0, 0
        domain = student_svc._resolve_domain_student(db, CsServiceStudent, student)
        if not domain:
            return [], 0, 0
        leaves = select(
            literal("leave").label("kind"), CsLeave.id.label("row_id"),
            literal("").label("subject"), CsLeave.status.label("status"),
            CsLeave.apply_time.label("event_time"),
        ).where(
            CsLeave.tenant_id == _tid(), CsLeave.cs_student_id == domain.id,
            CsLeave.is_deleted.is_(False),
        )
        orders = select(
            literal("workorder").label("kind"), CsWorkOrder.id.label("row_id"),
            CsWorkOrder.title.label("subject"), CsWorkOrder.status.label("status"),
            CsWorkOrder.created_at.label("event_time"),
        ).where(
            CsWorkOrder.tenant_id == _tid(), CsWorkOrder.cs_student_id == domain.id,
            CsWorkOrder.is_deleted.is_(False),
        )
        merged = union_all(leaves, orders).subquery()
        total = int(db.scalar(select(func.count()).select_from(merged)) or 0)
        unread = int(db.scalar(
            select(func.count()).select_from(merged).where(or_(
                and_(merged.c.kind == "leave", merged.c.status == "PENDING_REVIEW"),
                and_(merged.c.kind == "workorder", merged.c.status == "PENDING_HANDLE"),
            ))
        ) or 0)
        rows = db.execute(
            select(merged).order_by(merged.c.event_time.desc(), merged.c.row_id.desc())
            .offset((page - 1) * size).limit(size)
        ).all()

    items = []
    for row in rows:
        leave = row.kind == "leave"
        pending = row.status == ("PENDING_REVIEW" if leave else "PENDING_HANDLE")
        title = (f"你的请假申请当前状态：{row.status}" if leave
                 else f"工单「{row.subject or '未命名'}」当前状态：{row.status}")
        items.append({
            "id": f"{row.kind}-{row.row_id}", "messageId": None,
            "kind": "PROGRESS_AGG", "title": title, "module": "服务进度",
            "level": "normal", "time": _iso(row.event_time), "deadline": None,
            "read": not pending, "status": row.status, "link": "campus-service",
        })
    return items, total, unread


def _message_item(item):
    emergency = bool(item.get("emergency"))
    return {
        "id": str(item.get("messageId") or ""),
        "messageId": str(item.get("messageId") or ""),
        "kind": "UNIFIED_MESSAGE", "title": item.get("title") or "",
        "content": item.get("summary") or "",
        "module": item.get("category") or item.get("msgType") or "通知",
        "level": "high" if emergency else "normal",
        "time": item.get("createdAt"), "deadline": item.get("expireAt"),
        "read": str(item.get("readStatus") or "").upper() == "READ",
        "status": item.get("readStatus"), "link": item.get("actionKey") or "",
        "emergency": emergency,
        "receipt": bool(item.get("requireAck") and not item.get("acked")
                        and not item.get("withdrawn")),
        "requireAck": bool(item.get("requireAck")),
        "acked": bool(item.get("acked")), "withdrawn": bool(item.get("withdrawn")),
    }


def _student_todo_item(item):
    pending = str(item.get("status") or "").upper() == "PENDING"
    return {
        "id": f"todo-{item.get('todoId')}", "messageId": None,
        "kind": "TODO_AGG", "title": item.get("title") or "待办事项",
        "module": item.get("sourceModule") or "待办",
        "level": "high" if item.get("priority") == "HIGH" else "normal",
        "time": item.get("createdAt"), "deadline": item.get("dueAt"),
        "read": not pending, "status": item.get("status"),
        "link": item.get("sourceModule") or "",
    }


def student_messages_page(user, tab="todo", page=1, page_size=20):
    """三个标签分别查询数据库并分页，禁止调用 my_messages() 后切片。"""
    current = _require_student(user)
    tab = str(tab or "todo").lower()
    if tab not in {"todo", "notice", "progress"}:
        raise AppException("VALIDATION_ERROR", "tab 必须是 todo/notice/progress")
    page = max(1, int(page or 1))
    size = max(1, min(50, int(page_size or 20)))

    from app.services import notification_preference_service as preferences
    enabled = preferences.enabled_categories(current, ["todo", "notice", "progress"])
    if tab not in enabled:
        items, total = [], 0
    elif tab == "todo":
        rows, total = todo_svc.list_todos(current, page=page, page_size=size)
        items = [_student_todo_item(row) for row in rows]
    elif tab == "notice":
        rows, total = message_svc.list_messages(current, page=page, page_size=size)
        items = [_message_item(row) for row in rows]
    else:
        items, total, _ = _progress_page(current, page, size)

    pending = todo_svc.list_todos(current, status="PENDING", page=1, page_size=1)[1]
    message_counts = message_svc.count_messages(current)
    _, _, progress_unread = _progress_page(current, 1, 1)
    badges = {
        "todo": int(pending) if "todo" in enabled else 0,
        "notice": int(message_counts.get("unread") or 0) if "notice" in enabled else 0,
        "progress": int(progress_unread) if "progress" in enabled else 0,
    }
    emergency = []
    if "notice" in enabled:
        rows, _ = message_svc.list_messages(
            current, priority="EMERGENCY", pending_ack=True, page=1, page_size=5
        )
        emergency = [_message_item(row) for row in rows]

    return {
        "tabs": [
            {"key": "todo", "label": "待办", "badge": badges["todo"]},
            {"key": "notice", "label": "通知", "badge": badges["notice"]},
            {"key": "progress", "label": "服务进度", "badge": badges["progress"]},
        ],
        "tab": tab, "list": items, "page": page, "pageSize": size,
        "total": int(total), "hasMore": page * size < int(total),
        "emergencyPending": emergency,
    }


def read_messages_batch(user, message_ids):
    """当前学生可见消息一次 UPDATE，最多100条；不改变确认回执。"""
    current = _require_student(user)
    from app.models import UnifiedMessage

    values = list(message_ids or [])
    if len(values) > 100:
        raise AppException("VALIDATION_ERROR", "单次最多处理100条消息")
    ids = []
    for value in values:
        raw = str(value or "").replace("msg-", "").strip()
        if raw.isdigit():
            ids.append(int(raw))
    ids = list(dict.fromkeys(ids))
    now = datetime.utcnow()
    if not ids:
        return {"requestedCount": 0, "affectedCount": 0, "updatedAt": _iso(now)}

    with session() as db:
        visibility = message_svc._visibility(current)
        if visibility is None:
            affected = 0
        else:
            result = db.execute(
                sql_update(UnifiedMessage).where(
                    UnifiedMessage.tenant_id == _tid(),
                    UnifiedMessage.is_deleted.is_(False),
                    UnifiedMessage.id.in_(ids),
                    UnifiedMessage.status != "READ",
                    visibility,
                ).values(
                    status="READ", read_at=now,
                    version=func.coalesce(UnifiedMessage.version, 0) + 1,
                )
            )
            affected = max(0, int(result.rowcount or 0))
            db.commit()

    from app.services import mobile_student_service as student_svc
    student_svc.invalidate_home_cache(current)
    return {
        "requestedCount": len(ids), "affectedCount": affected,
        "updatedAt": _iso(now),
    }


def teacher_workbench(user, page_size=8):
    """单个HTTP请求返回教师首屏全部数据。"""
    current = _require_teacher(user)
    snapshot = snapshot_svc.snapshot(current, page_size=max(1, min(20, int(page_size or 8))))
    risk = teacher_risk_students_page(current, "all", 1, 5)
    summary = snapshot.get("summary") or {}
    count = snapshot.get("count") or {}
    todos = snapshot.get("todos") or {}
    by_type = count.get("byType") or {}

    metrics = [
        {"key": "pending", "label": "待我处理", "value": int(summary.get("pending") or 0)},
        {"key": "overdue", "label": "已逾期", "value": int(summary.get("overdue") or 0)},
        {"key": "near", "label": "24h到期", "value": int(summary.get("nearDeadline") or 0)},
        {"key": "done", "label": "今日完成", "value": int(summary.get("doneToday") or 0)},
    ]
    due = [{
        "id": item.get("todoId"), "title": item.get("title") or "",
        "module": item.get("sourceModule") or item.get("todoType") or "",
        "student": "", "deadline": item.get("dueAt") or "",
        "status": item.get("status") or "PENDING", "todoType": item.get("todoType"),
    } for item in (todos.get("items") or [])]

    return {
        "contextTitle": summary.get("role") or current.get("currentRoleCode") or "",
        "metrics": metrics, "pendingTotal": int(summary.get("pending") or 0),
        "dueSoon": due, "riskStudents": risk.get("list") or [], "recent": [],
        "messageSummary": snapshot.get("messages") or {}, "_real": True,
        "_role": summary.get("role") or current.get("currentRoleCode") or "",
        "_byType": by_type,
        "partialFailures": {"count": False, "todos": False, "risk": False},
    }
