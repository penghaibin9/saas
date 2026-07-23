"""消息发布治理：频控 + 静默时段。

- 频控：同租户同发布人滚动窗口内发布次数上限（默认 1 小时 20 次，可配置）。
- 静默：普通消息若落在静默窗则改 SCHEDULED 到窗结束后；紧急可绕过但写备注审计。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

# 租户级默认；后续可迁到租户配置表
DEFAULT_QUIET_START = "22:00"
DEFAULT_QUIET_END = "07:00"
DEFAULT_RATE_LIMIT = 20
DEFAULT_RATE_WINDOW_MINUTES = 60


def _parse_hhmm(s: str) -> tuple[int, int]:
    parts = str(s or "").strip().split(":")
    return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0


def is_in_quiet_hours(now: Optional[datetime] = None, *,
                      start: str = DEFAULT_QUIET_START,
                      end: str = DEFAULT_QUIET_END) -> bool:
    now = now or datetime.utcnow()
    # 用本地展示语义：UTC+8 校时
    local = now + timedelta(hours=8)
    sh, sm = _parse_hhmm(start)
    eh, em = _parse_hhmm(end)
    mins = local.hour * 60 + local.minute
    s = sh * 60 + sm
    e = eh * 60 + em
    if s == e:
        return False
    if s < e:
        return s <= mins < e
    # 跨夜：22:00–07:00
    return mins >= s or mins < e


def next_quiet_end(now: Optional[datetime] = None, *,
                   end: str = DEFAULT_QUIET_END) -> datetime:
    now = now or datetime.utcnow()
    local = now + timedelta(hours=8)
    eh, em = _parse_hhmm(end)
    candidate = local.replace(hour=eh, minute=em, second=0, microsecond=0)
    if candidate <= local:
        candidate = candidate + timedelta(days=1)
    # 回 UTC
    return candidate - timedelta(hours=8)


def assert_publish_rate(user_id: int, *, limit: int = DEFAULT_RATE_LIMIT,
                        window_minutes: int = DEFAULT_RATE_WINDOW_MINUTES) -> None:
    """滚动窗口发布受理次数（含 SCHEDULED/PUBLISHING/PUBLISHED/PENDING_REVIEW）。"""
    from app.models import MessageCampaign
    since = datetime.utcnow() - timedelta(minutes=window_minutes)
    with session() as db:
        n = db.scalar(select(func.count()).select_from(MessageCampaign).where(
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.sender_user_id == int(user_id),
            MessageCampaign.is_deleted.is_(False),
            MessageCampaign.created_at >= since,
            MessageCampaign.status.in_((
                "PENDING_REVIEW", "SCHEDULED", "PUBLISHING", "PUBLISHED",
                "PARTIAL_FAILED", "APPROVED",
            )),
        )) or 0
    if int(n) >= int(limit):
        raise AppException(
            "VALIDATION_ERROR",
            f"发布过于频繁：{window_minutes} 分钟内最多 {limit} 次，请稍后再试",
            http_status=429,
            details={"reason": "MESSAGE_RATE_LIMIT", "count": int(n), "limit": limit},
        )


def apply_quiet_hours_policy(*, emergency: bool, publish_mode: str,
                             scheduled_at: Optional[datetime],
                             now: Optional[datetime] = None) -> dict:
    """返回 {publishMode, scheduledAt, quietBypassed, note}。"""
    now = now or datetime.utcnow()
    mode = (publish_mode or "IMMEDIATE").upper()
    if emergency:
        if is_in_quiet_hours(now):
            return {
                "publishMode": mode,
                "scheduledAt": scheduled_at,
                "quietBypassed": True,
                "note": "紧急消息绕过静默时段",
            }
        return {
            "publishMode": mode,
            "scheduledAt": scheduled_at,
            "quietBypassed": False,
            "note": None,
        }
    if mode == "SCHEDULED" and scheduled_at:
        # 若预约落在静默窗，顺延到静默结束
        if is_in_quiet_hours(scheduled_at):
            end_at = next_quiet_end(scheduled_at)
            return {
                "publishMode": "SCHEDULED",
                "scheduledAt": end_at,
                "quietBypassed": False,
                "note": f"预约时间落在静默时段，已顺延至 {end_at.isoformat(sep=' ', timespec='minutes')}",
            }
        return {
            "publishMode": "SCHEDULED",
            "scheduledAt": scheduled_at,
            "quietBypassed": False,
            "note": None,
        }
    if is_in_quiet_hours(now):
        end_at = next_quiet_end(now)
        return {
            "publishMode": "SCHEDULED",
            "scheduledAt": end_at,
            "quietBypassed": False,
            "note": "当前处于静默时段，已改为静默结束后自动发布",
        }
    return {
        "publishMode": mode,
        "scheduledAt": scheduled_at,
        "quietBypassed": False,
        "note": None,
    }
