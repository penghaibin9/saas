"""不可猜测、按租户隔离的对象 Key 规则。"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from app.core.exceptions import AppException

ZONE_PREFIX = {
    "QUARANTINE": "quarantine",
    "CLEAN": "clean",
    "ACTIVE": "clean",  # 历史 ACTIVE 映射到正式 clean 分区
    "PREVIEW": "preview",
    "ARCHIVE": "archive",
    "EXPORT": "export",
    "REJECTED": "rejected",
    "TEMP": "temp",
}
_SAFE_EXT = re.compile(r"^[a-z0-9]{1,20}$")


def normalize_zone(zone: str) -> str:
    value = str(zone or "").strip().upper()
    if value not in ZONE_PREFIX:
        raise AppException("VALIDATION_ERROR", f"未知存储分区：{value or '-'}")
    return value


def build_object_key(*, zone: str, tenant_id: int, ext: str, now: datetime | None = None) -> str:
    zone = normalize_zone(zone)
    if int(tenant_id or 0) <= 0:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，不能生成对象 Key")
    suffix = str(ext or "").lower().lstrip(".")
    if not _SAFE_EXT.fullmatch(suffix):
        raise AppException("FILE_TYPE_NOT_ALLOWED", "文件扩展名不合法")
    current = now or datetime.utcnow()
    return (
        f"{ZONE_PREFIX[zone]}/{int(tenant_id)}/{current:%Y/%m}/"
        f"{uuid.uuid4().hex}.{suffix}"
    )


def assert_exact_object_key(object_key: str, *, zone: str, tenant_id: int) -> str:
    """STS 只允许当前租户精确对象，拒绝通配符和路径逃逸。"""
    value = str(object_key or "").strip().lstrip("/")
    prefix = f"{ZONE_PREFIX[normalize_zone(zone)]}/{int(tenant_id)}/"
    if not value.startswith(prefix) or ".." in value or "*" in value or "?" in value:
        raise AppException("FILE_STORAGE_SCOPE_INVALID", "对象 Key 超出当前租户和分区范围")
    if value.endswith("/"):
        raise AppException("FILE_STORAGE_SCOPE_INVALID", "临时授权必须指向单个对象")
    return value
