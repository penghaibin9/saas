"""统一待办治理：复用既有去重键，只按可核验的本校来源结果修复失效提醒。

关闭不办理源业务；源记录和待办加锁核验，待办版本及审计同事务。
未接入核验的业务类型返回明确拒绝，由原业务完成回写。
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


def _completed_source(db, row):
    """仅接受已核对原业务完成回写的来源；未知来源不能靠文字证明完成。"""
    from app.models import GraduationProposal, GraduationFinal, AaGradeTask, InternshipLeave
    from app.models.affairs_funding_ext import FeeReduction, StudentLoan

    sources = {
        ("graduation", "GD_PROPOSAL", "GD_PROPOSAL_REVIEW"): (GraduationProposal, {"APPROVED", "REJECTED"}),
        ("graduation", "GD_FINAL", "GD_FINAL_REVIEW"): (GraduationFinal, {"APPROVED", "REJECTED"}),
        ("academic-affairs", "AA_GRADE_TASK", "AA_GRADE_ENTRY"): (AaGradeTask, {"SUBMITTED", "ACADEMIC_REVIEW", "PUBLISHED", "ARCHIVED"}),
        ("internship", "INTERN_LEAVE", "INTERN_LEAVE_APPROVAL"): (InternshipLeave, {"APPROVED", "REJECTED", "WITHDRAWN", "RETURNED", "OVERDUE"}),
    }
    from app.services.affairs_funding_todo_service import REDUCTION_TYPES, LOAN_TYPES
    for kind in set(REDUCTION_TYPES.values()):
        sources[("student-affairs", "FEE_REDUCTION", kind)] = (FeeReduction, {"ISSUED", "REJECTED", "WITHDRAWN"})
    for kind in set(LOAN_TYPES.values()):
        sources[("student-affairs", "STUDENT_LOAN", kind)] = (StudentLoan, {"CONFIRMED", "WITHDRAWN"})
    spec = sources.get((row.source_module, row.source_biz_type, row.todo_type))
    if not spec:
        raise AppException("DATA_CONFLICT", "此类待办尚不能自动核验完成，请回所属业务模块办理", http_status=409)
    model, completed = spec
    source = db.scalar(select(model).where(
        model.id == row.source_biz_id, model.tenant_id == _tid(),
        model.is_deleted.is_(False)).with_for_update().execution_options(populate_existing=True))
    if source is None or source.status not in completed:
        raise AppException("DATA_CONFLICT", "来源业务未完成、已重新办理或无法核验，不能关闭提醒", http_status=409)
    return source


def close_todo_with_evidence(db, *, todo_id: int, evidence: str, expected_version=None, actor=None) -> UnifiedTodo:
    """锁定原业务状态后修复失效提醒；不改变业务结果，审计与待办同事务。"""
    from app.core.optimistic_lock import require_expected_version
    from app.core.timeutil import utc_now_naive
    from app.services.db_service import audit_insert_in_session

    text = (evidence or "").strip()
    if len(text) < 2:
        raise AppException("VALIDATION_ERROR", "完成证据不能为空", http_status=422)
    require_expected_version(expected_version)
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.id == int(todo_id), UnifiedTodo.tenant_id == _tid(),
        UnifiedTodo.is_deleted.is_(False))).first()
    if not row:
        raise AppException("DATA_NOT_FOUND", "待办不存在", http_status=404)
    # 先锁来源后锁待办，与业务完成回写顺序一致，避免互相等待。
    source_key = (row.source_module, row.source_biz_type, row.source_biz_id, row.todo_type)
    source = _completed_source(db, row)
    row = db.scalar(select(UnifiedTodo).where(
        UnifiedTodo.id == int(todo_id), UnifiedTodo.tenant_id == _tid(),
        UnifiedTodo.is_deleted.is_(False)).with_for_update().execution_options(populate_existing=True))
    if not row or row.status != "PENDING" or int(row.version or 0) != int(expected_version):
        raise AppException("DATA_CONFLICT", "待办已变化，请刷新后核对", http_status=409)
    if (row.source_module, row.source_biz_type, row.source_biz_id, row.todo_type) != source_key:
        raise AppException("DATA_CONFLICT", "待办来源已变化，请刷新后核对", http_status=409)
    row.remark = f"[完成证据] {text}" if not row.remark else f"{row.remark}\n[完成证据] {text}"
    row.status = "CANCELLED" if row.source_module == "student-affairs" and source.status == "WITHDRAWN" else "DONE"
    row.completed_at = utc_now_naive() if row.status == "DONE" else None
    row.version = int(row.version or 0) + 1
    if isinstance(actor, dict):
        actor_id = actor.get("userId") or actor.get("id")
    else:
        actor_id = getattr(actor, "userId", None) or getattr(actor, "id", None)
    audit_insert_in_session(db, "TODO_CLOSED_WITH_EVIDENCE", f"unified-todo:{todo_id}",
                            {"todoType": row.todo_type, "sourceModule": row.source_module,
                             "sourceBizId": row.source_biz_id, "sourceStatus": source.status,
                             "evidence": text, "actorId": actor_id}, "SUCCESS", tenant_id=_tid(), resource_id=str(todo_id))
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
        "remark": r.remark, "version": int(r.version or 0),
    } for r in rows]
    return items, total
