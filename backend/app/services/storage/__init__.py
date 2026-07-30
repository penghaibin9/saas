"""文件存储后端工厂。

FileObject 保存 bucket/objectKey/ETag 与分区；所有新物理写入由 GovernedStorageBackend 在最底层统一
执行租户硬配额。COS 普通下载走短时预签名，fetch_local 仅用于扫描、强敏感代理和核验。
"""
from __future__ import annotations

import hashlib

from app.services.storage.base import StorageBackend

_backend: StorageBackend | None = None
_backend_cache_key: tuple[str, ...] | None = None


def _config_cache_key(cfg: dict) -> tuple[str, ...]:
    kind = str(cfg.get("backend") or "local").lower()
    if kind != "cos":
        return (kind,)
    # 凭证只参与不可逆指纹，绝不写入日志或异常；同为 COS 但学校桶/地域/凭证不同必须重建客户端。
    secret_fingerprint = hashlib.sha256(
        f"{cfg.get('cosSecretId') or ''}:{cfg.get('cosSecretKey') or ''}".encode("utf-8")
    ).hexdigest()[:16]
    return (
        kind,
        str(cfg.get("cosRegion") or ""),
        str(cfg.get("cosBucket") or ""),
        secret_fingerprint,
    )


def get_backend() -> StorageBackend:
    """按完整生效配置返回受治理的存储后端单例，禁止跨租户复用错误 COS 客户端。"""
    global _backend, _backend_cache_key
    from app.services.storage.config import effective_config

    cfg = effective_config()
    cache_key = _config_cache_key(cfg)
    if _backend is not None and _backend_cache_key == cache_key:
        return _backend
    kind = cache_key[0]
    if kind == "cos":
        from app.services.storage.cos import CosStorageBackend

        delegate = CosStorageBackend(
            region=cfg["cosRegion"],
            bucket=cfg["cosBucket"],
            secret_id=cfg["cosSecretId"],
            secret_key=cfg["cosSecretKey"],
        )
    else:
        from app.services.storage.local import LocalStorageBackend

        delegate = LocalStorageBackend()
    from app.services.storage.governed import GovernedStorageBackend

    _backend = GovernedStorageBackend(delegate)
    _backend_cache_key = cache_key
    return _backend


def reset_backend() -> None:
    """清缓存的后端单例（供测试或配置切换后强制重建）。"""
    global _backend, _backend_cache_key
    _backend = None
    _backend_cache_key = None
