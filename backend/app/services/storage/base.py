"""存储后端接口。

写侧统一约定：file_service 先把字节流式写到本地临时位置（沿用现有 sha256 + 大小
校验逻辑），写完调 persist(key, local_temp) 交给后端持久化——本地后端就地保留，
COS 后端上传后清临时。读侧 fetch_local(key) 返回一个可直接 FileResponse 的本地路径，
本地后端即原文件，COS 后端按需拉回缓存。这样所有下载接口零改动。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    kind: str = "base"

    @abstractmethod
    def staging_path(self, key: str) -> Path:
        """返回写入前的本地临时落点（file_service 流式写到这里）。"""

    @abstractmethod
    def persist(self, key: str, staged: Path) -> None:
        """把已在 staged 的文件持久化到最终存储。本地：no-op；COS：上传后清临时。"""

    @abstractmethod
    def fetch_local(self, key: str) -> Path | None:
        """返回可读的本地路径供下载；对象不存在返回 None。COS：命中缓存或拉回。"""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """对象是否存在。"""

    @abstractmethod
    def delete(self, key: str) -> None:
        """删除对象（幂等，不存在不报错）。"""
