"""成绩服务兼容入口。

当前 ``AcademicGrade`` 尚未持久化 course_id，因此先完成两件必须的纠偏：
1. 有稳定 course_id/course_code 时优先使用，绝不按课程名合并；
2. 历史行仅以“规范课程名 + 课程性质 + 学分”作为显式兼容键，并按正式来源、考试尝试和
   最新记录选择有效行，不再用最高分硬编码学校的补考/重修制度。

V2后续迁移应把 ``AaGradeTask.course_id`` 投影到成绩读模型，并冻结学校有效成绩策略。
"""
from __future__ import annotations

import logging
import unicodedata
from decimal import Decimal, InvalidOperation

from . import academic_affairs_grade_service as _legacy

_LOG = logging.getLogger(__name__)
_SOURCE_PRIORITY = {
    "RECHECK": 70,
    "CHANGE": 60,
    "RECOGNIZED": 55,
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
        1 if pass_status in {"PASSED", "FAILED"} else 0,
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
