"""短信 provider 抽象基类 + 结果结构。
所有 provider 必须实现 send()，返回 SmsResult。真实 provider 为占位，不接真实密钥。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SmsResult:
    success: bool
    request_id: str | None = None
    error: str | None = None
    provider: str | None = None


class SmsProvider:
    name = "base"

    def send(self, phone: str, template_id: str, params: dict) -> SmsResult:  # noqa: D401
        raise NotImplementedError
