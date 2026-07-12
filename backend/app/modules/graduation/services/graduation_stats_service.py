"""毕业设计中心 · 毕设统计（只读聚合，跨模块口径，不新增业务表）。

聚合学生进度、导师工作量、题目/答辩/成绩/风险/归档等统计，供总看板与学院/专业对比使用。
隔离说明：只读聚合已有服务的统计函数，不重复实现业务逻辑。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx  # noqa: F401  (预留：后续数据范围过滤)
from app.models import GraduationStudent
from app.modules.graduation.services import (graduation_archive_service, graduation_batch_service, graduation_grade_service,
                          graduation_guidance_service, graduation_mentor_service, graduation_midterm_service,
                          graduation_review_service, graduation_risk_service)
from app.services.db_service import _tid, session

STAGE_LABEL = {"TOPIC_SELECTING": "选题中", "TASKBOOK_CONFIRM": "任务书确认", "GUIDING": "指导中",
              "MIDTERM": "中期检查", "FINAL_CHECK": "成果检查", "DEFENSE": "答辩中", "ARCHIVED": "已归档"}


def overview_stats() -> dict:
    with session() as db:
        base = [GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
                GraduationStudent.record_status == "ACTIVE"]
        total = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(*base)) or 0)
        by_stage = [{"stage": s, "label": STAGE_LABEL[s],
                    "count": int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
                        *base, GraduationStudent.stage == s)) or 0)} for s in STAGE_LABEL]
        by_risk = [{"level": lv, "count": int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            *base, GraduationStudent.risk_level == lv)) or 0)} for lv in ("NONE", "LOW", "MEDIUM", "HIGH")]
    return {
        "studentTotal": total,
        "byStage": by_stage,
        "byRisk": by_risk,
        "batch": graduation_batch_service.batch_stats(),
        "mentor": graduation_mentor_service.mentor_stats(),
        "guidance": graduation_guidance_service.guidance_stats(),
        "midterm": graduation_midterm_service.midterm_stats(),
        "review": graduation_review_service.review_stats(),
        "grade": graduation_grade_service.grade_stats(),
        "risk": graduation_risk_service.risk_stats(),
        "archive": graduation_archive_service.archive_stats(),
    }


def college_comparison() -> list[dict]:
    """按学院对比（现按 college_id 字段聚合；无学院信息的学生归入"未分类"）。"""
    with session() as db:
        rows = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE")).all()
        buckets: dict[str, dict] = {}
        for s in rows:
            key = s.class_name.split("-")[0] if s.class_name and "-" in s.class_name else "未分类"
            b = buckets.setdefault(key, {"name": key, "total": 0, "archived": 0, "highRisk": 0})
            b["total"] += 1
            if s.stage == "ARCHIVED":
                b["archived"] += 1
            if s.risk_level == "HIGH":
                b["highRisk"] += 1
        return sorted(buckets.values(), key=lambda x: -x["total"])
