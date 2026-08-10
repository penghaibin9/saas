"""强敏感字段静态加密（手机号等 `_encrypted` 列）。

写入统一 encrypt_field；读取统一 decrypt_field 再脱敏。
生产拒绝默认密钥；无效 Fernet 密文不得静默当明文使用。
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

_DEFAULT_DEV_KEY = "jxd5OL3YvyF335hh52bntwYmmA7ZJ_BXWxyZt4CcGd4="

# 密文信封：`k<版本>:<Fernet密文>`。
# 没有前缀的密文＝换钥机制上线前写入的历史数据，用全部已知密钥依次尝试。
_KID_PREFIX = "k"
_KID_SEP = ":"


def _fernet(key: str) -> Fernet:
    return Fernet(key.encode())


def _current_key() -> tuple[str, str]:
    from app.core.config import settings
    return settings.field_encryption_key_id, settings.field_encryption_key


def _all_keys() -> dict[str, str]:
    """{版本号: 密钥}，含当前密钥与全部历史密钥。"""
    from app.core.config import settings
    keys = dict(settings.field_encryption_previous_keys)
    kid, key = _current_key()
    keys[kid] = key
    return keys


def split_key_id(stored: str) -> tuple[str | None, str]:
    """拆出密文的密钥版本。无前缀（历史密文）返回 (None, 原文)。"""
    text = str(stored or "")
    if not text.startswith(_KID_PREFIX) or _KID_SEP not in text:
        return None, text
    head, _, body = text.partition(_KID_SEP)
    kid = head[len(_KID_PREFIX):]
    if kid and body.startswith("gAAAA"):
        return kid, body
    return None, text


def looks_like_fernet(value: str) -> bool:
    _, body = split_key_id(value)
    return body.startswith("gAAAA") and len(body) > 40


def encrypt_field(value) -> str | None:
    if value is None or value == "":
        return None
    kid, key = _current_key()
    token = _fernet(key).encrypt(str(value).encode()).decode()
    return f"{_KID_PREFIX}{kid}{_KID_SEP}{token}"


def _try_decrypt(text: str) -> str | None:
    """按密文自带的版本选密钥；历史无版本密文遍历全部已知密钥。"""
    kid, body = split_key_id(text)
    keys = _all_keys()
    candidates = [keys[kid]] if kid and kid in keys else list(keys.values())
    for key in candidates:
        try:
            return _fernet(key).decrypt(body.encode()).decode()
        except (InvalidToken, ValueError):
            continue
    return None


def decrypt_field(stored, *, allow_legacy_plaintext: bool = True) -> str | None:
    """解密。历史明文可兼容返回；疑似密文但解密失败则报错（生产）或返回 None。"""
    if not stored:
        return stored
    text = str(stored)
    plain = _try_decrypt(text)
    if plain is not None:
        return plain
    if allow_legacy_plaintext and not looks_like_fernet(text):
        return text
    from app.core.config import settings
    from app.core.exceptions import AppException
    import logging
    kid, _ = split_key_id(text)
    # 记下版本号：换钥后出问题时，这一行能直接指认"缺哪把旧钥匙"。
    logging.getLogger("app.crypto").error("sensitive_decrypt_failed key_id=%s", kid or "legacy")
    if settings.is_prod:
        raise AppException("SENSITIVE_DECRYPT_FAILED", "敏感字段解密失败，请联系管理员")
    return None


def hash_sensitive(value, field_type: str = "generic") -> str | None:
    """带服务器密钥的 HMAC-SHA256，用于检索匹配，不可逆。

    刻意**不**随 FIELD_ENCRYPTION_KEY 一起轮换：检索哈希一旦变化，历史行的
    检索列就全部失配。它用独立的 SENSITIVE_SEARCH_HMAC_KEY（未配置时回落到
    字段加密密钥，保持既有哈希继续命中）。要换这把钥匙必须整表重算检索列。
    """
    if value is None or value == "":
        return None
    import hashlib
    import hmac
    from app.core.config import settings
    key = (settings.sensitive_search_hmac_key or "").encode()
    msg = f"{field_type}:{value}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def encrypt_sensitive(value, field_type: str = "generic") -> str | None:
    """统一敏感字段加密入口（field_type 预留给密钥派生/审计）。"""
    _ = field_type
    return encrypt_field(value)


def decrypt_sensitive(value, field_type: str = "generic", *, allow_legacy_plaintext: bool = True) -> str | None:
    _ = field_type
    return decrypt_field(value, allow_legacy_plaintext=allow_legacy_plaintext)


def mask_phone(plain) -> str:
    """手机号脱敏（入参必须是明文）。密文列请用 mask_phone_encrypted。"""
    v = plain or ""
    return v[:3] + "****" + v[-4:] if len(v) >= 7 else ("***" if v else "")


def mask_id_card(plain) -> str:
    """身份证脱敏（入参必须是明文）。密文列请用 mask_id_card_encrypted。"""
    v = plain or ""
    return v[:3] + "*" * max(len(v) - 7, 4) + v[-4:] if len(v) >= 8 else ("***" if v else "")


def _mask_stored(stored, field_type: str, masker) -> str:
    """`_encrypted` 列的唯一正确读取路径：先解密再脱敏。

    列表展示不能因单行密文损坏整体 500，故解密失败降级为 `***`（不泄露、不中断），
    仅记 warning；需要准确明文的完整查看（reveal）仍直接用 decrypt_sensitive 让异常上抛。
    """
    if not stored:
        return ""
    try:
        plain = decrypt_field(stored)
    except Exception:  # noqa: BLE001 - 展示侧降级，真实原因已在 decrypt_field 落日志
        plain = None
    if not plain:
        # 有存值却解不出明文＝密文损坏或换过密钥。生产会抛异常、非生产返回 None，
        # 两种情况都统一降级为 ***：不泄露、不让列表 500，也不伪装成「未填写」。
        import logging
        logging.getLogger("app.crypto").warning("mask_stored_decrypt_failed field_type=%s", field_type)
        return "***"
    return masker(plain)


def mask_phone_encrypted(stored) -> str:
    """密文手机号 → 解密 → 脱敏。读取侧唯一正确入口。"""
    return _mask_stored(stored, "phone", mask_phone)


def mask_id_card_encrypted(stored) -> str:
    """密文身份证 → 解密 → 脱敏。读取侧唯一正确入口。"""
    return _mask_stored(stored, "id_card", mask_id_card)


def rewrap(stored) -> str | None:
    """把一条密文重新用当前密钥加密（换钥后的重加密任务用）。

    返回 None 表示无需处理（空值），返回原值表示已是当前密钥版本。
    解不开时抛异常——重加密任务必须知道哪条解不开，不能静默跳过。
    """
    if not stored:
        return stored
    text = str(stored)
    kid, _ = split_key_id(text)
    current_kid, _ = _current_key()
    if kid == current_kid:
        return text
    plain = _try_decrypt(text)
    if plain is None:
        if not looks_like_fernet(text):
            # 历史明文行（加密上线前写入）：这里正是把它加密掉的时机，不是错误。
            return encrypt_field(text)
        raise ValueError(f"密文无法用任何已知密钥解开（key_id={kid or 'legacy'}）")
    return encrypt_field(plain)


def key_rotation_status() -> dict:
    """当前密钥版本与可用历史密钥版本，供运维/健康检查确认换钥前提。"""
    from app.core.config import settings
    kid, _ = _current_key()
    return {
        "currentKeyId": kid,
        "previousKeyIds": sorted(settings.field_encryption_previous_keys.keys()),
        "searchHmacKeyIsSeparate": bool((settings.SENSITIVE_SEARCH_HMAC_KEY or "").strip()),
    }


def assert_field_encryption_safe() -> None:
    """生产禁止默认字段加密密钥；历史密钥必须是可用的 Fernet 密钥。"""
    from app.core.config import settings
    for kid, key in settings.field_encryption_previous_keys.items():
        try:
            Fernet(key.encode())
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"FIELD_ENCRYPTION_PREVIOUS_KEYS 中版本 {kid} 不是合法 Fernet 密钥：{exc}") from exc
    if not settings.is_prod:
        return
    key = (settings.field_encryption_key or "").strip()
    if not key or key == _DEFAULT_DEV_KEY or len(key) < 32:
        raise RuntimeError("生产环境必须设置独立 FIELD_ENCRYPTION_KEY（非开发默认值，长度合格）")
    if _DEFAULT_DEV_KEY in settings.field_encryption_previous_keys.values():
        raise RuntimeError("生产环境 FIELD_ENCRYPTION_PREVIOUS_KEYS 不得包含开发默认密钥")
