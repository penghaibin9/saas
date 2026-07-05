"""腾讯云短信 provider（占位）。
未接入真实 SDK；配置真实密钥并实现 send() 后方可上线。默认返回失败（占位），不真实发送。
真实实现步骤（上线时）：
  pip install tencentcloud-sdk-python-sms
  用 SMS_ACCESS_KEY_ID / SMS_ACCESS_KEY_SECRET / SMS_SIGN_NAME + provider_template_id 调 SendSms。
"""
from __future__ import annotations

from app.core.config import settings
from app.services.notification.sms_provider import SmsProvider, SmsResult


class TencentSmsProvider(SmsProvider):
    name = "tencent"

    def send(self, phone: str, template_id: str, params: dict) -> SmsResult:
        if not (settings.SMS_ACCESS_KEY_ID and settings.SMS_ACCESS_KEY_SECRET):
            return SmsResult(success=False, error="腾讯云短信未配置密钥（占位）", provider="tencent")
        # TODO 上线：接入 tencentcloud-sdk SMS，真实发送
        return SmsResult(success=False, error="腾讯云短信 provider 未实现真实发送（占位）", provider="tencent")
