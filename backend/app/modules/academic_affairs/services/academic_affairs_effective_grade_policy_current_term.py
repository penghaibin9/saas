"""无显式学期的正式成绩写入，收口到唯一当前学期后再冻结策略。"""
from __future__ import annotations

from sqlalchemy import event, select

from app.core.exceptions import AppException
from app.models.academic import AcademicGrade
from app.models import AaTerm
from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_compat as _compat


def _current_term_before_grade_insert(mapper, connection, target) -> None:
    if getattr(target, "tenant_id", None) and not str(getattr(target, "term", None) or "").strip():
        table = AaTerm.__table__
        rows = connection.execute(select(table).where(
            table.c.tenant_id == int(target.tenant_id),
            table.c.is_current.is_(True),
            table.c.is_deleted.is_(False),
        )).mappings().all()
        if len(rows) > 1:
            raise AppException(
                "DATA_CONFLICT",
                "学校存在多个当前学期，禁止为正式成绩猜测策略生效学期",
                details={"termIds": [str(row["id"]) for row in rows]},
                http_status=409,
            )
        if len(rows) == 1:
            target.term = _compat._term_code(rows[0])
    _compat._chronological_before_grade_insert(mapper, connection, target)


if event.contains(AcademicGrade, "before_insert", _compat._chronological_before_grade_insert):
    event.remove(AcademicGrade, "before_insert", _compat._chronological_before_grade_insert)
if not event.contains(AcademicGrade, "before_insert", _current_term_before_grade_insert):
    event.listen(AcademicGrade, "before_insert", _current_term_before_grade_insert)
