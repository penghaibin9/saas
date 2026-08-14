"""D8-U2 成绩任务列表只读 SQL 分页。

只优化 GET /grade-tasks 的查询形态：继续复用成绩域既有角色、教师键与学院范围裁决原语，
把原先全量 materialize 后 Python 切页改为 MySQL COUNT + LIMIT/OFFSET。成绩录入、提交、
审核、发布、更正、归档等 canonical 写链不在本模块实现。
"""
from __future__ import annotations

from sqlalchemy import func, select

from . import academic_affairs_grade_core_service as _core
from . import academic_affairs_grade_service as _grade_public


def _scope_conditions(db, user, status=None):
    """按现有成绩任务 dataScope 生成唯一 SQL 条件，不引入新的角色语义。"""
    from app.models import AaGradeTask

    conditions = [
        AaGradeTask.tenant_id == _core._tid(),
        AaGradeTask.is_deleted.is_(False),
    ]
    if status:
        conditions.append(AaGradeTask.status == status)

    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role in _core._REVIEW_ROLES or (user or {}).get("userType") == "PLATFORM_SUPER_ADMIN":
        return conditions
    if role == "COLLEGE_ADMIN":
        from app.core.affairs_security import build_affairs_context

        context = build_affairs_context(user, db)
        allowed = context.allowed_class_ids(db)
        if allowed is not None:
            conditions.append(AaGradeTask.class_id.in_(list(allowed) or [0]))
        return conditions

    conditions.append(
        AaGradeTask.teacher_key.in_(list(_core._user_keys(user or {})) or ["__none__"])
    )
    return conditions


def list_tasks(user, status=None, page=1, page_size=20):
    """返回当前可见成绩任务页；数据行只 materialize 当前页。"""
    from app.models import AaGradeTask

    page_no = max(1, int(page))
    size = int(page_size)
    with _core.session() as db:
        conditions = _scope_conditions(db, user, status)
        total = int(
            db.scalar(
                select(func.count(AaGradeTask.id)).where(*conditions)
            )
            or 0
        )
        if size <= 0:
            return [], total
        rows = db.scalars(
            select(AaGradeTask)
            .where(*conditions)
            .order_by(AaGradeTask.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        return [_grade_public._task_row(row) for row in rows], total
