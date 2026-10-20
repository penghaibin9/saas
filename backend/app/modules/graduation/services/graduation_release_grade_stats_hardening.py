"""Graduation scoped overview and college statistics hardening."""
from __future__ import annotations

from sqlalchemy import func, select
from app.models import GraduationStudent
from app.services.db_service import _tid, session
from app.modules.graduation.services.graduation_release_hardening_common import _student_scope_select


def _install_grade_stats_hardening() -> None:
    from app.modules.graduation.services import graduation_stats_service as stats

    stats.STAGE_LABEL["COMPLETED"] = "已完成"

    def overview_stats(batch_id=None):
        with session() as db:
            scope_q = _student_scope_select(db, _tid(), batch_id=batch_id)
            base = [GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE", GraduationStudent.id.in_(scope_q)]
            total = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(*base)) or 0)
            stage_counts = {str(k): int(v or 0) for k, v in db.execute(select(GraduationStudent.stage, func.count()).where(*base).group_by(GraduationStudent.stage)).all()}
            risk_counts = {str(k): int(v or 0) for k, v in db.execute(select(GraduationStudent.risk_level, func.count()).where(*base).group_by(GraduationStudent.risk_level)).all()}
        full = stats.has_full_scope()
        return {"batchId": str(batch_id) if batch_id else None, "studentTotal": total,
                "byStage": [{"stage": key, "label": stats.STAGE_LABEL[key], "count": stage_counts.get(key, 0)} for key in stats.STAGE_LABEL],
                "byRisk": [{"level": lv, "count": risk_counts.get(lv, 0)} for lv in ("NONE", "LOW", "MEDIUM", "HIGH")],
                "batch": stats.graduation_batch_service.batch_stats() if full else {"restricted": True},
                "mentor": stats.graduation_mentor_service.mentor_stats(batch_id=batch_id) if full else {"restricted": True},
                "guidance": stats.graduation_guidance_service.guidance_stats(batch_id=batch_id),
                "midterm": stats.graduation_midterm_service.midterm_stats(batch_id=batch_id),
                "review": stats.graduation_review_service.review_stats(batch_id=batch_id),
                "grade": stats.graduation_grade_service.grade_stats(batch_id=batch_id),
                "risk": stats.graduation_risk_service.risk_stats(batch_id=batch_id),
                "archive": stats.graduation_archive_service.archive_stats(batch_id=batch_id)}

    def college_comparison(batch_id=None):
        with session() as db:
            scope_q = _student_scope_select(db, _tid(), batch_id=batch_id)
            q = select(func.coalesce(func.nullif(GraduationStudent.college_id, ""), "未分类").label("college"), func.count().label("total"), func.sum(GraduationStudent.stage == "ARCHIVED").label("archived"), func.sum(GraduationStudent.stage == "COMPLETED").label("completed"), func.sum(GraduationStudent.risk_level == "HIGH").label("high_risk")).where(GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE", GraduationStudent.id.in_(scope_q)).group_by(func.coalesce(func.nullif(GraduationStudent.college_id, ""), "未分类")).order_by(func.count().desc())
            return [{"name": college, "collegeId": None if college == "未分类" else college, "total": int(total or 0), "archived": int(archived or 0), "completed": int(completed or 0), "highRisk": int(high or 0)} for college, total, archived, completed, high in db.execute(q).all()]
    stats.overview_stats = overview_stats
    stats.college_comparison = college_comparison
