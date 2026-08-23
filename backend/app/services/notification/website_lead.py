"""官网商务咨询短信转发。

隐私约束：
- 不创建销售线索表，不写业务数据库。
- 不调用 sms_service.send_sms（该函数会写 NotificationTask/NotificationLog）。
- 访客学校、联系人、电话、意向、留言只在本次请求内存与短信供应商请求中存在。
- 防滥用只保存不可逆摘要计数；生产优先 Redis，Redis 不可用时 fail closed。
"""
from __future__ import annotations

import hashlib
import os
import threading
import time

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.core.redis_client import _prefix, get_redis
from app.services.notification.sms_service import get_provider

_MEM_RATE: dict[tuple[str, int], int] = {}
_MEM_LOCK = threading.Lock()


class WebsiteLeadRequest(BaseModel):
    school_name: str = Field(min_length=2, max_length=80)
    contact_name: str = Field(default="", max_length=40)
    phone: str = Field(min_length=11, max_length=11)
    interest: str = Field(min_length=2, max_length=40)
    message: str = Field(default="", max_length=200)
    website: str = Field(default="", max_length=120)  # honeypot
    source_path: str = Field(default="/contact", max_length=120)

    @field_validator("school_name", "contact_name", "interest", "message", "website", "source_path", mode="before")
    @classmethod
    def _clean_text(cls, value):
        return " ".join(str(value or "").strip().split())

    @field_validator("phone", mode="before")
    @classmethod
    def _clean_phone(cls, value):
        phone = "".join(ch for ch in str(value or "") if ch.isdigit())
        if len(phone) != 11 or not phone.startswith("1") or phone[1] not in "3456789":
            raise ValueError("请输入有效的中国大陆手机号")
        return phone


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


def _is_live_env() -> bool:
    return bool(settings.is_prod or str(settings.APP_ENV or "").strip().lower() == "staging")


def _sms_enabled() -> bool:
    return str(getattr(settings, "SMS_ENABLED", "") or "").strip().lower() in {"true", "1", "yes", "on"}


def _rate_digest(client_ip: str) -> str:
    salt = _env("WEBSITE_LEAD_RATE_SALT", str(getattr(settings, "JWT_SECRET", "") or "website-lead"))
    return hashlib.sha256(f"{salt}|{client_ip or 'unknown'}".encode("utf-8")).hexdigest()[:32]


def allow_website_lead(client_ip: str) -> tuple[bool, str]:
    """每 IP 每小时最多 6 次。只保存 IP 的不可逆摘要计数，不保存表单内容。"""
    bucket = int(time.time() // 3600)
    limit = max(int(_env("WEBSITE_LEAD_RATE_LIMIT_PER_HOUR", "6")), 1)
    digest = _rate_digest(client_ip)
    redis = get_redis()
    if redis is not None:
        key = _prefix(f"website-lead:rate:{bucket}:{digest}")
        count = int(redis.incr(key))
        if count == 1:
            redis.expire(key, 3700)
        return count <= limit, "RATE_LIMITED" if count > limit else "OK"

    if _is_live_env():
        return False, "RATE_STORE_UNAVAILABLE"

    key = (digest, bucket)
    with _MEM_LOCK:
        count = _MEM_RATE.get(key, 0) + 1
        _MEM_RATE[key] = count
        for old in [item for item in _MEM_RATE if item[1] < bucket - 2]:
            _MEM_RATE.pop(old, None)
    return count <= limit, "RATE_LIMITED" if count > limit else "OK"


def send_website_lead_sms(payload: WebsiteLeadRequest) -> dict:
    """直接调用 provider；不写 NotificationTask/NotificationLog，也不记录 PII 日志。"""
    if payload.website:
        return {"status": "IGNORED_BOT"}

    if not _sms_enabled():
        return {"status": "UNAVAILABLE", "reasonCode": "SMS_DISABLED"}

    template_id = _env("SMS_TEMPLATE_WEBSITE_LEAD")
    recipient = _env("WEBSITE_LEAD_NOTIFY_PHONE", "13549666867")
    if not template_id or not recipient:
        return {"status": "UNAVAILABLE", "reasonCode": "CONFIG_MISSING"}

    provider = get_provider()
    if _is_live_env() and getattr(provider, "name", "") == "mock":
        return {"status": "UNAVAILABLE", "reasonCode": "PROVIDER_NOT_LIVE"}

    # 腾讯云短信模板变量按 dict 插入顺序传递：
    # {1}=学校 {2}=联系人 {3}=访客电话 {4}=意向 {5}=留言。
    # 为降低模板变量超长风险，仅在短信内做展示截断；原始表单不会被持久化。
    params = {
        "school": payload.school_name[:30],
        "contact": (payload.contact_name or "未填写")[:12],
        "phone": payload.phone,
        "interest": payload.interest[:16],
        "message": (payload.message or "希望进一步沟通")[:36],
    }

    attempts = max(int(getattr(settings, "SMS_MAX_RETRY", 2) or 2), 0) + 1
    last = None
    for _ in range(attempts):
        last = provider.send(recipient, template_id, params)
        if getattr(last, "success", False):
            return {"status": "SENT"}
        if not getattr(last, "retryable", False):
            break

    return {
        "status": "UNAVAILABLE",
        "reasonCode": str(getattr(last, "provider_code", "") or "PROVIDER_FAILED")[:64],
    }
