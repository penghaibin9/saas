from __future__ import annotations
import hashlib,hmac
from cryptography.fernet import Fernet,InvalidToken
from app.core.exceptions import AppException
from app.core.config import settings

def _key():
    value=(settings.field_encryption_key or "").strip()
    if not value:
        raise AppException("SECURITY_CONFIG_REQUIRED","服务端未配置字段加密密钥",http_status=503)
    try:
        Fernet(value.encode())
    except Exception as exc:
        raise AppException("SECURITY_CONFIG_INVALID","字段加密密钥格式非法",http_status=503) from exc
    return value

def encrypt_field(value):
    if value is None or value=="": return None
    return Fernet(_key().encode()).encrypt(str(value).encode()).decode()

def decrypt_field(value,*,allow_legacy_plaintext=True):
    if not value: return value
    text=str(value)
    try: return Fernet(_key().encode()).decrypt(text.encode()).decode()
    except InvalidToken:
        if allow_legacy_plaintext and not text.startswith("gAAAA"): return text
        raise AppException("SENSITIVE_DECRYPT_FAILED","敏感字段解密失败")

def encrypt_sensitive(value,field_type="generic"):
    return encrypt_field(value)

def decrypt_sensitive(value,field_type="generic",*,allow_legacy_plaintext=True):
    return decrypt_field(value,allow_legacy_plaintext=allow_legacy_plaintext)

def hash_sensitive(value,field_type="generic"):
    if value is None or value=="": return None
    key=(settings.sensitive_search_hmac_key or _key()).encode()
    return hmac.new(key,f"{field_type}:{value}".encode(),hashlib.sha256).hexdigest()

def mask_phone(value):
    text=str(value or "")
    return text[:3]+"****"+text[-4:] if len(text)>=7 else ("***" if text else "")

def mask_id_card(value):
    text=str(value or "")
    return text[:3]+"*"*max(len(text)-7,4)+text[-4:] if len(text)>=8 else ("***" if text else "")

def mask_phone_encrypted(value):
    if not value: return ""
    try: return mask_phone(decrypt_field(value))
    except Exception: return "***"

def mask_id_card_encrypted(value):
    if not value: return ""
    try: return mask_id_card(decrypt_field(value))
    except Exception: return "***"
