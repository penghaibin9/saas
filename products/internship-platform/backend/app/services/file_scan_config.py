"""公共文件扫描配置视图。使用环境变量，生产环境始终 fail-closed。"""
from __future__ import annotations

import os
from dataclasses import dataclass

from app.core.config import settings


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class FileScanConfig:
    enabled: bool
    required: bool
    host: str
    port: int
    unix_socket: str
    connect_timeout: float
    read_timeout: float
    chunk_size: int
    max_attempts: int
    retry_base_seconds: int
    stale_lock_seconds: int
    batch_size: int
    poll_seconds: float


def get_file_scan_config() -> FileScanConfig:
    return FileScanConfig(
        enabled=_bool("CLAMAV_ENABLED", False),
        required=bool(settings.is_prod or _bool("FILE_SCAN_REQUIRED", False)),
        host=os.getenv("CLAMAV_HOST", "127.0.0.1"),
        port=_int("CLAMAV_PORT", 3310),
        unix_socket=os.getenv("CLAMAV_UNIX_SOCKET", ""),
        connect_timeout=max(0.1, _float("CLAMAV_CONNECT_TIMEOUT", 2.0)),
        read_timeout=max(1.0, _float("CLAMAV_READ_TIMEOUT", 30.0)),
        chunk_size=max(64 * 1024, _int("FILE_SCAN_CHUNK_SIZE_KB", 1024) * 1024),
        max_attempts=max(1, _int("FILE_SCAN_MAX_ATTEMPTS", 5)),
        retry_base_seconds=max(1, _int("FILE_SCAN_RETRY_BASE_SECONDS", 30)),
        stale_lock_seconds=max(60, _int("FILE_SCAN_STALE_LOCK_SECONDS", 600)),
        batch_size=max(1, _int("FILE_SCAN_BATCH_SIZE", 10)),
        poll_seconds=max(0.2, _float("FILE_SCAN_POLL_SECONDS", 2.0)),
    )
