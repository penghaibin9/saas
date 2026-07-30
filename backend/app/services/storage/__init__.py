"""文件存储后端工厂。

FileObject 保存 bucket/objectKey/ETag 与分区；所有新物理写入由 GovernedStorageBackend 在最底层统一
执行租户硬配额。COS 普通下载走短时预签名，fetch_local 仅用于扫描、强敏感代理和核验。
"""
from __future__ import annotations

from app.services.storage.base import StorageBackend

_backend: StorageBackend | None = None
_backend_kind: str | None = None


def get_backend() -> StorageBackend:
    """按生效配置返回受治理的存储后端单例；配置变化时 reset_backend() 重建。"""
    global _backend, _backend_kind
    from app.services.storage.config import effective_config

    cfg = effective_config()
    kind = cfg["backend"]
    if _backend is not None and _backend_kind == kind:
        return _backend
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
    _backend_kind = kind
    return _backend


def reset_backend() -> None:
    """清缓存的后端单例（供测试或配置切换后强制重建）。"""
    global _backend, _backend_kind
    _backend = None
    _backend_kind = None
