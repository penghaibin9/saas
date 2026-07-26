"""优秀成果候选查询：成绩优秀只是候选条件，不直接等于优秀成果认定。"""
from __future__ import annotations

from sqlalchemy import func, select

from app.models import GraduationFinal, GraduationGrade, GraduationStudent
from app.models.graduation_extension import GraduationExcellentOutcome
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services.db_service import _tid, session


def list_candidates(*, batch_id: int, page: int = 1, page_size: int = 20):
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        nominated = select(GraduationExcellentOutcome.gd_student_id).where(
            GraduationExcellentOutcome.tenant_id == _tid(),
            GraduationExcellentOutcome.batch_id == int(batch_id),
            GraduationExcellentOutcome.is_deleted.is_(False),
            GraduationExcellentOutcome.status.not_in(("REJECTED", "WITHDRAWN")),
        )
        final_ids = select(GraduationFinal.gd_student_id).where(
            GraduationFinal.tenant_id == _tid(),
            GraduationFinal.final_type == "定稿",
            GraduationFinal.status == "APPROVED",
            GraduationFinal.is_deleted.is_(False),
        )
        q = select(GraduationStudent, GraduationGrade).join(
            GraduationGrade, GraduationGrade.gd_student_id == GraduationStudent.id,
        ).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.batch_id == int(batch_id),
            GraduationStudent.id.in_(scope_ids or [-1]),
            GraduationStudent.id.in_(final_ids),
            GraduationStudent.id.not_in(nominated),
            GraduationStudent.is_deleted.is_(False),
            GraduationGrade.tenant_id == _tid(),
            GraduationGrade.status == "PUBLISHED",
            GraduationGrade.grade_level == "优秀",
            GraduationGrade.is_deleted.is_(False),
        )
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.execute(q.order_by(GraduationGrade.total_score.desc(), GraduationStudent.id)
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [{
            "gdStudentId": str(student.id), "studentName": student.name,
            "studentNo": student.student_no or "", "className": student.class_name or "",
            "topicTitle": student.topic_title or "", "advisorName": student.advisor_name or "",
            "totalScore": grade.total_score, "gradeLevel": grade.grade_level,
        } for student, grade in rows], total
