"""短信发送编排（P13-B）。
职责：开关判断 → 手机号校验 → 频率限制 → 调 provider（带重试）→ 落任务/日志（脱敏）。
铁律：
- SMS_ENABLED != true 时**永不真实发送**，记录 SKIPPED。
- 测试环境（provider=mock）永不真实发送。
- 发送失败**不抛异常**，不影响主业务提交（fire-and-forget）。
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

# 每租户每分钟计数：{(tenant_id, minute_bucket): count}
_RATE: dict = {}


def _cfg(name: str, default):
    # 容错读取（即便配置类临时缺字段也不崩，回退默认/环境变量）
    import os
    v = getattr(settings, name, None)
    if v in (None, ""):
        v = os.getenv(name, default)
    return v if v is not None else default


def _sms_enabled() -> bool:
    return str(_cfg("SMS_ENABLED", "false")).strip().lower() in ("true", "1", "yes", "on")


def get_provider(name: str | None = None):
    n = str(name or _cfg("SMS_PROVIDER", "mock") or "mock").strip().lower()
    if n == "aliyun":
        return AliyunSmsProvider()
    if n == "tencent":
        return TencentSmsProvider()
    return MockSmsProvider()


def _template_id(template_code: str) -> str:
    return {
        "TODO": settings.SMS_TEMPLATE_TODO,
        "REJECTED": settings.SMS_TEMPLATE_REJECTED,
        "WARNING": settings.SMS_TEMPLATE_WARNING,
    }.get((template_code or "").upper(), "") or (template_code or "")


def _rate_ok(tenant_id: int) -> bool:
    bucket = int(time.time() // 60)
    key = (tenant_id, bucket)
    cnt = _RATE.get(key, 0)
    if cnt >= max(int(settings.SMS_RATE_LIMIT_PER_MINUTE or 30), 1):
        return False
    _RATE[key] = cnt + 1
    return True


def _log(tenant_id, task_id, biz_type, provider, phone_masked, result, reason=None, request_id=None):
    if not db_enabled():
        return
    try:
        from app.models import NotificationLog
        db = get_sessionmaker()()
        try:
            db.add(NotificationLog(tenant_id=tenant_id, task_id=task_id, biz_type=biz_type,
                                   channel="SMS", provider=provider, phone_masked=phone_masked,
                                   result=result, reason=reason, request_id=request_id))
            db.commit()
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        pass  # 日志失败绝不影响主流程


def _task(tenant_id, biz_type, template_code, receiver_name, phone_masked, params, status,
          retry_count=0, last_error=None):
    if not db_enabled():
        return None
    try:
        from app.models import NotificationTask
        db = get_sessionmaker()()
        try:
            t = NotificationTask(tenant_id=tenant_id, biz_type=biz_type, channel="SMS",
                                 template_code=template_code, receiver_name=receiver_name,
                                 receiver_phone_masked=phone_masked, payload_json=params,
                                 status=status, retry_count=retry_count, last_error=last_error)
            db.add(t)
            db.commit()
            db.refresh(t)
            return t.id
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        return None


def send_sms(tenant_id: int, phone: str | None, template_code: str, params: dict | None = None,
             biz_type: str = "TODO", receiver_name: str | None = None, provider=None) -> dict:
    """发送一条短信（受开关/频率控制）。返回 {status, reason?}。绝不抛异常。"""
    params = params or {}
    masked = _mask_phone(phone) if phone else ""
    try:
        # 1) 总开关
        if not _sms_enabled():
            tid = _task(tenant_id, biz_type, template_code, receiver_name, masked, params, "SKIPPED",
                        last_error="SMS_ENABLED=false")
            _log(tenant_id, tid, biz_type, "-", masked, "SKIPPED", reason="SMS 未开启（默认关闭）")
            return {"status": "SKIPPED", "reason": "SMS_ENABLED=false"}
        # 2) 手机号
        if not phone or len(str(phone)) < 7:
            tid = _task(tenant_id, biz_type, template_code, receiver_name, masked, params, "SKIPPED",
                        last_error="缺手机号")
            _log(tenant_id, tid, biz_type, "-", masked, "SKIPPED", reason="缺手机号")
            return {"status": "SKIPPED", "reason": "缺手机号"}
        # 3) 频率限制
        if not _rate_ok(tenant_id):
            tid = _task(tenant_id, biz_type, template_code, receiver_name, masked, params, "SKIPPED",
                        last_error="超出发送频率")
            _log(tenant_id, tid, biz_type, "-", masked, "SKIPPED", reason="超出每分钟发送上限")
            return {"status": "SKIPPED", "reason": "超出发送频率"}
        # 4) 发送 + 重试
        p = provider or get_provider()
        tpl = _template_id(template_code)
        attempts = int(settings.SMS_MAX_RETRY or 2) + 1
        last_err = None
        for i in range(attempts):
            res = p.send(str(phone), tpl, params)
            if res.success:
                tid = _task(tenant_id, biz_type, template_code, receiver_name, masked, params, "SENT",
                            retry_count=i)
                _log(tenant_id, tid, biz_type, res.provider or p.name, masked, "SUCCESS",
                     request_id=res.request_id)
                return {"status": "SENT", "requestId": res.request_id, "retries": i}
            last_err = res.error
        tid = _task(tenant_id, biz_type, template_code, receiver_name, masked, params, "FAILED",
                    retry_count=attempts - 1, last_error=last_err)
        _log(tenant_id, tid, biz_type, p.name, masked, "FAIL", reason=last_err)
        return {"status": "FAILED", "reason": last_err, "retries": attempts - 1}
    except Exception as e:  # noqa: BLE001  发送异常绝不影响主业务
        _log(tenant_id, None, biz_type, "-", masked, "FAIL", reason="内部异常:" + str(e)[:200])
        return {"status": "FAILED", "reason": "内部异常"}


# ── 三类业务事件封装（供主业务在合适处调用；不侵入主流程强绑定）──

def notify_todo(tenant_id, phone, name, params=None, provider=None):
    return send_sms(tenant_id, phone, "TODO", params, "TODO", name, provider)


def notify_rejected(tenant_id, phone, name, params=None, provider=None):
    return send_sms(tenant_id, phone, "REJECTED", params, "REJECTED", name, provider)


def notify_warning(tenant_id, phone, name, params=None, provider=None):
    return send_sms(tenant_id, phone, "WARNING", params, "WARNING", name, provider)
