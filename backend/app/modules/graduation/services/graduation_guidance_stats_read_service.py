"""V9.2 U4/M12 · 指导频次统计只读模型。

当前批次、当前数据范围内学生的指导次数统一由 SQL 聚合；不足学生必须通过
LEFT JOIN + GROUP BY + HAVING 得出，0 次指导学生仍保留。正式写链仍由
``graduation_guidance_service`` 负责。
"""
from __future__ import annotations

from sqlalchemy import and_, func, select

from app.models import GraduationGuidance, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services.db_service import _tid, session


def _grouped_counts(scope_ids):
    count_col = func.count(GraduationGuidance.id).label("guidance_count")
    return (
        select(
            GraduationStudent.id.label("student_id"),
            GraduationStudent.name.label("student_name"),
            GraduationStudent.advisor_name.label("advisor_name"),
            count_col,
        )
        .outerjoin(
            GraduationGuidance,
            and_(
                GraduationGuidance.gd_student_id == GraduationStudent.id,
                GraduationGuidance.tenant_id == _tid(),
                GraduationGuidance.is_deleted.is_(False),
            ),
        )
        .where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.id.in_(scope_ids),
            GraduationStudent.stage.notin_(("TOPIC_SELECTING", "TASKBOOK_CONFIRM")),
        )
        .group_by(
            GraduationStudent.id,
            GraduationStudent.name,
            GraduationStudent.advisor_name,
        )
    )


def guidance_stats(threshold: int = 3, batch_id=None) -> dict:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        if not scope_ids:
            return {
                "threshold": threshold,
                "studentCount": 0,
                "avgCount": 0,
                "insufficientCount": 0,
                "insufficientStudents": [],
                "batchId": str(batch_id) if batch_id else None,
            }

        grouped = _grouped_counts(scope_ids)
        counts = grouped.subquery()
        student_count, avg_count = db.execute(
            select(
                func.count(counts.c.student_id),
                func.coalesce(func.avg(counts.c.guidance_count), 0),
            )
        ).one()

        # M12 hard contract: the insufficient ledger is selected by SQL HAVING,
        # not by materializing every student's count and filtering in Python.
        count_expr = func.count(GraduationGuidance.id)
        insufficient_rows = db.execute(
            _grouped_counts(scope_ids)
            .having(count_expr < threshold)
            .order_by(GraduationStudent.id)
        ).all()
        insufficient = [
            {
                "gdStudentId": str(student_id),
                "studentName": student_name,
                "advisorName": advisor_name or "",
                "count": int(count or 0),
            }
            for student_id, student_name, advisor_name, count in insufficient_rows
        ]

        return {
            "threshold": threshold,
            "studentCount": int(student_count or 0),
            "avgCount": round(float(avg_count or 0), 1),
            "insufficientCount": len(insufficient),
            "insufficientStudents": insufficient,
            "batchId": str(batch_id) if batch_id else None,
        }
