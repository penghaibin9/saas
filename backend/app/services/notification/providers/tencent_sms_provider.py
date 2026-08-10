"""腾讯云短信 Provider。手机号按 E.164 传给 SendSms。"""
from __future__ import annotations

import json

from app.core.config import settings
from app.services.notification.sms_provider import SmsProvider, SmsResult


class TencentSmsProvider(SmsProvider):
    name = "tencent"

    def __init__(self, client=None):
        self._client = client

    def _build_client(self):
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.sms.v20210111 import sms_client

        cred = credential.Credential(settings.SMS_ACCESS_KEY_ID, settings.SMS_ACCESS_KEY_SECRET)
        http = HttpProfile()
        http.endpoint = "sms.tencentcloudapi.com"
        http.reqTimeout = int(settings.SMS_REQUEST_TIMEOUT_SECONDS or 5)
        profile = ClientProfile(httpProfile=http)
        return sms_client.SmsClient(cred, settings.SMS_TENCENT_REGION or "ap-guangzhou", profile)

    def send(self, phone: str, template_id: str, params: dict) -> SmsResult:
        if not (settings.SMS_ACCESS_KEY_ID and settings.SMS_ACCESS_KEY_SECRET
                and settings.SMS_SIGN_NAME and settings.SMS_TENCENT_SDK_APP_ID and template_id):
            return SmsResult(False, error="腾讯云短信配置不完整", provider=self.name,
                             provider_code="CONFIG_MISSING", retryable=False)
        try:
            from tencentcloud.sms.v20210111 import models

            req = models.SendSmsRequest()
            number = str(phone)
            if number.isdigit() and len(number) == 11:
                number = "+86" + number
            req.from_json_string(json.dumps({
                "PhoneNumberSet": [number],
                "SmsSdkAppId": str(settings.SMS_TENCENT_SDK_APP_ID),
                "SignName": settings.SMS_SIGN_NAME,
                "TemplateId": str(template_id),
                # 模板变量顺序以调用方 dict 的插入顺序为准。
                "TemplateParamSet": [str(value) for value in params.values()],
            }, ensure_ascii=False))
            response = (self._client or self._build_client()).SendSms(req)
            statuses = list(getattr(response, "SendStatusSet", None) or [])
            status = statuses[0] if statuses else None
            code = str(getattr(status, "Code", "") or "")
            request_id = str(getattr(response, "RequestId", "") or "") or None
            if code.lower() == "ok":
                return SmsResult(True, request_id=request_id, provider=self.name,
                                 provider_code=code, retryable=False)
            message = str(getattr(status, "Message", "") or code or "发送失败")
            retryable = code in {"InternalError", "InternalError.SendAndRecvFail"}
            return SmsResult(False, request_id=request_id, error=message[:200], provider=self.name,
                             provider_code=code, retryable=retryable)
        except Exception as exc:
            return SmsResult(False, error=f"腾讯云短信调用失败:{type(exc).__name__}",
                             provider=self.name, provider_code="SDK_ERROR", retryable=True)
