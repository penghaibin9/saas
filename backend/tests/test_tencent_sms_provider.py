from __future__ import annotations

import json


class _Status:
    Code = "Ok"
    Message = "send success"


class _Response:
    RequestId = "req-test-1"
    SendStatusSet = [_Status()]


class _Client:
    def __init__(self):
        self.payload = None

    def SendSms(self, request):
        self.payload = json.loads(request.to_json_string())
        return _Response()


def test_tencent_provider_maps_cloud_api_3_request(monkeypatch):
    from app.core.config import settings
    from app.services.notification.providers.tencent_sms_provider import TencentSmsProvider

    monkeypatch.setattr(settings, "SMS_ACCESS_KEY_ID", "test-secret-id")
    monkeypatch.setattr(settings, "SMS_ACCESS_KEY_SECRET", "test-secret-key")
    monkeypatch.setattr(settings, "SMS_SIGN_NAME", "测试学校")
    monkeypatch.setattr(settings, "SMS_TENCENT_SDK_APP_ID", "1400000000")
    client = _Client()
    result = TencentSmsProvider(client=client).send(
        "13812345678", "900001", {"code": "123456"},
    )
    assert result.success is True and result.request_id == "req-test-1"
    assert client.payload["PhoneNumberSet"] == ["+8613812345678"]
    assert client.payload["SmsSdkAppId"] == "1400000000"
    assert client.payload["TemplateId"] == "900001"
    assert client.payload["TemplateParamSet"] == ["123456"]
