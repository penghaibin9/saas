"""优秀成果/延期答辩写动作统一输入门禁。

所有四端写入口先经过这里，避免超长文本写爆审计列、任意日期字符串和错误 evidence DTO。
"""
from __future__ import annotations

from datetime import date

from app.core.exceptions import AppException
from app.modules.graduation.services import graduation_extension_safety_service as safety
from app.modules.graduation.services import graduation_extension_service as base


def _text(value, label: str, *, minimum: int = 0, maximum: int = 1000) -> str:
    text = str(value or "").strip()
    if len(text) < minimum:
        raise AppException("VALIDATION_ERROR", f"{label}不少于 {minimum} 字")
    if len(text) > maximum:
        raise AppException("VALIDATION_ERROR", f"{label}不能超过 {maximum} 字")
    return text


def _evidence(value) -> list:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise AppException("VALIDATION_ERROR", "附件证据必须为列表")
    if len(value) > 20:
        raise AppException("VALIDATION_ERROR", "附件证据最多 20 项")
    return value


def _decision(action) -> str:
    value = str(action or "").strip().upper()
    if value not in {"APPROVE", "REJECT"}:
        raise AppException("VALIDATION_ERROR", "action 必须为 APPROVE/REJECT")
    return value


def _review_comment(action: str, comment) -> str:
    return _text(comment, "驳回理由" if action == "REJECT" else "审核意见",
                 minimum=5 if action == "REJECT" else 0)


def nominate_excellent(gd_student_id, reason, evidence=None) -> dict:
    return safety.nominate_excellent(
        gd_student_id,
        _text(reason, "优秀成果提名理由", minimum=10),
        _evidence(evidence),
    )


def apply_delay(user: dict, reason, evidence=None) -> dict:
    return safety.apply_delay(
        user,
        _text(reason, "延期答辩原因", minimum=10),
        _evidence(evidence),
    )


def advisor_review_delay(record_id, action, comment) -> dict:
    decision = _decision(action)
    return safety.advisor_review_delay(record_id, decision, _review_comment(decision, comment))


def major_review_excellent(record_id, action, comment) -> dict:
    decision = _decision(action)
    return base.major_review_excellent(record_id, decision, _review_comment(decision, comment))


def college_review_excellent(record_id, action, comment) -> dict:
    decision = _decision(action)
    return base.college_review_excellent(record_id, decision, _review_comment(decision, comment))


def major_review_delay(record_id, action, comment) -> dict:
    decision = _decision(action)
    return base.major_review_delay(record_id, decision, _review_comment(decision, comment))


def college_review_delay(record_id, action, comment) -> dict:
    decision = _decision(action)
    return base.college_review_delay(record_id, decision, _review_comment(decision, comment))


def schedule_delay(record_id, defense_group_id, planned_date) -> dict:
    planned = _text(planned_date, "延期答辩日期", minimum=10, maximum=10)
    try:
        date.fromisoformat(planned)
    except ValueError:
        raise AppException("VALIDATION_ERROR", "延期答辩日期必须为 YYYY-MM-DD") from None
    return safety.schedule_delay(record_id, defense_group_id, planned)
