"""强敏感字段静态加密（手机号等 `_encrypted` 列）。

写入统一 encrypt_field；读取统一 decrypt_field 再脱敏。
生产拒绝默认密钥；无效 Fernet 密文不得静默当明文使用。
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

_DEFAULT_DEV_KEY = "jxd5OL3YvyF335hh52bntwYmmA7ZJ_BXWxyZt4CcGd4="


def _fernet() -> Fernet:
    from app.core.config import settings
    return Fernet(settings.field_encryption_key.encode())


def looks_like_fernet(value: str) -> bool:
    s = str(value or "")
    return s.startswith("gAAAA") and len(s) > 40


def encrypt_field(value) -> str | None:
    if value is None or value == "":
        return None
    return _fernet().encrypt(str(value).encode()).decode()


def decrypt_field(stored, *, allow_legacy_plaintext: bool = True) -> str | None:
    """解密。历史明文可兼容返回；疑似密文但解密失败则报错（生产）或返回 None。"""
    if not stored:
        return stored
    text = str(stored)
    try:
        return _fernet().decrypt(text.encode()).decode()
    except (InvalidToken, ValueError):
        if allow_legacy_plaintext and not looks_like_fernet(text):
            return text
        from app.core.config import settings
        from app.core.exceptions import AppException
        import logging
        logging.getLogger("app.crypto").error("sensitive_decrypt_failed")
        if settings.is_prod:
            raise AppException("SENSITIVE_DECRYPT_FAILED", "敏感字段解密失败，请联系管理员")
        return None


def hash_sensitive(value, field_type: str = "generic") -> str | None:
    """带服务器密钥的 HMAC-SHA256，用于检索匹配，不可逆。"""
    if value is None or value == "":
        return None
    import hashlib
    import hmac
    from app.core.config import settings
    key = (settings.field_encryption_key or "").encode()
    msg = f"{field_type}:{value}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def encrypt_sensitive(value, field_type: str = "generic") -> str | None:
    """统一敏感字段加密入口（field_type 预留给密钥派生/审计）。"""
    _ = field_type
    return encrypt_field(value)


def decrypt_sensitive(value, field_type: str = "generic", *, allow_legacy_plaintext: bool = True) -> str | None:
    _ = field_type
    return decrypt_field(value, allow_legacy_plaintext=allow_legacy_plaintext)


def assert_field_encryption_safe() -> None:
    """生产禁止默认字段加密密钥。"""
    from app.core.config import settings
    if not settings.is_prod:
        return
    key = (settings.field_encryption_key or "").strip()
    if not key or key == _DEFAULT_DEV_KEY or len(key) < 32:
        raise RuntimeError("生产环境必须设置独立 FIELD_ENCRYPTION_KEY（非开发默认值，长度合格）")
