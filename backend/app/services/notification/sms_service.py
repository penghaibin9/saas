"""短信发送编排（P13-B）。
职责：开关判断 → 手机号校验 → 频率限制 → 调 provider（带重试）→ 落任务/日志（脱敏）。
铁律：
- SMS_ENABLED != true 时永不真实发送，记录 SKIPPED。
- 测试环境（provider=mock）永不真实发送。
- 发送失败不抛异常，不影响主业务提交（fire-and-forget）。
- 手机号一律脱敏，日志不落明文。
- 全部按 tenant_id 隔离。
"""
from __future__ import annotations

import time

from app.core.config import settings
from app.db.session import db_enabled, get_sessionmaker
from app.services.db_service import _mask_phone
from app.services.notification.providers.aliyun_sms_provider import AliyunSmsProvider
from app.services.notification.providers.mock_sms_provider import MockSmsProvider
from app.services.notification.providers.tencent_sms_provider import TencentSmsProvider

_RATE: dict = {}


def _cfg(name: str, default):
    import os
    value = getattr(settings, name, None)
    if value in (None, ""):
        value = os.getenv(name, default)
    return value if value is not None else default


def _sms_enabled() -> bool:
    return str(_cfg("SMS_ENABLED", "false")).strip().lower() in (
        "true", "1", "yes", "on")


def get_provider(name: str | None = None):
    provider_name = str(name or _cfg("SMS_PROVIDER", "mock") or "mock").strip().lower()
    if provider_name == "aliyun":
        return AliyunSmsProvider()
    if provider_name == "tencent":
        return TencentSmsProvider()
    return MockSmsProvider()


def _template_id(template_code: str) -> str:
    return {
        "TODO": settings.SMS_TEMPLATE_TODO,
        "REJECTED": settings.SMS_TEMPLATE_REJECTED,
        "WARNING": settings.SMS_TEMPLATE_WARNING,
        "GUARDIAN_CONSENT": settings.SMS_TEMPLATE_GUARDIAN_CONSENT,
    }.get((template_code or "").upper(), "") or (template_code or "")


def _rate_ok(tenant_id: int) -> bool:
    bucket = int(time.time() // 60)
    key = (tenant_id, bucket)
    count = _RATE.get(key, 0)
    if count >= max(int(settings.SMS_RATE_LIMIT_PER_MINUTE or 30), 1):
        return False
    _RATE[key] = count + 1
    return True


def _log(tenant_id, task_id, biz_type, provider, phone_masked, result,
         reason=None, request_id=None):
    if not db_enabled():
        return
    try:
        from app.models import NotificationLog
        db = get_sessionmaker()()
        try:
            db.add(NotificationLog(
                tenant_id=tenant_id, task_id=task_id, biz_type=biz_type,
                channel="SMS", provider=provider, phone_masked=phone_masked,
                result=result, reason=reason, request_id=request_id))
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def _task(tenant_id, biz_type, template_code, receiver_name, phone_masked,
          params, status, retry_count=0, last_error=None):
    if not db_enabled():
        return None
    try:
        from app.models import NotificationTask
        db = get_sessionmaker()()
        try:
            task = NotificationTask(
                tenant_id=tenant_id, biz_type=biz_type, channel="SMS",
                template_code=template_code, receiver_name=receiver_name,
                receiver_phone_masked=phone_masked, payload_json=params,
                status=status, retry_count=retry_count, last_error=last_error)
            db.add(task)
            db.commit()
            db.refresh(task)
            return task.id
        finally:
            db.close()
    except Exception:
        return None


def send_sms(tenant_id: int, phone: str | None, template_code: str,
             params: dict | None = None, biz_type: str = "TODO",
             receiver_name: str | None = None, provider=None) -> dict:
    """发送一条短信。返回状态，绝不把发送异常转成业务成功。"""
    params = params or {}
    masked = _mask_phone(phone) if phone else ""
    try:
        if not _sms_enabled():
            task_id = _task(
                tenant_id, biz_type, template_code, receiver_name, masked,
                params, "SKIPPED", last_error="SMS_ENABLED=false")
            _log(tenant_id, task_id, biz_type, "-", masked, "SKIPPED",
                 reason="SMS 未开启（默认关闭）")
            return {"status": "SKIPPED", "reason": "SMS_ENABLED=false"}
        if not phone or len(str(phone)) < 7:
            task_id = _task(
                tenant_id, biz_type, template_code, receiver_name, masked,
                params, "SKIPPED", last_error="缺手机号")
            _log(tenant_id, task_id, biz_type, "-", masked, "SKIPPED",
                 reason="缺手机号")
            return {"status": "SKIPPED", "reason": "缺手机号"}
        if not _rate_ok(tenant_id):
            task_id = _task(
                tenant_id, biz_type, template_code, receiver_name, masked,
                params, "SKIPPED", last_error="超出发送频率")
            _log(tenant_id, task_id, biz_type, "-", masked, "SKIPPED",
                 reason="超出每分钟发送上限")
            return {"status": "SKIPPED", "reason": "超出发送频率"}
        sms_provider = provider or get_provider()
        template = _template_id(template_code)
        attempts = int(settings.SMS_MAX_RETRY or 2) + 1
        last_error = None
        for attempt in range(attempts):
            response = sms_provider.send(str(phone), template, params)
            if response.success:
                task_id = _task(
                    tenant_id, biz_type, template_code, receiver_name,
                    masked, params, "SENT", retry_count=attempt)
                _log(
                    tenant_id, task_id, biz_type,
                    response.provider or sms_provider.name, masked, "SUCCESS",
                    request_id=response.request_id)
                return {
                    "status": "SENT", "requestId": response.request_id,
                    "retries": attempt,
                }
            last_error = response.error
        task_id = _task(
            tenant_id, biz_type, template_code, receiver_name, masked,
            params, "FAILED", retry_count=attempts - 1,
            last_error=last_error)
        _log(tenant_id, task_id, biz_type, sms_provider.name, masked, "FAIL",
             reason=last_error)
        return {
            "status": "FAILED", "reason": last_error,
            "retries": attempts - 1,
        }
    except Exception as error:
        _log(tenant_id, None, biz_type, "-", masked, "FAIL",
             reason="内部异常:" + str(error)[:200])
        return {"status": "FAILED", "reason": "内部异常"}


def notify_todo(tenant_id, phone, name, params=None, provider=None):
    return send_sms(tenant_id, phone, "TODO", params, "TODO", name, provider)


def notify_rejected(tenant_id, phone, name, params=None, provider=None):
    return send_sms(
        tenant_id, phone, "REJECTED", params, "REJECTED", name, provider)


def notify_warning(tenant_id, phone, name, params=None, provider=None):
    return send_sms(
        tenant_id, phone, "WARNING", params, "WARNING", name, provider)


def notify_guardian_consent(tenant_id, phone, name, params=None, provider=None):
    return send_sms(
        tenant_id, phone, "GUARDIAN_CONSENT", params,
        "INTERNSHIP_GUARDIAN_CONSENT", name, provider)
