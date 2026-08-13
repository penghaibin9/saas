"""V9.2 U4/M12 · 指导频次统计只读模型。

一次 SQL 分组聚合当前批次、当前数据范围内学生的指导次数；不做逐学生 COUNT，
也不截断不足学生明细。正式写链仍由 graduation_guidance_service 负责。
"""
from __future__ import annotations

from sqlalchemy import and_, func, select

from app.models import GraduationGuidance, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services.db_service import _tid, session


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

        count_col = func.count(GraduationGuidance.id).label("guidance_count")
        rows = db.execute(
            select(
                GraduationStudent.id,
                GraduationStudent.name,
                GraduationStudent.advisor_name,
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
            .order_by(GraduationStudent.id)
        ).all()

        total_count = 0
        insufficient = []
        for student_id, student_name, advisor_name, count in rows:
            count = int(count or 0)
            total_count += count
            if count < threshold:
                insufficient.append({
                    "gdStudentId": str(student_id),
                    "studentName": student_name,
                    "advisorName": advisor_name or "",
                    "count": count,
                })

        return {
            "threshold": threshold,
            "studentCount": len(rows),
            "avgCount": round(total_count / len(rows), 1) if rows else 0,
            "insufficientCount": len(insufficient),
            "insufficientStudents": insufficient,
            "batchId": str(batch_id) if batch_id else None,
        }
