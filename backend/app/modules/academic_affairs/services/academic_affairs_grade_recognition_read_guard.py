"""C-W4 bounded read guard for grade-recognition operations.

Recognition submit/review remains owned by the mature recognition service.  This
adapter replaces only the school-wide operations ledger that historically loaded all
recognition rows and sliced in Python.
"""
from __future__ import annotations

from sqlalchemy import func, select

from . import academic_affairs_recognition_service as recognition

_MAX_PAGE_SIZE = 200


def list_all(user, status=None, page=1, page_size=50):
    from app.models import AaGradeRecognition

    page_no = max(1, int(page or 1))
    size = max(1, min(int(page_size or 50), _MAX_PAGE_SIZE))
    with recognition.session() as db:
        recognition._require_school(user, db)
        conditions = [
            AaGradeRecognition.tenant_id == recognition._tid(),
            AaGradeRecognition.is_deleted.is_(False),
        ]
        if status:
            conditions.append(AaGradeRecognition.status == str(status).upper())
        total = int(
            db.scalar(
                select(func.count()).select_from(AaGradeRecognition).where(*conditions)
            )
            or 0
        )
        rows = db.scalars(
            select(AaGradeRecognition)
            .where(*conditions)
            .order_by(AaGradeRecognition.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        return [recognition._dto(row) for row in rows], total


list_all._grade_recognition_sql_pagination = True


def install() -> None:
    current = getattr(recognition, "list_all", None)
    if getattr(current, "_grade_recognition_sql_pagination", False):
        return
    if not hasattr(recognition, "_grade_recognition_read_original_list_all"):
        recognition._grade_recognition_read_original_list_all = current
    recognition.list_all = list_all
