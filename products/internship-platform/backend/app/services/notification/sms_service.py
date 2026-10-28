"""Standalone SMS adapter.

默认 fail-closed：未开启短信返回 SKIPPED；已开启但未配置 Provider 返回 FAILED。
不在仓库保存供应商密钥，也不伪造发送成功。
"""
from __future__ import annotations

from typing import Protocol

from app.core.config import settings


class SmsProvider(Protocol):
    name: str

    def send(self, phone: str, template_code: str, params: dict) -> dict: ...


_provider: SmsProvider | None = None


def configure_provider(provider: SmsProvider | None) -> None:
    global _provider
    _provider = provider


def send_sms(
    tenant_id: int,
    phone: str | None,
    template_code: str,
    params: dict | None = None,
    biz_type: str = "TODO",
    receiver_name: str | None = None,
    provider: SmsProvider | None = None,
    sensitive_params: bool = False,
) -> dict:
    _ = tenant_id, biz_type, receiver_name, sensitive_params
    if not settings.SMS_ENABLED:
        return {
            "status": "SKIPPED",
            "reason": "SMS_ENABLED=false",
            "reasonCode": "SMS_DISABLED",
            "retryable": False,
        }
    if not phone or len(str(phone).strip()) < 7:
        return {
            "status": "SKIPPED",
            "reason": "缺手机号",
            "reasonCode": "PHONE_UNAVAILABLE",
            "retryable": False,
        }
    active = provider or _provider
    if active is None:
        return {
            "status": "FAILED",
            "reason": "SMS provider 未配置",
            "reasonCode": "SMS_PROVIDER_NOT_CONFIGURED",
            "retryable": False,
        }
    try:
        result = dict(active.send(str(phone), str(template_code), dict(params or {})) or {})
    except Exception:
        return {
            "status": "FAILED",
            "reason": "短信供应商调用失败",
            "reasonCode": "TRANSIENT_PROVIDER",
            "retryable": True,
        }
    status = str(result.get("status") or "").upper()
    if status not in {"SENT", "FAILED", "SKIPPED"}:
        return {
            "status": "FAILED",
            "reason": "短信供应商返回状态无效",
            "reasonCode": "INVALID_PROVIDER_RESPONSE",
            "retryable": False,
        }
    return result


def notify_guardian_consent(
    tenant_id,
    phone,
    name,
    params=None,
    provider=None,
):
    return send_sms(
        int(tenant_id),
        phone,
        "GUARDIAN_CONSENT",
        params,
        "INTERNSHIP_GUARDIAN_CONSENT",
        name,
        provider,
    )
