"""工作台·待办与消息真实数据服务（工作台积木 B1「待办磁贴」/ B6「消息」的后端口径）。

背景与定位
────────────────────────────────────────────────────────────
`api/v1/todos.py` 此前直接返回 `mock_data.MOCK_TODOS` 静态列表：无租户过滤、无按人过滤，
所有学校所有教职工看到同一份演示待办。而真实待办数据其实一直在写——请假/违纪/资助/困难认定/
风险/教务异动/调停课等 9+ 处业务在 `t_unified_todo` 落库（含 `assignee_id`、`student_id`、`due_at`）。
本服务把「读端」接回真库，使工作台的数字与业务库一致。

可见性口径（工作台语义 = 「我要处理的事」，不是「全校所有待办」）
────────────────────────────────────────────────────────────
教职工：
  1) `assignee_id == 本人`           —— 明确指派给我的；
  2) `assignee_id == 0`（学院池待办）—— 仅当该待办关联学生落在我的数据范围内才可见。
     范围由 `affairs_security.build_affairs_context(...).allowed_class_ids(db)` 统一裁定：
     None=本租户全量（TENANT_ALL，如校级管理员）；空集=fail-closed（未配范围一律看不到）。
  注意与 `mobile_teacher_service._filter_by_assignee_todos` 的差异：移动端那支在 COLLEGE 分支下
  放行了全部 `assignee_id==0`（不校验学生归属），本服务按学生范围收紧，避免跨学院可见。
学生（student-mini）：只看本人——`assignee_id == 本人` 或 `student_id == 本人学籍档案`。

`uid` 无法解析为正整数时（演示/异常令牌）绝不回落成 `assignee_id == 0`，否则会把
全部池待办暴露给身份不明的调用方；此时按 fail-closed 返回空。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, or_, select

from app.services.db_service import _iso, _tid, session

# 契约兼容：返回结构对齐 docs/05 §04 待办审批消息 API（前端 PC + 小程序均按此消费）
_TODO_DONE = "DONE"
_TODO_PENDING = "PENDING"


def _uid(user: dict | None) -> int:
    """令牌 userId → 数字用户 ID。`db-123`/`u_123` 前缀剥离；不可解析返回 0（调用方按 fail-closed 处理）。"""
    raw = str((user or {}).get("userId") or "")
    for prefix in ("db-", "u_"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _is_student(user: dict | None) -> bool:
    return str((user or {}).get("userType") or "").strip().upper() == "STUDENT"


def _self_student_id(db, user: dict | None) -> int:
    """学生本人学籍档案 ID（按令牌 studentNo 在本租户内解析；租户内学号唯一）。"""
    from app.models import StudentProfile
    sn = str((user or {}).get("studentNo") or "").strip()
    if not sn:
        return 0
    row = db.scalar(select(StudentProfile.id).where(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.student_no == sn,
        StudentProfile.is_deleted.is_(False)))
    return int(row) if row else 0


def _visibility_cond(db, user: dict):
    """返回 SQLAlchemy 可见性条件；None 表示「查不到任何数据」（fail-closed）。"""
    from app.models import StudentProfile, UnifiedTodo
    uid = _uid(user)

    if _is_student(user):
        sid = _self_student_id(db, user)
        parts = []
        if uid:
            parts.append(UnifiedTodo.assignee_id == uid)
        if sid:
            parts.append(UnifiedTodo.student_id == sid)
        return or_(*parts) if parts else None

    # 教职工：本人指派 + 范围内池待办
    from app.core.affairs_security import build_affairs_context
    ctx = build_affairs_context(user, db)
    allowed = ctx.allowed_class_ids(db)          # None=全租户；set()=fail-closed
    parts = []
    if uid:
        parts.append(UnifiedTodo.assignee_id == uid)
    if allowed is None:
        parts.append(UnifiedTodo.assignee_id == 0)          # 校级：池待办全可见
    elif allowed:
        stu_ids = list(db.scalars(select(StudentProfile.id).where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.class_id.in_(list(allowed)),
            StudentProfile.is_deleted.is_(False))).all())
        if stu_ids:
            parts.append(and_(UnifiedTodo.assignee_id == 0,
                              UnifiedTodo.student_id.in_(stu_ids)))
    # allowed == set() → 未配范围，只保留「明确指派给我的」，不放行任何池待办
    return or_(*parts) if parts else None


def _utc_now() -> datetime:
    """库内 created_at/updated_at/due_at 均由 CommonMixin 的 datetime.utcnow 写入（naive UTC），
    比较基准必须同为 UTC，不能用本地时间，否则中国时区会整体偏 8 小时。"""
    return datetime.utcnow()


def _local_today_start_utc() -> datetime:
    """「今日」是使用者的本地概念（settings.TIMEZONE_OFFSET_HOURS，默认 +8），
    但存储是 UTC：先取本地零点，再换算回 UTC 作为比较边界。"""
    from app.core.config import settings
    offset = timedelta(hours=int(getattr(settings, "TIMEZONE_OFFSET_HOURS", 8) or 0))
    local_midnight = (_utc_now() + offset).replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight - offset


def _priority(row) -> str:
    """t_unified_todo 无 priority 列：按「是否逾期/临期」与风险类型派生，不臆造业务优先级。"""
    tt = (row.todo_type or "").upper()
    if "RISK" in tt or "OVERDUE" in tt:
        return "HIGH"
    if row.due_at and row.due_at <= _utc_now() + timedelta(hours=24):
        return "HIGH"
    return "NORMAL"


def _todo_dict(row) -> dict:
    return {
        "todoId": str(row.id),
        "todoType": row.todo_type,
        "title": row.title,
        "bizType": row.source_biz_type,
        "bizId": str(row.source_biz_id) if row.source_biz_id else None,
        "sourceModule": row.source_module,
        "priority": _priority(row),
        "status": row.status,
        "dueAt": _iso(row.due_at) if row.due_at else None,
        "createdAt": _iso(row.created_at) if row.created_at else None,
    }


def _msg_dict(row) -> dict:
    return {
        "messageId": str(row.id),
        "msgType": row.message_type,
        "title": row.title,
        "summary": row.content,
        "readStatus": row.status,
        # actionUrl 只在能确定真实落点时给出；无法确定时返回 None，不编造前端路由造成死链
        "actionUrl": None,
        "createdAt": _iso(row.created_at) if row.created_at else None,
    }


# ────────────────────────── 待办 ──────────────────────────

def list_todos(user: dict, status: Optional[str] = None, todo_type: Optional[str] = None,
               page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    from app.models import UnifiedTodo
    with session() as db:
        vis = _visibility_cond(db, user)
        if vis is None:
            return [], 0
        conds = [UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False), vis]
        if status:
            conds.append(UnifiedTodo.status == status)
        if todo_type:
            conds.append(UnifiedTodo.todo_type == todo_type)
        total = db.scalar(select(func.count()).select_from(UnifiedTodo).where(*conds)) or 0
        rows = db.scalars(select(UnifiedTodo).where(*conds)
                          .order_by(UnifiedTodo.status.asc(), UnifiedTodo.due_at.is_(None).asc(),
                                    UnifiedTodo.due_at.asc(), UnifiedTodo.id.desc())
                          .offset(max(0, (page - 1) * page_size)).limit(page_size)).all()
        return [_todo_dict(r) for r in rows], int(total)


def count_todos(user: dict) -> dict:
    """红点角标：仅统计 PENDING，并按 todo_type 分组（工作台磁贴直接消费）。"""
    from app.models import UnifiedTodo
    with session() as db:
        vis = _visibility_cond(db, user)
        if vis is None:
            return {"total": 0, "byType": {}}
        conds = [UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False),
                 UnifiedTodo.status == _TODO_PENDING, vis]
        rows = db.execute(select(UnifiedTodo.todo_type, func.count())
                          .where(*conds).group_by(UnifiedTodo.todo_type)).all()
        by_type = {t: int(n) for t, n in rows}
        return {"total": sum(by_type.values()), "byType": by_type}


def summary(user: dict) -> dict:
    """工作台顶部汇总：pending / overdue / nearDeadline / doneToday，全部按本人可见范围收敛。

    取代 db_service.todo_summary()：那支只过滤 tenant_id，不分人——辅导员会看到全校待办数；
    且 overdue / nearDeadline 恒为硬编码 0，doneToday 实际返回的是历史全部已完成数。
    """
    from app.models import UnifiedTodo
    now = _utc_now()
    soon = now + timedelta(hours=24)
    today_start = _local_today_start_utc()
    with session() as db:
        vis = _visibility_cond(db, user)
        if vis is None:
            return {"pending": 0, "overdue": 0, "nearDeadline": 0, "doneToday": 0}
        base = [UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False), vis]

        def _n(*extra):
            return int(db.scalar(select(func.count()).select_from(UnifiedTodo)
                                 .where(*base, *extra)) or 0)

        pending_cond = UnifiedTodo.status == _TODO_PENDING
        return {
            "pending": _n(pending_cond),
            "overdue": _n(pending_cond, UnifiedTodo.due_at.is_not(None), UnifiedTodo.due_at < now),
            "nearDeadline": _n(pending_cond, UnifiedTodo.due_at.is_not(None),
                               UnifiedTodo.due_at >= now, UnifiedTodo.due_at <= soon),
            "doneToday": _n(UnifiedTodo.status == _TODO_DONE,
                            UnifiedTodo.updated_at.is_not(None),
                            UnifiedTodo.updated_at >= today_start),
        }


def get_todo(user: dict, todo_id: str) -> dict | None:
    """详情：不在可见范围内一律返回 None（由路由层转 404，不泄漏存在性）。"""
    from app.models import UnifiedTodo
    with session() as db:
        vis = _visibility_cond(db, user)
        if vis is None:
            return None
        try:
            tid_int = int(todo_id)
        except (TypeError, ValueError):
            return None
        row = db.scalar(select(UnifiedTodo).where(
            UnifiedTodo.id == tid_int, UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.is_deleted.is_(False), vis))
        if not row:
            return None
        d = _todo_dict(row)
        d["actions"] = ["COMPLETE"] if row.status == _TODO_PENDING else []
        return d


def complete_todo(user: dict, todo_id: str, comment: str | None = None) -> tuple[dict | None, str | None]:
    """完成待办。返回 (数据, 错误码)；错误码 NOT_FOUND / ALREADY_DONE 由路由层转对应异常。"""
    from app.models import UnifiedTodo
    with session() as db:
        vis = _visibility_cond(db, user)
        if vis is None:
            return None, "NOT_FOUND"
        try:
            tid_int = int(todo_id)
        except (TypeError, ValueError):
            return None, "NOT_FOUND"
        row = db.scalar(select(UnifiedTodo).where(
            UnifiedTodo.id == tid_int, UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.is_deleted.is_(False), vis))
        if not row:
            return None, "NOT_FOUND"
        if row.status == _TODO_DONE:
            return None, "ALREADY_DONE"
        row.status = _TODO_DONE
        if comment:
            row.remark = (comment or "")[:500]
        db.commit()
        return {"todoId": str(row.id), "status": _TODO_DONE}, None


# ────────────────────────── 消息 ──────────────────────────

def _msg_cond(user: dict):
    from app.models import UnifiedMessage
    uid = _uid(user)
    return (UnifiedMessage.receiver_id == uid) if uid else None


def list_messages(user: dict, read_status: Optional[str] = None,
                  page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    from app.models import UnifiedMessage
    with session() as db:
        vis = _msg_cond(user)
        if vis is None:
            return [], 0
        conds = [UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False), vis]
        if read_status:
            conds.append(UnifiedMessage.status == read_status)
        total = db.scalar(select(func.count()).select_from(UnifiedMessage).where(*conds)) or 0
        rows = db.scalars(select(UnifiedMessage).where(*conds)
                          .order_by(UnifiedMessage.id.desc())
                          .offset(max(0, (page - 1) * page_size)).limit(page_size)).all()
        return [_msg_dict(r) for r in rows], int(total)


def count_messages(user: dict) -> dict:
    from app.models import UnifiedMessage
    with session() as db:
        vis = _msg_cond(user)
        if vis is None:
            return {"unread": 0}
        n = db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False),
            UnifiedMessage.status == "UNREAD", vis)) or 0
        return {"unread": int(n)}


def read_message(user: dict, message_id: str) -> dict | None:
    from app.models import UnifiedMessage
    with session() as db:
        vis = _msg_cond(user)
        if vis is None:
            return None
        try:
            mid = int(message_id)
        except (TypeError, ValueError):
            return None
        row = db.scalar(select(UnifiedMessage).where(
            UnifiedMessage.id == mid, UnifiedMessage.tenant_id == _tid(),
            UnifiedMessage.is_deleted.is_(False), vis))
        if not row:
            return None
        if row.status != "READ":
            row.status = "READ"
            row.read_at = _utc_now()          # 与 CommonMixin 的 utcnow 写入口径一致
            db.commit()
        return {"messageId": str(row.id), "readStatus": "READ"}
