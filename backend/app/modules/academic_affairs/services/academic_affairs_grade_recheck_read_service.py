"""D8-U3 成绩复查台账只读 SQL 分页。

只优化 GET /grade-rechecks：继续复用 canonical 成绩复查服务的 TENANT_ALL 范围门禁与 DTO，
把全校复查申请全量 materialize 后 Python 切页改为 MySQL COUNT + LIMIT/OFFSET。
复审、成绩更正、排他锁、有效成绩策略快照、审计和通知写链均不在本模块实现。
"""
from __future__ import annotations

from sqlalchemy import func, select

from . import academic_affairs_grade_recheck_service as _base


def list_all(user, status=None, page=1, page_size=50):
    """返回教务处可见的成绩复查台账页；只 materialize 当前页。"""
    from app.models import AaGradeRecheck

    page_no = max(1, int(page))
    size = int(page_size)
    with _base.session() as db:
        _base._require_school(user, db)
        conditions = [
            AaGradeRecheck.tenant_id == _base._tid(),
            AaGradeRecheck.is_deleted.is_(False),
        ]
        if status:
            conditions.append(AaGradeRecheck.status == status)

        total = int(
            db.scalar(select(func.count(AaGradeRecheck.id)).where(*conditions)) or 0
        )
        if size <= 0:
            return [], total
        rows = db.scalars(
            select(AaGradeRecheck)
            .where(*conditions)
            .order_by(AaGradeRecheck.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        return [_base._dto(row) for row in rows], total
