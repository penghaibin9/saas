"""请假日期输入合同。

学生四端使用 date 控件，结束日期语义为“包含当天”。因此：
- 纯日期开始值归一到 00:00:00；
- 纯日期结束值归一到 23:59:59；
- 同日请假有效并计算为约1天；
- 非法日期、倒序、空值在进入数据库前统一返回 VALIDATION_ERROR。
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException

_DATE_FMT = "%Y-%m-%d"
_DATE_TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M")
_INSTALLED = False


def _date_only(value) -> bool:
    if not isinstance(value, str):
        return False
    raw = value.strip()
    if len(raw) != 10:
        return False
    try:
        datetime.strptime(raw, _DATE_FMT)
        return True
    except ValueError:
        return False


def _parse(value, *, end_of_day: bool, fallback=None):
    if value is None or value == "":
        return fallback
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if _date_only(raw):
        dt = datetime.strptime(raw, _DATE_FMT)
        return dt.replace(hour=23, minute=59, second=59) if end_of_day else dt
    for fmt in _DATE_TIME_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise AppException("VALIDATION_ERROR", "请假日期时间格式不正确")


def normalize_range(start_value, end_value, *, fallback_start=None, fallback_end=None):
    start = _parse(start_value, end_of_day=False, fallback=fallback_start)
    end = _parse(end_value, end_of_day=True, fallback=fallback_end)
    if not start or not end:
        raise AppException("VALIDATION_ERROR", "请填写请假开始和结束日期")
    if end <= start:
        raise AppException("VALIDATION_ERROR", "结束日期时间必须晚于开始日期时间")
    return start, end


def normalize_reason(value, *, minimum: int = 5, maximum: int = 300) -> str:
    reason = str(value or "").strip()
    if len(reason) < minimum or len(reason) > maximum:
        raise AppException("VALIDATION_ERROR", f"请假事由需{minimum}-{maximum}字")
    return reason


def install() -> None:
    """包装首次申请，确保所有PC/小程序/门户入口进入同一日期合同。"""
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_leave_service as service

    original = service.apply_leave
    if getattr(original, "_inclusive_leave_date_contract", False):
        _INSTALLED = True
        return

    def wrapped(body, user, *, skip_scope_check: bool = False):
        start, end = normalize_range(getattr(body, "startTime", None), getattr(body, "endTime", None))
        reason = normalize_reason(getattr(body, "reason", None))
        leave_type = str(getattr(body, "leaveType", None) or "PERSONAL").strip().upper()
        if leave_type not in service.L_TYPE:
            raise AppException("VALIDATION_ERROR", "请假类型非法")
        # Pydantic model 与测试用 SimpleNamespace 均允许属性赋值；统一传入明确时间字符串。
        body.startTime = start.strftime("%Y-%m-%d %H:%M:%S")
        body.endTime = end.strftime("%Y-%m-%d %H:%M:%S")
        body.reason = reason
        body.leaveType = leave_type
        return original(body, user, skip_scope_check=skip_scope_check)

    wrapped._inclusive_leave_date_contract = True
    wrapped._inclusive_leave_date_original = original
    service.apply_leave = wrapped
    _INSTALLED = True
