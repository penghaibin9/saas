"""成绩服务兼容入口：所有成绩消费者统一使用P0-11有效成绩策略。"""
from __future__ import annotations

from sqlalchemy import select

from . import academic_affairs_grade_service as _legacy
from .academic_affairs_effective_grade_policy_service import (
    grade_identity_key,
    resolve_effective_grade,
)


def __getattr__(name):
    return getattr(_legacy, name)


def effective_grade_rows(rows):
    """兼容旧函数名；真实规则由统一策略服务提供。"""
    return resolve_effective_grade(rows)


def refresh_academic_aggregates(db, academic_student) -> None:
    """用统一有效成绩口径刷新均分、未通过、学分和GPA。"""
    from app.models import AcademicGrade

    all_rows = db.scalars(select(AcademicGrade).where(
        AcademicGrade.tenant_id == _legacy._tid(),
        AcademicGrade.acad_student_id == academic_student.id,
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    )).all()
    rows = effective_grade_rows(all_rows)
    scored = [row for row in rows if row.score is not None]

    academic_student.avg_score = (
        round(sum(float(row.score) for row in scored) / len(scored))
        if scored else 0
    )
    academic_student.failed_count = sum(
        1 for row in rows
        if str(row.pass_status or "").upper() in {"FAIL", "FAILED"}
    )
    academic_student.obtained_credits = sum(
        float(row.credit_value or 0)
        for row in rows
        if str(row.pass_status or "").upper() == "PASSED"
    )

    if not scored:
        academic_student.gpa = 0
        return
    total_credit = sum(float(row.credit_value or 0) for row in scored)
    if total_credit > 0:
        academic_student.gpa = round(
            sum(
                _legacy._course_point(row.score) * float(row.credit_value or 0)
                for row in scored
            ) / total_credit,
            2,
        )
    else:
        academic_student.gpa = round(
            sum(_legacy._course_point(row.score) for row in scored) / len(scored),
            2,
        )


# 原模块内部、成绩单、预警、毕业审核和其它兼容消费者统一命中同一策略。
_legacy.grade_identity_key = grade_identity_key
_legacy.effective_grade_rows = effective_grade_rows
_legacy._refresh_aggregates = refresh_academic_aggregates
