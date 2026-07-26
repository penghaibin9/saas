"""毕业设计运行时配置兼容。

归档预览令牌使用系统 JWT 强密钥签名。配置对象正式字段为 JWT_SECRET_KEY/JWT_SECRET，
这里提供单一只读别名，避免业务代码自行猜测配置字段或使用开发固定字符串。
"""
from __future__ import annotations

from app.core.config import settings

_INSTALLED = False


def signing_secret() -> str:
    secret = (getattr(settings, "JWT_SECRET_KEY", "") or getattr(settings, "JWT_SECRET", "") or "").strip()
    if len(secret) < 16:
        from app.core.exceptions import AppException
        raise AppException("SERVER_ERROR", "归档预览签名密钥未正确配置", http_status=503)
    return secret


def install_runtime_settings() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    cls = type(settings)
    if not hasattr(cls, "jwt_secret"):
        setattr(cls, "jwt_secret", property(lambda _self: signing_secret()))
