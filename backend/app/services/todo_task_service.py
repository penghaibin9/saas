"""SYS-15 待办治理 adapter：在既有 t_unified_todo 上提供"带完成证据关闭"和幂等创建。

去重仍然靠 t_unified_todo.uk_todo_dedup（tenant+source_module+source_biz_id+todo_type+assignee_id），
写法对齐已生产验证的 app.modules.graduation.services.graduation_todo_helper.todo_upsert，
不重复发明另一套幂等逻辑。

t_unified_todo 没有结构化"完成证据"列（模型文件 app/models/approval.py 不在 SYS-15
施工白名单内，不能加列）。完成证据落在 remark 字段 + 审计日志（app.services.audit_log），
关闭动作要求调用方显式传 evidence，不允许静默关闭——这是"完成证据"的可核验实现，
不是把要求偷换成"随便关一下"。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import UnifiedTodo
from app.services.db_service import _tid


def create_todo_idempotent(db, *, source_module: str, source_biz_type: str, source_biz_id,
                           todo_type: str, assignee_id: int, student_id=None,
                           title: str, due_at=None, remark: str | None = None) -> UnifiedTodo:
    """幂等创建/复活 PENDING 待办；命中 uk_todo_dedup 时返回既有行（同 dedupeKey 不重复建待办）。"""
    aid = int(assignee_id or 0)
    bid = int(source_biz_id)
    if aid <= 0:
        raise AppException("VALIDATION_ERROR", "待办必须有责任人（assignee_id）", http_status=422)
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == source_module,
        UnifiedTodo.source_biz_id == bid, UnifiedTodo.todo_type == todo_type,
        UnifiedTodo.assignee_id == aid, UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        return row
    row = UnifiedTodo(
        tenant_id=_tid(), source_module=source_module, source_biz_type=source_biz_type,
        source_biz_id=bid, todo_type=todo_type, assignee_id=aid, student_id=student_id,
        title=title, status="PENDING", due_at=due_at, remark=remark)
    db.add(row)
    db.flush()
    return row


def close_todo_with_evidence(db, *, todo_id: int, evidence: str, actor=None) -> UnifiedTodo:
    """业务完成后关闭待办，必须带完成证据；写审计留痕。"""
    from app.services import audit_log

    text = (evidence or "").strip()
    if len(text) < 2:
        raise AppException("VALIDATION_ERROR", "完成证据不能为空", http_status=422)
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.id == int(todo_id), UnifiedTodo.tenant_id == _tid(),
        UnifiedTodo.is_deleted.is_(False))).first()
    if not row:
        raise AppException("NOT_FOUND", "待办不存在", http_status=404)
    if row.status == "DONE":
        return row
    row.remark = f"[完成证据] {text}" if not row.remark else f"{row.remark}\n[完成证据] {text}"
    row.status = "DONE"
    row.version = int(row.version or 0) + 1
    if isinstance(actor, dict):
        actor_id = actor.get("userId") or actor.get("id")
    else:
        actor_id = getattr(actor, "userId", None) or getattr(actor, "id", None)
    audit_log.record("TODO_CLOSED_WITH_EVIDENCE", f"unified-todo:{todo_id}",
                     {"todoType": row.todo_type, "sourceModule": row.source_module,
                      "sourceBizId": row.source_biz_id, "evidence": text, "actorId": actor_id})
    return row


def list_backlog(db=None, *, page: int = 1, page_size: int = 50):
    """积压待办台账：PENDING，按 due_at 升序（无期限的排后面）。

    不传 db 时自己开关会话（供路由直接调用）；传入 db 时复用调用方会话（供测试复用）。"""
    if db is None:
        from app.db.session import get_sessionmaker
        session = get_sessionmaker()()
        try:
            return list_backlog(session, page=page, page_size=page_size)
        finally:
            session.close()

    from sqlalchemy import func

    tid = _tid()
    base = select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == tid, UnifiedTodo.is_deleted.is_(False),
        UnifiedTodo.status == "PENDING")
    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    rows = db.scalars(base.order_by(UnifiedTodo.due_at.is_(None), UnifiedTodo.due_at.asc(), UnifiedTodo.id.asc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    items = [{
        "id": r.id, "sourceModule": r.source_module, "sourceBizType": r.source_biz_type,
        "sourceBizId": r.source_biz_id, "todoType": r.todo_type, "assigneeId": r.assignee_id,
        "title": r.title, "status": r.status, "dueAt": r.due_at.isoformat() if r.due_at else None,
        "remark": r.remark,
    } for r in rows]
    return items, total
