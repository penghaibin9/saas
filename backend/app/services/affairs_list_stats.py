"""学工分页列表的全量状态聚合工具。"""
from __future__ import annotations

from sqlalchemy import func, select


def status_counts_by_column(
    db, model, status_col, base_conds, join_student=None, allowed_class_ids=None
) -> dict:
    """按状态聚合完整过滤集，永不受当前分页窗口影响。"""
    stmt = select(status_col, func.count()).select_from(model)
    conds = list(base_conds or [])
    if join_student is not None:
        stmt = stmt.join(join_student, join_student.id == model.student_id)
        if allowed_class_ids is not None:
            conds.append(join_student.class_id.in_(allowed_class_ids or {-1}))
    rows = db.execute(stmt.where(*conds).group_by(status_col)).all()
    counts = {str(status): int(count or 0) for status, count in rows if status is not None}
    counts["ALL"] = sum(counts.values())
    return counts
