"""本地磁盘存储后端（默认）。

行为与历史 file_service 直接操作 UPLOAD_DIR 完全一致：字节流式写到
UPLOAD_DIR/key 后就地保留，下载即返回该路径。persist 是 no-op（文件写完即在位）。
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings


class LocalStorageBackend:
    kind = "local"

    def _root(self) -> Path:
        d = Path(settings.UPLOAD_DIR or "./uploads")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def staging_path(self, key: str) -> Path:
        # 本地后端的临时落点即最终落点：写完就在位，persist 无需搬运。
        target = self._root() / key
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def persist(self, key: str, staged: Path) -> None:
        return None

    def fetch_local(self, key: str) -> Path | None:
        path = self._root() / key
        return path if path.exists() else None

    def exists(self, key: str) -> bool:
        return (self._root() / key).exists()

    def delete(self, key: str) -> None:
        (self._root() / key).unlink(missing_ok=True)
