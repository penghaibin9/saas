"""大型归档的分块哈希与流式 ZIP 写入工具。"""
from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

CHUNK_SIZE = 1024 * 1024


def sha256_path(path: str | Path) -> tuple[str, int]:
    source = Path(path)
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as stream:
        while True:
            chunk = stream.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def add_path(
    archive: zipfile.ZipFile,
    archive_name: str,
    source_path: str | Path,
    *,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
) -> tuple[str, int]:
    """校验源文件并通过 ZipFile.open 分块写入，避免加载整个文件。"""
    source = Path(source_path)
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as reader, archive.open(archive_name, "w", force_zip64=True) as writer:
        while True:
            chunk = reader.read(CHUNK_SIZE)
            if not chunk:
                break
            writer.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    actual = digest.hexdigest()
    if expected_sha256 and actual != str(expected_sha256):
        from app.core.exceptions import AppException

        raise AppException("DATA_CONFLICT", "归档材料真实字节哈希校验失败")
    if expected_size is not None and size != int(expected_size):
        from app.core.exceptions import AppException

        raise AppException("DATA_CONFLICT", "归档材料真实字节大小与冻结清单不一致")
    return actual, size


def add_json(archive: zipfile.ZipFile, archive_name: str, payload: Any) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    archive.writestr(archive_name, data)


def temporary_zip(prefix: str = "file-center-") -> tuple[Path, zipfile.ZipFile]:
    handle = tempfile.NamedTemporaryFile(prefix=prefix, suffix=".zip", delete=False)
    path = Path(handle.name)
    handle.close()
    return path, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, allowZip64=True)
