"""统一时间处理：API 边界带时区，库内存 UTC naive（兼容现有 DateTime 列）。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.core.config import settings

UTC = timezone.utc


def tenant_tz():
    """租户默认时区（当前全局配置；后续可按租户 IANA 覆盖）。"""
    name = getattr(settings, "TENANT_TIMEZONE", None) or "Asia/Shanghai"
    try:
        return ZoneInfo(str(name))
    except Exception:  # noqa: BLE001
        offset = int(getattr(settings, "TIMEZONE_OFFSET_HOURS", 8) or 8)
        return timezone(timedelta(hours=offset))


def utc_now() -> datetime:
    """返回 UTC aware datetime。"""
    return datetime.now(UTC)


def utc_now_naive() -> datetime:
    """写入现有无时区 DateTime 列的 UTC naive。"""
    return utc_now().replace(tzinfo=None)


def to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # 无时区输入按租户本地时区解释，再转 UTC（禁止当 UTC）
        dt = dt.replace(tzinfo=tenant_tz())
    return dt.astimezone(UTC).replace(tzinfo=None)


def local_day_bounds_utc(value: date | datetime | str) -> tuple[datetime, datetime]:
    """把“租户本地自然日”转换成数据库可比较的 UTC-naive ``[start, end)``。

    API 的 ``YYYY-MM-DD``、工作台“今日新增/今日已办”都属于人的本地日历语义，
    不能直接拿 UTC 00:00 切日。使用 IANA ``tenant_tz()`` 构造本地零点后再转 UTC，
    也兼容将来存在夏令时的租户时区，不把“一天”硬编码成 UTC 固定边界。
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            day = value.date()
        else:
            day = value.astimezone(tenant_tz()).date()
    elif isinstance(value, date):
        day = value
    else:
        day = datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    tz = tenant_tz()
    local_start = datetime.combine(day, time.min, tzinfo=tz)
    local_end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return (
        local_start.astimezone(UTC).replace(tzinfo=None),
        local_end.astimezone(UTC).replace(tzinfo=None),
    )


def local_today_bounds_utc(now: datetime | None = None) -> tuple[datetime, datetime]:
    """当前租户“今天”的 UTC-naive ``[start, end)``，供数据库统计统一复用。"""
    current = now or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    local_day = current.astimezone(tenant_tz()).date()
    return local_day_bounds_utc(local_day)


def parse_api_datetime(raw) -> Optional[datetime]:
    """解析 API 时间，返回 UTC naive（入库）。优先 RFC3339 / ISO8601。"""
    if not raw:
        return None
    if isinstance(raw, datetime):
        return to_utc_naive(raw)
    s = str(raw).strip()
    if not s:
        return None
    # 常见前端：2026-07-24T10:00:00+08:00 / ...Z / 空格分隔
    normalized = s.replace(" ", "T")
    try:
        if normalized.endswith("Z"):
            dt = datetime.fromisoformat(normalized[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(normalized)
        return to_utc_naive(dt)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            local = datetime.strptime(normalized[:19] if len(normalized) >= 19 else normalized, fmt)
            return to_utc_naive(local.replace(tzinfo=tenant_tz()))
        except ValueError:
            continue
    return None


def iso_utc(v) -> str | None:
    """API 输出：UTC 带 Z。"""
    if v is None:
        return None
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        else:
            v = v.astimezone(UTC)
        return v.isoformat(timespec="seconds").replace("+00:00", "Z")
    return str(v)


def local_now() -> datetime:
    """租户本地当前时间（aware）。"""
    return utc_now().astimezone(tenant_tz())
