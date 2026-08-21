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
学生（student-mini）：**只按 `assignee_id == 当前 User.id` 判断收件人**。
  `student_id` 永远只是“这条业务待办处理的是哪名学生”的 subject，不是 audience；老师审批
  学生请假/资助/违纪时同样会填 student_id，绝不能因此把老师的待办暴露给该学生。
  真正需要学生处理的待办，生产者必须通过正式账号绑定把 `assignee_id` 写成学生 User.id。

`uid` 无法解析为正整数时（演示/异常令牌）绝不回落成 `assignee_id == 0`，否则会把
全部池待办暴露给身份不明的调用方；此时按 fail-closed 返回空。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, or_, select

from app.services.db_service import _iso, _tid, session
from app.services.todo_route_registry import resolve_todo_route

# 契约兼容：返回结构对齐 docs/05 §04 待办审批消息 API（前端 PC + 小程序均按此消费）
_TODO_DONE = "DONE"
_TODO_PENDING = "PENDING"

# TP-W12：generic complete（本文件 complete_todo + /todos/{id}/complete）之前对任意
# 可见的 PENDING UnifiedTodo 都直接翻成 DONE——LEAVE_APPROVAL 这类待办可以被"标记
# 完成"，但真实 WorkflowTask/Leave 仍然 PENDING，业务对象与待办列表口径分叉。
#
# 已核实：下面枚举的每个 todo_type 都由各自业务模块在真实审批/处理动作完成时，
# 用自己的 `_todo_done()`/`todo_done()` 帮助函数同步 UnifiedTodo → DONE（
# affairs_leave_service/affairs_aid_service/affairs_risk_service/
# affairs_discipline_service/affairs_funding_service/affairs_dorm_service/
# academic_affairs_change_service/academic_affairs_grade_core_service/
# academic_affairs_schedule_change_service/academic_affairs_warning_service/
# employment_service/graduation_todo_helper/internship_todo_helper/
# affairs_operations_service），完全不经过这里——generic complete 从未是它们的
# 真实完成路径。因此这些 todo_type 归为 DOMAIN_COMMAND：只能由对应业务动作完成，
# generic complete 一律拒绝。未在下表登记的 todo_type 默认也是 DOMAIN_COMMAND
# （fail-closed）；只有显式登记为 ACK_ONLY 的类型才允许 generic complete——
# 目前没有真正的纯确认类待办，`GENERIC_ACK` 只是测试/未来占位，不代表已有生产
# 类型属于这一类。
_COMPLETION_MODE_DOMAIN_COMMAND = "DOMAIN_COMMAND"
_COMPLETION_MODE_ACK_ONLY = "ACK_ONLY"

_DOMAIN_COMMAND_TODO_TYPES: frozenset[str] = frozenset({
    "LEAVE_APPROVAL", "LEAVE_OVERDUE", "LEAVE_CANCEL", "LEAVE_EXTENSION",
    "AID_APPROVAL", "AID_ADJUST",
    "FUNDING_APPROVAL",
    "DISCIPLINE_APPROVAL", "DISCIPLINE_REMOVE",
    "DORM_TRANSFER", "DORM_EXCEPTION",
    "RISK_HANDLE",
    "AA_STATUS_APPROVAL", "AA_SCHEDULE_CHANGE_APPROVAL", "AA_GRADE_ENTRY",
    "ACAD_WARNING_HANDLE",
    "EMPLOYMENT_FOLLOWUP",
    "GD_PROPOSAL_REVIEW", "GD_TOPIC_CHANGE_REVIEW", "GD_FINAL_REVIEW", "GD_DEFENSE_SCORE",
    "INTERN_WEEKLY_REVIEW", "INTERN_LEAVE_APPROVAL", "INTERN_EXCEPTION_HANDLE",
    "INTERN_VISIT_RECTIFY",
    "MATERIAL_REVIEW",
})

#: 显式允许 generic complete 的 ACK_ONLY 类型——当前没有真实生产类型进入这个集合。
_ACK_ONLY_TODO_TYPES: frozenset[str] = frozenset()


def _completion_mode(todo_type: str | None) -> str:
    tt = str(todo_type or "").strip().upper()
    if tt in _ACK_ONLY_TODO_TYPES:
        return _COMPLETION_MODE_ACK_ONLY
    return _COMPLETION_MODE_DOMAIN_COMMAND


def todo_completion_mode_snapshot() -> dict[str, str]:
    """供 CI/合同测试枚举：新增业务 todo_type 时如果忘了登记进
    `_DOMAIN_COMMAND_TODO_TYPES`，运行时默认值已经 fail-closed 成
    DOMAIN_COMMAND（安全），但这份快照仍然把"已知业务类型"显式列出来，
    方便测试直接断言 LEAVE/RISK/GRADE 等具体类型，而不是只测默认行为。"""
    return {tt: _COMPLETION_MODE_DOMAIN_COMMAND for tt in sorted(_DOMAIN_COMMAND_TODO_TYPES)}


def _uid(user: dict | None) -> int:
    """使用全系统统一身份映射解析待办办理人；无法解析时继续 fail-closed。"""
    from app.services.message_identity import resolve_message_user_id

    return int(resolve_message_user_id(user or {}) or 0)


def _is_student(user: dict | None) -> bool:
    return str((user or {}).get("userType") or "").strip().upper() == "STUDENT"


def _self_student_id(db, user: dict | None) -> int:
    """学生本人学籍档案 ID（仅供其它需要 subject 身份的调用；不参与 todo audience 判定）。"""
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
        # P1 audience hardening：student_id 是 subject，不是 recipient。
        # 只有显式指派给当前学生 User.id 的待办才属于“我的待办”。
        return UnifiedTodo.assignee_id == uid if uid else None

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
        # TP-W13：范围内学生 ID 不再整批拉回 Python 再拼 IN 字面量列表——万人学院会
        # 把这条 SQL 文本、网络往返和 Python 内存都拉大。改成把 StudentProfile 查询
        # 作为子查询直接交给数据库做 `student_id IN (SELECT id FROM ...)`，范围内
        # 零个学生时子查询天然不命中任何行，不需要再单独判断空列表。
        stu_id_subquery = select(StudentProfile.id).where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.class_id.in_(allowed),
            StudentProfile.is_deleted.is_(False))
        parts.append(and_(UnifiedTodo.assignee_id == 0,
                          UnifiedTodo.student_id.in_(stu_id_subquery)))
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


def _todo_dict(row, *, client: str = "pc") -> dict:
    record_id = str(row.source_biz_id) if row.source_biz_id else None
    route = resolve_todo_route(row.todo_type, record_id, client=client)
    # TP-W12：COMPLETE 只在 generic complete 真的会被接受时才出现在 allowedActions
    # 里——DOMAIN_COMMAND 类型点了也会被 complete_todo() 拒绝，与其让前端露出一个
    # 注定失败的按钮，不如干脆不给这个动作；这类待办只能靠 OPEN 去业务页真实处理。
    allowed_actions = (
        ["COMPLETE"] if row.status == _TODO_PENDING
        and _completion_mode(row.todo_type) == _COMPLETION_MODE_ACK_ONLY
        else []
    )
    if route:
        allowed_actions.insert(0, "OPEN")
    version = int(getattr(row, "version", 0) or 0)
    data = {
        "todoId": str(row.id),
        "todoType": row.todo_type,
        "title": row.title,
        # Legacy aliases stay during V3 migration; canonical V3 names are below.
        "bizType": row.source_biz_type,
        "bizId": record_id,
        "sourceBizType": row.source_biz_type,
        "sourceBizId": record_id,
        # P1-07 typed deep-link DTO：所有客户端只消费这些字段，不再按标题/todoType 猜路由。
        "recordId": record_id,
        "routeName": route.get("routeName") if route else None,
        "routeParams": route.get("routeParams") if route else {},
        "query": route.get("query") if route else {},
        "routePath": route.get("path") if route else None,
        "routeExact": bool(route and route.get("exact")),
        "focusMode": route.get("focusMode") if route else "NONE",
        "allowedActions": allowed_actions,
        "version": version,
        "expectedVersion": version if version > 0 else None,
        "sourceModule": row.source_module,
        "priority": _priority(row),
        "status": row.status,
        "dueAt": _iso(row.due_at) if row.due_at else None,
        "createdAt": _iso(row.created_at) if row.created_at else None,
    }
    # T1 Teacher V3 pass-through: this helper owns no route map.  If the shared
    # route authority cannot prove a teacherMini target yet, action stays None.
    if client == "teacherMini":
        from app.services.teacher_mobile_todo_projection_service import project_teacher_todo
        projected = project_teacher_todo(data)
        data["action"] = projected.get("action") if projected else None
    return data


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
               page: int = 1, page_size: int = 20, *, client: str = "pc") -> tuple[list[dict], int]:
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
        return [_todo_dict(r, client=client) for r in rows], int(total)


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


def get_todo(user: dict, todo_id: str, *, client: str = "pc") -> dict | None:
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
        d = _todo_dict(row, client=client)
        # TP-W12：与 _todo_dict() 的 allowedActions 同一口径，不能各算各的——
        # 否则详情页的 actions 字段又会把 DOMAIN_COMMAND 类型的 COMPLETE 露出来。
        d["actions"] = (
            ["COMPLETE"] if row.status == _TODO_PENDING
            and _completion_mode(row.todo_type) == _COMPLETION_MODE_ACK_ONLY
            else []
        )
        return d


def complete_todo(user: dict, todo_id: str, comment: str | None = None) -> tuple[dict | None, str | None]:
    """完成待办。返回 (数据, 错误码)；错误码 NOT_FOUND / ALREADY_DONE /
    DOMAIN_COMMAND_REQUIRED 由路由层转对应异常。

    TP-W12：这是唯一一处"generic complete"入口。DOMAIN_COMMAND 类型的待办
    （LEAVE_APPROVAL/RISK_HANDLE/AA_GRADE_ENTRY 等，见
    `_DOMAIN_COMMAND_TODO_TYPES`）必须由各自业务模块的真实审批/处理动作
    同步完成，这里直接拒绝——否则待办列表会显示"已完成"，但背后的
    WorkflowTask/Leave/Risk 等真实业务对象仍然 PENDING，两边口径分叉。
    """
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
        if _completion_mode(row.todo_type) != _COMPLETION_MODE_ACK_ONLY:
            return None, "DOMAIN_COMMAND_REQUIRED"
        row.status = _TODO_DONE
        if comment:
            row.remark = (comment or "")[:500]
        db.commit()
        return {"todoId": str(row.id), "status": _TODO_DONE}, None


# ────────────────────────── 消息 ──────────────────────────

def list_messages(user: dict, read_status: Optional[str] = None,
                  page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    from app.services import message_center_service as mc
    return mc.list_messages_compat(user, read_status=read_status, page=page, page_size=page_size)


def count_messages(user: dict) -> dict:
    from app.services import message_center_service as mc
    return mc.count_messages_compat(user)


def read_message(user: dict, message_id: str) -> dict | None:
    from app.services import message_center_service as mc
    return mc.read_message_compat(user, message_id)
