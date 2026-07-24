"""上传内容安全：扩展名 / Content-Type / magic bytes 一致性、文件名消毒、ZIP 风险、可替换扫描器。"""
from __future__ import annotations

import re
import zipfile
from io import BytesIO
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import AppException

# 状态机（t_file_object.status）
FILE_STATUS_UPLOADING = "UPLOADING"
FILE_STATUS_QUARANTINED = "QUARANTINED"
FILE_STATUS_AVAILABLE = "AVAILABLE"
FILE_STATUS_REJECTED = "REJECTED"
FILE_STATUS_DELETED = "DELETED"
# 历史值兼容
_LEGACY_AVAILABLE = frozenset({"STORED", "AVAILABLE", ""})

MAX_FILENAME_LEN = 180

# 扩展名 → 允许的声明 Content-Type 子集（空则不强制客户端类型）
_EXT_MIME: dict[str, set[str]] = {
    "pdf": {"application/pdf"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "gif": {"image/gif"},
    "txt": {"text/plain", "text/csv", "application/octet-stream"},
    "csv": {"text/csv", "text/plain", "application/vnd.ms-excel", "application/octet-stream"},
    "zip": {"application/zip", "application/x-zip-compressed", "application/octet-stream"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip", "application/octet-stream",
    },
    "xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip", "application/octet-stream",
    },
    "pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip", "application/octet-stream",
    },
    "doc": {"application/msword", "application/octet-stream"},
    "xls": {"application/vnd.ms-excel", "application/octet-stream"},
    "ppt": {"application/vnd.ms-powerpoint", "application/octet-stream"},
}

# 高风险：无真实杀毒时不得默认 AVAILABLE
_HIGH_RISK_EXT = frozenset({"zip", "docx", "xlsx", "pptx", "doc", "xls", "ppt"})


def sanitize_filename(filename: str | None) -> str:
    """去路径、控制字符、CRLF，限制长度。"""
    name = (filename or "unnamed").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = name.replace("\r", "").replace("\n", "")
    name = name.strip().strip(".")
    if not name:
        name = "unnamed"
    if len(name) > MAX_FILENAME_LEN:
        stem, _, ext = name.rpartition(".")
        if ext and len(ext) <= 20:
            keep = MAX_FILENAME_LEN - len(ext) - 1
            name = f"{stem[:keep]}.{ext}"
        else:
            name = name[:MAX_FILENAME_LEN]
    return name


def sniff_mime(head: bytes) -> str | None:
    """基于 magic bytes 识别常见类型；无法识别返回 None。"""
    if not head:
        return None
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "image/gif"
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06") or head.startswith(b"PK\x07\x08"):
        return "application/zip"
    # OLE compound（旧 Office）
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword"
    # 文本粗判：可打印比例
    sample = head[:512]
    if sample and all(b < 128 and (b >= 32 or b in (9, 10, 13)) for b in sample):
        return "text/plain"
    return None


def _ooxml_kind(data: bytes) -> str | None:
    """ZIP 容器内识别 docx/xlsx/pptx。"""
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile:
        return None
    if "[Content_Types].xml" not in names:
        return "zip"
    if any(n.startswith("word/") for n in names):
        return "docx"
    if any(n.startswith("xl/") for n in names):
        return "xlsx"
    if any(n.startswith("ppt/") for n in names):
        return "pptx"
    return "zip"


def validate_zip_safety(data: bytes) -> None:
    """限制条目数、解压后体积、压缩比、路径穿越。"""
    max_entries = int(settings.FILE_ZIP_MAX_ENTRIES or 200)
    max_uncomp = int(settings.FILE_ZIP_MAX_UNCOMPRESSED_MB or 100) * 1024 * 1024
    max_ratio = int(settings.FILE_ZIP_MAX_RATIO or 100)
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > max_entries:
                raise AppException("FILE_ZIP_REJECTED", f"ZIP 条目过多（>{max_entries}）")
            total = 0
            compressed = 0
            for info in infos:
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/"):
                    raise AppException("FILE_ZIP_REJECTED", "ZIP 含路径穿越，已拒绝")
                total += max(0, int(info.file_size or 0))
                compressed += max(0, int(info.compress_size or 0))
                if total > max_uncomp:
                    raise AppException("FILE_ZIP_REJECTED", "ZIP 解压后体积超限")
            if compressed > 0 and total / compressed > max_ratio:
                raise AppException("FILE_ZIP_REJECTED", "ZIP 压缩比异常，疑似 zip bomb")
    except AppException:
        raise
    except zipfile.BadZipFile:
        raise AppException("FILE_TYPE_MISMATCH", "ZIP 内容损坏或非合法 ZIP")


def validate_content(*, filename: str, declared_content_type: str | None,
                     data: bytes, ext: str) -> tuple[str, str]:
    """
    校验扩展名、声明类型、magic 一致。
    返回 (normalized_mime, initial_status) — status 为 AVAILABLE 或 QUARANTINED。
    """
    ext = (ext or "").lower()
    if ext == "zip" and not settings.FILE_ALLOW_ZIP:
        raise AppException("FILE_TYPE_NOT_ALLOWED", "普通附件默认禁用 ZIP，请联系管理员开通")

    sniffed = sniff_mime(data[:64] if data else b"")
    declared = (declared_content_type or "").split(";")[0].strip().lower()

    # 假扩展名：exe 等 magic 已在白名单外；此处拦「声称 pdf/jpg 实为其它」
    if ext in ("pdf",) and sniffed != "application/pdf":
        raise AppException("FILE_TYPE_MISMATCH", "文件内容与扩展名不一致（期望 PDF）")
    if ext in ("png",) and sniffed != "image/png":
        raise AppException("FILE_TYPE_MISMATCH", "文件内容与扩展名不一致（期望 PNG）")
    if ext in ("jpg", "jpeg") and sniffed != "image/jpeg":
        raise AppException("FILE_TYPE_MISMATCH", "文件内容与扩展名不一致（期望 JPEG）")
    if ext in ("gif",) and sniffed != "image/gif":
        raise AppException("FILE_TYPE_MISMATCH", "文件内容与扩展名不一致（期望 GIF）")

    if ext in ("zip", "docx", "xlsx", "pptx"):
        if sniffed != "application/zip":
            raise AppException("FILE_TYPE_MISMATCH", "文件内容与扩展名不一致（期望 ZIP/OOXML）")
        validate_zip_safety(data)
        kind = _ooxml_kind(data)
        if ext == "zip" and kind not in (None, "zip"):
            # 允许 zip 内为 ooxml，仍按 zip 业务用途
            pass
        elif ext in ("docx", "xlsx", "pptx") and kind != ext:
            raise AppException("FILE_TYPE_MISMATCH", f"OOXML 容器与扩展名不一致（期望 {ext}）")

    if ext in ("txt", "csv"):
        if sniffed and sniffed not in ("text/plain",):
            # 允许 sniff 失败时的二进制误判拒绝
            if sniffed not in ("text/plain",):
                raise AppException("FILE_TYPE_MISMATCH", "文本文件内容异常")

    allowed_decl = _EXT_MIME.get(ext)
    if declared and allowed_decl and declared not in allowed_decl and declared != "application/octet-stream":
        # 客户端乱报类型：仍以 magic 为准，但拒绝明显冲突（如 image/png 报 pdf）
        if sniffed and declared.split("/")[0] != (sniffed.split("/")[0]):
            raise AppException("FILE_TYPE_MISMATCH", "声明 Content-Type 与文件内容不一致")

    mime = sniffed or (next(iter(allowed_decl)) if allowed_decl else "application/octet-stream")

    # 扫描器钩子
    scanner = get_file_scanner()
    scan_result = scanner.scan(data, filename=filename, ext=ext)
    if scan_result == "reject":
        raise AppException("FILE_REJECTED", "文件未通过安全扫描")
    if scan_result == "quarantine":
        return mime, FILE_STATUS_QUARANTINED
    # production：无真实杀毒时，Office/ZIP 等高风险不得默认 AVAILABLE
    if settings.is_prod and ext in _HIGH_RISK_EXT:
        return mime, FILE_STATUS_QUARANTINED
    return mime, FILE_STATUS_AVAILABLE


def is_downloadable_status(status: str | None) -> bool:
    s = (status or "").upper()
    if s in (FILE_STATUS_QUARANTINED, FILE_STATUS_REJECTED, FILE_STATUS_UPLOADING, FILE_STATUS_DELETED):
        return False
    return s in _LEGACY_AVAILABLE or s == FILE_STATUS_AVAILABLE


class FileScanner:
    """可替换病毒扫描接口。默认 no-op：高风险由 validate_content 置 QUARANTINED。"""

    def scan(self, data: bytes, *, filename: str, ext: str) -> str:
        """返回 allow / quarantine / reject。"""
        return "allow"


_scanner: FileScanner | None = None


def get_file_scanner() -> FileScanner:
    global _scanner
    if _scanner is None:
        _scanner = FileScanner()
    return _scanner


def set_file_scanner(scanner: FileScanner | None) -> None:
    global _scanner
    _scanner = scanner
