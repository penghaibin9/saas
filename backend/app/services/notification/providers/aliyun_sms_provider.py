"""阿里云短信 Provider。SDK 延迟导入，未启用短信时不会加载第三方包。"""
from __future__ import annotations

import json

from app.core.config import settings
from app.services.notification.sms_provider import SmsProvider, SmsResult


class AliyunSmsProvider(SmsProvider):
    name = "aliyun"

    def __init__(self, client=None):
        self._client = client

    def _build_client(self):
        from alibabacloud_dysmsapi20170525.client import Client
        from alibabacloud_tea_openapi import models as open_api_models

        config = open_api_models.Config(
            access_key_id=settings.SMS_ACCESS_KEY_ID,
            access_key_secret=settings.SMS_ACCESS_KEY_SECRET,
        )
        config.endpoint = "dysmsapi.aliyuncs.com"
        config.read_timeout = int(settings.SMS_REQUEST_TIMEOUT_SECONDS or 5) * 1000
        config.connect_timeout = int(settings.SMS_REQUEST_TIMEOUT_SECONDS or 5) * 1000
        return Client(config)

    def send(self, phone: str, template_id: str, params: dict) -> SmsResult:
        if not (settings.SMS_ACCESS_KEY_ID and settings.SMS_ACCESS_KEY_SECRET
                and settings.SMS_SIGN_NAME and template_id):
            return SmsResult(False, error="阿里云短信配置不完整", provider=self.name,
                             provider_code="CONFIG_MISSING", retryable=False)
        try:
            from alibabacloud_dysmsapi20170525 import models as sms_models

            client = self._client or self._build_client()
            request = sms_models.SendSmsRequest(
                phone_numbers=str(phone),
                sign_name=settings.SMS_SIGN_NAME,
                template_code=str(template_id),
                template_param=json.dumps(params, ensure_ascii=False, separators=(",", ":")),
            )
            response = client.send_sms(request)
            body = getattr(response, "body", None)
            code = str(getattr(body, "code", "") or "")
            request_id = str(getattr(body, "request_id", "") or "") or None
            if code.upper() == "OK":
                return SmsResult(True, request_id=request_id, provider=self.name,
                                 provider_code=code, retryable=False)
            message = str(getattr(body, "message", "") or code or "发送失败")
            retryable = code in {"isp.RAM_PERMISSION_DENY", "isv.SYSTEM_ERROR", "isp.SYSTEM_ERROR"}
            return SmsResult(False, request_id=request_id, error=message[:200], provider=self.name,
                             provider_code=code, retryable=retryable)
        except Exception as exc:  # SDK/network failures are converted to a delivery result
            return SmsResult(False, error=f"阿里云短信调用失败:{type(exc).__name__}",
                             provider=self.name, provider_code="SDK_ERROR", retryable=True)
