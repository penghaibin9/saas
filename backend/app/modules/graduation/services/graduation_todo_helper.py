"""毕设域 UnifiedTodo 写入（工作台 P5 / T7 GD_MENTOR）。

幂等键对齐 uk_todo_dedup：tenant + source_module + source_biz_id + todo_type + assignee_id。
受理人优先 mentor.teacher_no → User.login_name；无法解析则跳过（不写 assignee=0 池待办）。
"""
from __future__ import annotations

from sqlalchemy import select

from app.services.db_service import _tid

SRC_MODULE = "graduation"

TODO_PROPOSAL = "GD_PROPOSAL_REVIEW"
TODO_FINAL = "GD_FINAL_REVIEW"
TODO_TOPIC_CHANGE = "GD_TOPIC_CHANGE_REVIEW"


def resolve_mentor_assignee_id(db, stu) -> int:
    """导师 → 系统用户 ID；无法唯一证明时返回 0（调用方跳过写待办）。"""
    from app.models import User
    from app.modules.graduation.services.graduation_scope_service import _mentor_teacher_no

    teacher_no = _mentor_teacher_no(db, stu)
    if teacher_no:
        row = db.scalars(select(User).where(
            User.tenant_id == _tid(), User.login_name == teacher_no,
            User.is_deleted.is_(False), User.status == "ACTIVE")).first()
        if row:
            return int(row.id)
    name = (getattr(stu, "advisor_name", None) or "").strip()
    if not name:
        return 0
    rows = db.scalars(select(User).where(
        User.tenant_id == _tid(), User.real_name == name,
        User.user_type.in_(("TEACHER", "STAFF", "SCHOOL_ADMIN", "ADMIN")),
        User.is_deleted.is_(False), User.status == "ACTIVE")).all()
    return int(rows[0].id) if len(rows) == 1 else 0


def todo_upsert(db, *, biz_type: str, biz_id, todo_type: str, assignee_id: int,
                student_id, title: str) -> bool:
    """创建或复活 PENDING 待办；assignee_id<=0 时跳过。返回是否写入。"""
    from app.models import UnifiedTodo
    aid = int(assignee_id or 0)
    if aid <= 0 or not biz_id:
        return False
    bid = int(biz_id)
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == SRC_MODULE,
        UnifiedTodo.source_biz_id == bid, UnifiedTodo.todo_type == todo_type,
        UnifiedTodo.assignee_id == aid, UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title = title
        row.status = "PENDING"
        row.student_id = student_id
        row.source_biz_type = biz_type
        row.version = int(row.version or 0) + 1
        return True
    db.add(UnifiedTodo(
        tenant_id=_tid(), source_module=SRC_MODULE, source_biz_type=biz_type,
        source_biz_id=bid, todo_type=todo_type, assignee_id=aid,
        student_id=student_id, title=title, status="PENDING"))
    return True


def todo_done(db, *, biz_id, todo_type: str) -> int:
    """将该业务单据下同类型待办全部标 DONE；返回更新条数。"""
    from app.models import UnifiedTodo
    if not biz_id:
        return 0
    n = 0
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == SRC_MODULE,
            UnifiedTodo.source_biz_id == int(biz_id), UnifiedTodo.todo_type == todo_type,
            UnifiedTodo.is_deleted.is_(False), UnifiedTodo.status == "PENDING")).all():
        r.status = "DONE"
        r.version = int(r.version or 0) + 1
        n += 1
    return n


def push_proposal_todo(db, proposal, stu) -> bool:
    aid = resolve_mentor_assignee_id(db, stu)
    name = (getattr(stu, "name", None) or getattr(stu, "real_name", None) or "学生")
    return todo_upsert(
        db, biz_type="GD_PROPOSAL", biz_id=proposal.id, todo_type=TODO_PROPOSAL,
        assignee_id=aid, student_id=getattr(stu, "student_id", None),
        title=f"开题待批阅：{name}")


def push_final_todo(db, final_row, stu) -> bool:
    aid = resolve_mentor_assignee_id(db, stu)
    name = (getattr(stu, "name", None) or getattr(stu, "real_name", None) or "学生")
    ftype = getattr(final_row, "final_type", "") or "成果"
    return todo_upsert(
        db, biz_type="GD_FINAL", biz_id=final_row.id, todo_type=TODO_FINAL,
        assignee_id=aid, student_id=getattr(stu, "student_id", None),
        title=f"{ftype}待批阅：{name}")


def push_topic_change_todo(db, change_req, stu) -> bool:
    aid = resolve_mentor_assignee_id(db, stu)
    name = (getattr(stu, "name", None) or getattr(stu, "real_name", None) or "学生")
    return todo_upsert(
        db, biz_type="GD_TOPIC_CHANGE", biz_id=change_req.id, todo_type=TODO_TOPIC_CHANGE,
        assignee_id=aid, student_id=getattr(stu, "student_id", None),
        title=f"选题变更待审：{name}")
