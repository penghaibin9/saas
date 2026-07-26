"""成绩服务兼容入口。

当前 ``AcademicGrade`` 尚未持久化 course_id，因此先完成两件必须的纠偏：
1. 有稳定 course_id/course_code 时优先使用，绝不按课程名合并；
2. 历史行仅以“规范课程名 + 课程性质 + 学分”作为显式兼容键，并按正式来源、考试尝试和
   最新记录选择有效行，不再用最高分硬编码学校的补考/重修制度。

本facade同时替换原模块内部的有效成绩与汇总函数，保证成绩发布、成绩单、预警和毕业审核
不会出现两套口径。V2后续迁移应把 ``AaGradeTask.course_id`` 投影到成绩读模型，并冻结学校
有效成绩策略快照。
"""
from __future__ import annotations

import logging
import unicodedata
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from . import academic_affairs_grade_service as _legacy

_LOG = logging.getLogger(__name__)
_SOURCE_PRIORITY = {
    "RECHECK": 70,
    "CHANGE": 60,
    "RECOGNIZED": 55,
    "RECOGNITION": 55,
    "PUBLISH": 50,
    "MANUAL": 40,
    "LEGACY": 10,
}
_EXAM_PRIORITY = {
    "CLEARANCE": 50,
    "MAKEUP": 40,
    "RETAKE": 30,
    "FINAL": 20,
    "NORMAL": 10,
}


def __getattr__(name):
    return getattr(_legacy, name)


def _normalize_name(value) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return "".join(text.split())


def _credit_key(value) -> str:
    try:
        return str(Decimal(str(value or 0)).quantize(Decimal("0.1")))
    except (InvalidOperation, ValueError):
        return str(value or "")


def grade_identity_key(row):
    """返回稳定课程身份；历史无ID行明确标记LEGACY，不与不同性质/学分课程混并。"""
    student_id = getattr(row, "acad_student_id", None)
    course_id = getattr(row, "course_id", None)
    if course_id not in (None, ""):
        return (student_id, "COURSE_ID", str(course_id))

    course_code = str(getattr(row, "course_code", None) or "").strip().upper()
    if course_code:
        return (student_id, "COURSE_CODE", course_code)

    return (
        student_id,
        "LEGACY",
        _normalize_name(getattr(row, "course_name", None)),
        str(getattr(row, "nature", None) or "").upper(),
        _credit_key(getattr(row, "credit_value", None)),
    )


def _attempt_rank(row):
    """正式来源 > 考试尝试类型 > 最新记录；分数不参与优先级。"""
    source = str(getattr(row, "source", None) or "LEGACY").upper()
    exam_type = str(getattr(row, "exam_type", None) or "NORMAL").upper()
    record_status = str(getattr(row, "record_status", None) or "ACTIVE").upper()
    pass_status = str(getattr(row, "pass_status", None) or "PENDING").upper()
    row_id = int(getattr(row, "id", None) or 0)
    return (
        1 if record_status == "ACTIVE" else 0,
        _SOURCE_PRIORITY.get(source, 20),
        _EXAM_PRIORITY.get(exam_type, 15),
        1 if pass_status in {"PASSED", "FAILED", "FAIL"} else 0,
        row_id,
    )


def effective_grade_rows(rows):
    """按稳定课程身份和正式尝试顺序确定有效成绩，禁止最高分覆盖。"""
    selected = {}
    legacy_count = 0
    for row in rows or []:
        key = grade_identity_key(row)
        if len(key) > 1 and key[1] == "LEGACY":
            legacy_count += 1
        current = selected.get(key)
        if current is None or _attempt_rank(row) > _attempt_rank(current):
            selected[key] = row

    if legacy_count:
        _LOG.warning(
            "effective grade used legacy identity for %s rows; migrate AcademicGrade.course_id",
            legacy_count,
        )
    return list(selected.values())


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


# 原模块函数内部通过自身globals查找这两个名字；显式替换后，publish_grades/transcript等旧函数
# 也会消费同一规则，而不是只有facade外部调用才生效。
_legacy.effective_grade_rows = effective_grade_rows
_legacy._refresh_aggregates = refresh_academic_aggregates
