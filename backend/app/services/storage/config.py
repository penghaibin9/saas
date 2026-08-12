"""文件存储配置：平台运营端可视化配置的读写 + 密钥加密 + 生效值合并。

配置优先级：平台运营端界面配置（t_platform_config，config_type=FILE_STORAGE）
> .env / 环境变量（settings）。运营端填的配置即时生效，小白无需碰配置文件。

密钥安全：COS_SECRET_KEY 使用系统独立的 FIELD_ENCRYPTION_KEY 密钥环加密后存库，
不再与 JWT 签名密钥耦合。历史上由 JWT 派生 Fernet 写入的无版本密文仍可读取；
下次保存配置时会自动重包为当前字段加密密钥版本。读回前端一律脱敏（只留后 4 位）。
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_CONFIG_TYPE = "FILE_STORAGE"
_MASK = "********"


def _legacy_jwt_fernet() -> Fernet:
    """仅用于读取旧版由 JWT 密钥派生的 COS SecretKey 密文，禁止新写入继续使用。"""
    seed = (settings.JWT_SECRET_KEY or getattr(settings, "jwt_secret", "") or "dev-storage-key").encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
    return Fernet(key)


def _encrypt(plain: str) -> str:
    """新写入统一走可轮换的字段加密密钥环，密文自带 key id。"""
    if not plain:
        return ""
    from app.core.field_crypto import encrypt_field

    return encrypt_field(plain) or ""


def _decrypt(token: str) -> str:
    """解密平台存储密钥；新格式 fail-closed，旧 JWT 派生密文只做兼容读取。

    新密文形如 ``k<id>:gAAAA...``，必须由 FIELD_ENCRYPTION_KEY/历史 keyring 解开；
    若解不开，生产环境直接报错，不能静默回退另一份环境变量密钥而制造配置假绿。
    无 key-id 的 ``gAAAA...`` 视为历史格式：先尝试字段密钥环，再尝试当前 JWT 派生旧钥。
    """
    if not token:
        return ""

    text = str(token)
    from app.core.field_crypto import decrypt_field, split_key_id

    kid, _ = split_key_id(text)
    if kid:
        # 带版本的新格式已经明确属于字段加密 keyring；失败必须保留 field_crypto 的
        # SENSITIVE_DECRYPT_FAILED 语义，不能误当旧 JWT 密文继续兜底。
        return decrypt_field(text, allow_legacy_plaintext=False) or ""

    # 历史无版本 Fernet：先兼容极少数可能由字段密钥写出的无前缀数据。
    try:
        plain = decrypt_field(text, allow_legacy_plaintext=False)
        if plain:
            return plain
    except Exception:  # noqa: BLE001 - 继续尝试唯一允许的 legacy JWT 兼容路径
        pass

    try:
        return _legacy_jwt_fernet().decrypt(text.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        if settings.is_prod:
            from app.core.exceptions import AppException

            raise AppException(
                "STORAGE_CONFIG_DECRYPT_FAILED",
                "文件存储密钥解密失败，请先恢复正确的历史密钥后再继续",
                http_status=503,
            )
        return ""


def _mask(secret: str) -> str:
    if not secret:
        return ""
    tail = secret[-4:] if len(secret) >= 4 else secret
    return f"{_MASK}{tail}"


def _stored() -> dict:
    """平台运营端已保存的原始配置（含加密密钥密文）。DB 未启用或无记录返回空。"""
    from app.db.session import db_enabled
    if not db_enabled():
        return {}
    try:
        from app.services import platform_service
        return platform_service.get_config_json(0, _CONFIG_TYPE, "-") or {}
    except Exception:  # noqa: BLE001 — 配置读取失败不阻断上传下载，回退 .env
        return {}


def effective_config() -> dict:
    """后端内部用的生效配置（secretKey 已解密为明文）。DB 配置优先，回退 settings。"""
    s = _stored()
    backend = (s.get("backend") or getattr(settings, "FILE_STORAGE_BACKEND", "") or "local").strip().lower()
    region = s.get("cosRegion") or getattr(settings, "COS_REGION", "") or ""
    bucket = s.get("cosBucket") or getattr(settings, "COS_BUCKET", "") or ""
    secret_id = s.get("cosSecretId") or getattr(settings, "COS_SECRET_ID", "") or ""
    stored_secret = s.get("cosSecretKeyEnc") or ""
    secret_key = _decrypt(stored_secret) if stored_secret else (getattr(settings, "COS_SECRET_KEY", "") or "")
    return {"backend": backend, "cosRegion": region, "cosBucket": bucket,
            "cosSecretId": secret_id, "cosSecretKey": secret_key,
            "source": "platform" if s else "env"}


def masked_config() -> dict:
    """给前端读回：密钥脱敏，不返回明文。"""
    e = effective_config()
    return {"backend": e["backend"], "cosRegion": e["cosRegion"], "cosBucket": e["cosBucket"],
            "cosSecretId": _mask(e["cosSecretId"]), "cosSecretKey": _mask(e["cosSecretKey"]),
            "hasSecretId": bool(e["cosSecretId"]), "hasSecretKey": bool(e["cosSecretKey"]),
            "source": e["source"]}


def save_config(payload: dict) -> dict:
    """保存平台运营端配置；旧密文在正常保存时自动重包为当前 FIELD_ENCRYPTION_KEY。"""
    from app.core.exceptions import AppException
    from app.services import platform_service
    prev = _stored()
    backend = (payload.get("backend") or "local").strip().lower()
    if backend not in ("local", "cos"):
        raise AppException("VALIDATION_ERROR", "存储后端只能是 local 或 cos")

    region = (payload.get("cosRegion") or "").strip()
    bucket = (payload.get("cosBucket") or "").strip()
    new_id = (payload.get("cosSecretId") or "").strip()
    new_key = (payload.get("cosSecretKey") or "").strip()

    # 脱敏占位（未修改）或留空则沿用旧值，避免读回脱敏后再保存把真密钥抹掉。
    if new_id.startswith(_MASK) or not new_id:
        secret_id = prev.get("cosSecretId", "")
    else:
        secret_id = new_id

    if new_key.startswith(_MASK) or not new_key:
        previous_enc = prev.get("cosSecretKeyEnc", "")
        if previous_enc:
            # 正常保存就是安全迁移点：先证明旧密文仍能解开，再用当前 key-id 重包。
            previous_plain = _decrypt(previous_enc)
            secret_key_enc = _encrypt(previous_plain) if previous_plain else previous_enc
        else:
            secret_key_enc = ""
    else:
        secret_key_enc = _encrypt(new_key)

    if backend == "cos":
        missing = [n for n, v in (("地域", region), ("桶名", bucket),
                                  ("SecretId", secret_id), ("SecretKey", secret_key_enc)) if not v]
        if missing:
            raise AppException("VALIDATION_ERROR",
                               f"启用腾讯云 COS 需要填写：{('、'.join(missing))}")

    stored = {"backend": backend, "cosRegion": region, "cosBucket": bucket,
              "cosSecretId": secret_id, "cosSecretKeyEnc": secret_key_enc}
    platform_service.put_config_json(0, _CONFIG_TYPE, "-", stored)
    from app.services import storage
    storage.reset_backend()  # 配置变更即时生效
    return masked_config()


def test_connection() -> dict:
    """用生效配置试连 COS：写一个探针对象再删。返回 {ok, message}。"""
    e = effective_config()
    if e["backend"] != "cos":
        return {"ok": False, "message": "当前后端是「本地磁盘」，无需连接对象存储。切到 COS 并保存后再测试。"}
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError:
        return {"ok": False, "message": "服务器未安装 cos-python-sdk-v5，请先安装：pip install cos-python-sdk-v5"}
    for name, val in (("地域", e["cosRegion"]), ("桶名", e["cosBucket"]),
                      ("SecretId", e["cosSecretId"]), ("SecretKey", e["cosSecretKey"])):
        if not val:
            return {"ok": False, "message": f"缺少 {name}，请先填写并保存。"}
    try:
        client = CosS3Client(CosConfig(Region=e["cosRegion"], SecretId=e["cosSecretId"],
                                       SecretKey=e["cosSecretKey"], Token=None, Scheme="https"))
        probe_key = ".healthcheck/probe.txt"
        client.put_object(Bucket=e["cosBucket"], Body=b"ok", Key=probe_key)
        client.delete_object(Bucket=e["cosBucket"], Key=probe_key)
        return {"ok": True, "message": "连接成功！腾讯云 COS 读写正常，可以放心切换。"}
    except Exception as exc:  # noqa: BLE001 — 把真实错误友好回传给运营者排错
        return {"ok": False, "message": f"连接失败：{exc}"}
