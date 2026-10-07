from __future__ import annotations
from datetime import date,datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo
from app.core.config import settings
UTC=timezone.utc
def tenant_tz():
    try:return ZoneInfo(settings.TENANT_TIMEZONE)
    except Exception:return timezone(timedelta(hours=settings.TIMEZONE_OFFSET_HOURS))
def utc_now():return datetime.now(UTC)
def utc_now_naive():return utc_now().replace(tzinfo=None)
def local_now():return utc_now().astimezone(tenant_tz())
def local_day_bounds_utc(value):
    day=value.date() if isinstance(value,datetime) else value if isinstance(value,date) else datetime.strptime(str(value),"%Y-%m-%d").date()
    start=datetime.combine(day,time.min,tzinfo=tenant_tz());end=datetime.combine(day+timedelta(days=1),time.min,tzinfo=tenant_tz())
    return start.astimezone(UTC).replace(tzinfo=None),end.astimezone(UTC).replace(tzinfo=None)
def iso_utc(value):
    if value is None:return None
    if isinstance(value,datetime):
        if value.tzinfo is None:value=value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00","Z")
    return str(value)
