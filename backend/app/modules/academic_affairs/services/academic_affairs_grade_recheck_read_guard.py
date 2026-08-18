"""C-W4 bounded read guard for the mature grade-recheck ledger.

Grade recheck submit/review remains entirely owned by
``academic_affairs_grade_recheck_service``.  This guard replaces only the school
ledger read that historically loaded every row and sliced in Python.
"""
from __future__ import annotations

from sqlalchemy import func, select

from . import academic_affairs_grade_recheck_service as recheck

_MAX_PAGE_SIZE = 200


def list_all(user, status=None, page=1, page_size=50):
    from app.models import AaGradeRecheck

    page_no = max(1, int(page or 1))
    size = max(1, min(int(page_size or 50), _MAX_PAGE_SIZE))
    with recheck.session() as db:
        recheck._require_school(user, db)
        conditions = [
            AaGradeRecheck.tenant_id == recheck._tid(),
            AaGradeRecheck.is_deleted.is_(False),
        ]
        if status:
            conditions.append(AaGradeRecheck.status == str(status).upper())
        total = int(
            db.scalar(
                select(func.count()).select_from(AaGradeRecheck).where(*conditions)
            )
            or 0
        )
        rows = db.scalars(
            select(AaGradeRecheck)
            .where(*conditions)
            .order_by(AaGradeRecheck.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        return [recheck._dto(row) for row in rows], total


list_all._grade_recheck_sql_pagination = True


def install() -> None:
    if not hasattr(recheck, "_grade_recheck_read_original_list_all"):
        recheck._grade_recheck_read_original_list_all = recheck.list_all
    recheck.list_all = list_all
