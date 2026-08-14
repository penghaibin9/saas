"""V9.2 U4/M12 · 指导频次统计只读模型。

当前批次、当前数据范围内学生的指导次数统一由 SQL 聚合；不足学生必须通过
LEFT JOIN + GROUP BY + HAVING 得出，0 次指导学生仍保留。dataScope 复用 U2/M9
已封板的 SQL selector，不先 materialize 全批学生。正式写链仍由
``graduation_guidance_service`` 负责。

生产规模约束：stats 只返回不足学生的有界 preview；``insufficientCount`` 始终是
SQL 精确总数，``insufficientHasMore`` 明确告知 preview 是否被截断，避免 2 万人
批次把整份不足名单塞进单个统计响应。
"""
from __future__ import annotations

from sqlalchemy import and_, func, select

from app.models import GraduationGuidance, GraduationStudent
from app.modules.graduation.services.graduation_proposal_read_service import student_scope_select
from app.services.db_service import _tid, session

INSUFFICIENT_PREVIEW_LIMIT = 200


def _grouped_counts(scope_select):
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
            GraduationStudent.id.in_(scope_select),
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
        scope_select = student_scope_select(db, _tid(), batch_id=batch_id)
        grouped = _grouped_counts(scope_select)
        counts = grouped.subquery()
        student_count, avg_count = db.execute(
            select(
                func.count(counts.c.student_id),
                func.coalesce(func.avg(counts.c.guidance_count), 0),
            )
        ).one()

        # M12 hard contract: insufficient truth comes from SQL HAVING, never from
        # materializing every student's count and filtering in Python. The count is
        # exact; only the response preview is bounded for school-scale payload safety.
        count_expr = func.count(GraduationGuidance.id)
        insufficient_query = _grouped_counts(scope_select).having(count_expr < threshold)
        insufficient_count = int(db.scalar(
            select(func.count()).select_from(insufficient_query.subquery())
        ) or 0)
        insufficient_rows = db.execute(
            insufficient_query
            .order_by(GraduationStudent.id)
            .limit(INSUFFICIENT_PREVIEW_LIMIT)
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
            "insufficientCount": insufficient_count,
            "insufficientStudents": insufficient,
            "insufficientPreviewLimit": INSUFFICIENT_PREVIEW_LIMIT,
            "insufficientHasMore": insufficient_count > len(insufficient),
            "batchId": str(batch_id) if batch_id else None,
        }
