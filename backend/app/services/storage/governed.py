"""在物理写入边界统一执行租户硬配额。

这样用户上传、系统生成 Excel/PDF/ZIP、错误回执等所有调用 StorageBackend.persist 的路径都受同一
配额约束，不依赖每个业务页面记得调用治理服务。
"""
from __future__ import annotations

from pathlib import Path


class GovernedStorageBackend:
    def __init__(self, delegate) -> None:
        self._delegate = delegate
        self.kind = getattr(delegate, "kind", "unknown")

    def __getattr__(self, name):
        return getattr(self._delegate, name)

    def staging_path(self, key: str) -> Path:
        return self._delegate.staging_path(key)

    def persist(self, key: str, staged: Path):
        from app.services.file_storage_governance_service import assert_quota_available

        if staged.exists():
            assert_quota_available(staged.stat().st_size)
        return self._delegate.persist(key, staged)

    def fetch_local(self, key: str):
        return self._delegate.fetch_local(key)

    def exists(self, key: str) -> bool:
        return self._delegate.exists(key)

    def delete(self, key: str) -> None:
        self._delegate.delete(key)

    def head_object(self, key: str):
        method = getattr(self._delegate, "head_object", None)
        return method(key) if method else None

    def copy_object(self, source_key: str, target_key: str):
        return self._delegate.copy_object(source_key, target_key)

    def presigned_download_url(self, key: str, *, filename: str, expires_seconds: int = 180):
        return self._delegate.presigned_download_url(key, filename=filename, expires_seconds=expires_seconds)
