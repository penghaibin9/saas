"""包 8：归档快照只从证据快照字典读取稳定 fileId。

强制归档依据在正式绑定后保存为 file/version/hash/binding 字典。旧证据包采集器
曾对 ``*_file_ids`` 列表直接 ``str(item)``，会把整份字典误当文件 ID。这里保留
旧纯 ID 列表兼容，同时对快照字典只读取 ``fileId`` 并去重。
"""
from __future__ import annotations

from app.modules.internship.services import internship_evidence_package_service as base

_INSTALLED = False


def _append_unique(found: list[str], value) -> None:
    if isinstance(value, dict):
        value = value.get("fileId")
    text = str(value or "").strip()
    if text and text not in found:
        found.append(text)


def _file_ids(value: dict) -> list[str]:
    found: list[str] = []
    for key, item in (value or {}).items():
        lowered = str(key or "").lower()
        if lowered.endswith("file_id"):
            _append_unique(found, item)
        elif lowered.endswith("file_ids") and isinstance(item, list):
            for entry in item:
                _append_unique(found, entry)
    return found


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    base._file_ids = _file_ids
    _INSTALLED = True
