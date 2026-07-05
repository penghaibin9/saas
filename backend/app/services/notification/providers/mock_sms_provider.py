"""Mock 短信 provider：永不真实发送，仅返回成功（可配置为失败，供测试重试用）。"""
from __future__ import annotations

import uuid

from app.services.notification.sms_provider import SmsProvider, SmsResult


class MockSmsProvider(SmsProvider):
    name = "mock"

    def __init__(self, fail: bool = False, fail_times: int = 0):
        # fail=True 恒失败；fail_times=N 前 N 次失败后成功（测重试）
        self._fail = fail
        self._fail_times = fail_times
        self._calls = 0

    def send(self, phone: str, template_id: str, params: dict) -> SmsResult:
        self._calls += 1
        if self._fail:
            return SmsResult(success=False, error="mock 恒失败", provider="mock")
        if self._calls <= self._fail_times:
            return SmsResult(success=False, error=f"mock 第{self._calls}次失败", provider="mock")
        return SmsResult(success=True, request_id="mock-" + uuid.uuid4().hex[:12], provider="mock")
