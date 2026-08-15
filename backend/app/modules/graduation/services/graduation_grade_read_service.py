from __future__ import annotations

from sqlalchemy import func, or_, select

from app.core.exceptions import AppException
from app.models import GraduationGrade, GraduationStudent
from app.modules.graduation.services.graduation_proposal_read_service import student_scope_select
from app.services.db_service import _tid, session

MISSING_TYPES = {"ANY", "ADVISOR", "REVIEWER", "DEFENSE", "TOTAL"}


def _missing_clause(missing_type):
    value = str(missing_type or "").strip().upper()
    if not value:
        return None
    if value not in MISSING_TYPES:
        raise AppException("VALIDATION_ERROR", "invalid missingType")
    mapping = {
        "ADVISOR": GraduationGrade.advisor_score.is_(None),
        "REVIEWER": GraduationGrade.reviewer_score.is_(None),
        "DEFENSE": GraduationGrade.defense_score.is_(None),
        "TOTAL": GraduationGrade.total_score.is_(None),
    }
    if value == "ANY":
        return or_(mapping["ADVISOR"], mapping["REVIEWER"], mapping["DEFENSE"], mapping["TOTAL"])
    return mapping[value]


def list_grades(page, page_size, keyword=None, status=None, batch_id=None, missing_type=None):
    from app.modules.graduation.services import graduation_grade_service as svc

    tenant_id = _tid()
    with session() as db:
        scope_select = student_scope_select(db, tenant_id, batch_id=batch_id)
        join_on = GraduationStudent.id == GraduationGrade.gd_student_id
        filters = [
            GraduationGrade.tenant_id == tenant_id,
            GraduationGrade.is_deleted.is_(False),
            GraduationStudent.tenant_id == tenant_id,
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.id.in_(scope_select),
        ]
        if batch_id:
            filters.append(GraduationStudent.batch_id == int(batch_id))
        if status:
            filters.append(GraduationGrade.status == status)
        value = str(keyword or "").strip()
        if value:
            filters.append(or_(GraduationStudent.name.contains(value), GraduationStudent.student_no.contains(value)))
        missing_clause = _missing_clause(missing_type)
        if missing_clause is not None:
            filters.append(missing_clause)
        total = int(db.scalar(
            select(func.count(func.distinct(GraduationGrade.id)))
            .select_from(GraduationGrade)
            .join(GraduationStudent, join_on)
            .where(*filters)
        ) or 0)
        rows = db.execute(
            select(GraduationGrade, GraduationStudent)
            .join(GraduationStudent, join_on)
            .where(*filters)
            .order_by(GraduationGrade.id.desc())
            .offset((max(1, int(page)) - 1) * int(page_size))
            .limit(int(page_size))
        ).all()
        return [svc._row(grade, student) for grade, student in rows], total
