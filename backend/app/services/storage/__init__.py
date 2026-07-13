"""文件存储后端抽象。

file_service 只认「存储 key」（如 20260713/xxx.pdf），字节存在哪由本模块决定：
- local：字节落本地 UPLOAD_DIR（默认，行为与历史一字不变）。
- cos：字节落腾讯云对象存储 COS；上传时推到 COS，下载时按需拉回本地缓存。

关键：切换后端不改 t_file_object 表——file_key 语义在两种后端下相同，
迁移只是把字节从本地盘复制到 COS，数据库零改动。

后端选择由 settings.FILE_STORAGE_BACKEND 决定，进程内缓存单例。
"""
from __future__ import annotations

from app.services.storage.base import StorageBackend

_backend: StorageBackend | None = None
_backend_kind: str | None = None


def get_backend() -> StorageBackend:
    """按生效配置返回存储后端单例（平台运营端配置优先，回退 .env）。
    配置变化时经 reset_backend() 重建。"""
    global _backend, _backend_kind
    from app.services.storage.config import effective_config
    cfg = effective_config()
    kind = cfg["backend"]
    if _backend is not None and _backend_kind == kind:
        return _backend
    if kind == "cos":
        from app.services.storage.cos import CosStorageBackend
        _backend = CosStorageBackend(region=cfg["cosRegion"], bucket=cfg["cosBucket"],
                                     secret_id=cfg["cosSecretId"], secret_key=cfg["cosSecretKey"])
    else:
        from app.services.storage.local import LocalStorageBackend
        _backend = LocalStorageBackend()
    _backend_kind = kind
    return _backend


def reset_backend() -> None:
    """清缓存的后端单例（供测试在切换 settings 后强制重建）。"""
    global _backend, _backend_kind
    _backend = None
    _backend_kind = None
