"""毕业设计运行时兼容安装。

- 归档预览令牌使用系统 JWT 强密钥签名；
- 安装选题志愿 Excel 的统一模板、预校验与确认规则；
- 安装毕业设计材料专用的业务对象下载授权链。
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

    from app.modules.graduation.services.graduation_material_access_consistency import (
        install_material_access_consistency,
    )
    from app.modules.graduation.services.graduation_topic_import_consistency import (
        install_topic_import_consistency,
    )
    install_material_access_consistency()
    install_topic_import_consistency()
