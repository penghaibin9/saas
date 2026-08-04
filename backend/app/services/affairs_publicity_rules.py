"""Formal validation helpers for student-affairs publicity batches."""
from __future__ import annotations

import re

from app.core.exceptions import AppException


def publicity_days(value) -> int:
    try:
        days = int(value if value is not None else 5)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "公示天数必须为整数") from exc
    if days < 1 or days > 30:
        raise AppException("VALIDATION_ERROR", "正式公示天数应为1-30天")
    return days


def school_year(value) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{4}", text):
        raise AppException("VALIDATION_ERROR", "学年格式应为YYYY-YYYY")
    start, end = (int(part) for part in text.split("-"))
    if end != start + 1:
        raise AppException("VALIDATION_ERROR", "学年起止年份必须连续")
    return text


def validate_dates(parse_datetime, body) -> None:
    start = parse_datetime(getattr(body, "applyStart", None))
    end = parse_datetime(getattr(body, "applyEnd", None))
    if getattr(body, "applyStart", None) and not start:
        raise AppException("VALIDATION_ERROR", "申请开始时间格式不正确")
    if getattr(body, "applyEnd", None) and not end:
        raise AppException("VALIDATION_ERROR", "申请结束时间格式不正确")
    if start and end and end <= start:
        raise AppException("VALIDATION_ERROR", "申请结束时间必须晚于开始时间")
