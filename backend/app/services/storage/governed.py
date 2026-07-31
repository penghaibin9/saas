"""在物理写入边界统一执行并发安全的租户硬配额预留。

用户上传、系统生成 Excel/PDF/ZIP、错误回执等所有调用 StorageBackend.persist 的路径
先持久化 HELD 预留，再写物理对象。FileObject 登记后由预留服务自动对账消费；写入失败
立即释放，进程中断则按 TTL 回收。DB_DISABLED 模式直接委托物理后端。
"""
from __future__ import annotations

import hashlib
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
        from app.db.session import db_enabled

        reservation_key = ""
        if db_enabled() and staged.exists():
            from app.core.context import current_tenant_id
            from app.services.file_storage_quota_reservation_service import reserve_quota

            tenant_id = int(current_tenant_id() or 0)
            reservation_key = "persist:" + hashlib.sha256(
                f"{tenant_id}:{key}".encode("utf-8")
            ).hexdigest()
            reserve_quota(
                reservation_key=reservation_key,
                source_type="STORAGE_PERSIST",
                source_id=str(key),
                size_bytes=staged.stat().st_size,
                module_code="SHARED",
                tenant_id=tenant_id,
            )
        try:
            return self._delegate.persist(key, staged)
        except Exception:
            if reservation_key:
                from app.services.file_storage_quota_reservation_service import release_quota

                release_quota(reservation_key, reason="PHYSICAL_PERSIST_FAILED")
            raise

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
