"""上传内容安全：文件名、MIME/magic、OOXML/ZIP 结构与异步扫描判定。"""
from __future__ import annotations

import re
import zipfile
from io import BytesIO
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import AppException

FILE_STATUS_UPLOADING = "UPLOADING"
FILE_STATUS_QUARANTINED = "QUARANTINED"
FILE_STATUS_AVAILABLE = "AVAILABLE"
FILE_STATUS_REJECTED = "REJECTED"
FILE_STATUS_DELETED = "DELETED"
# 历史文件对象曾使用 STORED / CONFIRMED 表示已落盘、已确认可用；只在扫描状态安全时兼容。
_LEGACY_AVAILABLE = frozenset({"STORED", "CONFIRMED", "AVAILABLE", ""})
MAX_FILENAME_LEN = 180

_EXT_MIME: dict[str, set[str]] = {
    "pdf": {"application/pdf"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "gif": {"image/gif"},
    "txt": {"text/plain", "text/csv", "application/octet-stream"},
    "csv": {"text/csv", "text/plain", "application/vnd.ms-excel", "application/octet-stream"},
    "zip": {"application/zip", "application/x-zip-compressed", "application/octet-stream"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip", "application/octet-stream"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip", "application/octet-stream"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/zip", "application/octet-stream"},
    "doc": {"application/msword", "application/octet-stream"},
    "xls": {"application/vnd.ms-excel", "application/octet-stream"},
    "ppt": {"application/vnd.ms-powerpoint", "application/octet-stream"},
}

_SCAN_REQUIRED_EXT = frozenset({"zip", "docx", "xlsx", "pptx", "doc", "xls", "ppt", "txt", "csv"})
_SYSTEM_ZIP_BIZ = frozenset({"COMPLIANCE_EVIDENCE", "ARCHIVE_PACKAGE", "GRADUATION_MATERIAL", "INTERNSHIP"})


def sanitize_filename(filename: str | None) -> str:
    name = (filename or "unnamed").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).replace("\r", "").replace("\n", "")
    name = name.strip().strip(".") or "unnamed"
    if len(name) > MAX_FILENAME_LEN:
        stem, sep, ext = name.rpartition(".")
        name = f"{stem[:MAX_FILENAME_LEN-len(ext)-1]}.{ext}" if sep and len(ext) <= 20 else name[:MAX_FILENAME_LEN]
    return name


def sniff_mime(head: bytes) -> str | None:
    if not head:
        return None
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "application/zip"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword"
    sample = head[:512]
    if sample and all(b < 128 and (b >= 32 or b in (9, 10, 13)) for b in sample):
        return "text/plain"
    return None


def is_scan_required_for_upload(ext: str | None) -> bool:
    """生产/显式启用扫描时，高风险扩展必须进入隔离队列。

    非生产且未配置 ClamAV 时保留历史兼容，避免测试和本地开发把所有 Office 文件永久卡住；
    生产环境由 file_scan_config.required 强制 fail-closed。
    """
    if (ext or "").lower() not in _SCAN_REQUIRED_EXT:
        return False
    from app.services.file_scan_config import get_file_scan_config
    config = get_file_scan_config()
    return bool(config.required or config.enabled)


def _zip_limits() -> tuple[int, int, int]:
    entries = int(getattr(settings, "FILE_ZIP_MAX_ENTRIES", 200) or 200)
    uncompressed = int(getattr(settings, "FILE_ZIP_MAX_UNCOMPRESSED_MB", 100) or 100) * 1024 * 1024
    ratio = int(getattr(settings, "FILE_ZIP_MAX_RATIO", 100) or 100)
    return entries, uncompressed, ratio


def _validate_zip_info(zf: zipfile.ZipFile) -> None:
    max_entries, max_uncompressed, max_ratio = _zip_limits()
    infos = zf.infolist()
    if len(infos) > max_entries:
        raise AppException("FILE_ZIP_REJECTED", f"ZIP 条目过多（>{max_entries}）")
    total = compressed = 0
    for info in infos:
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/"):
            raise AppException("FILE_ZIP_REJECTED", "ZIP 含路径穿越，已拒绝")
        total += max(0, int(info.file_size or 0))
        compressed += max(0, int(info.compress_size or 0))
        if total > max_uncompressed:
            raise AppException("FILE_ZIP_REJECTED", "ZIP 解压后体积超限")
    if compressed > 0 and total / compressed > max_ratio:
        raise AppException("FILE_ZIP_REJECTED", "ZIP 压缩比异常，疑似 zip bomb")


def validate_zip_safety(data: bytes) -> None:
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            _validate_zip_info(zf)
    except AppException:
        raise
    except zipfile.BadZipFile as exc:
        raise AppException("FILE_TYPE_MISMATCH", "ZIP 内容损坏或非合法 ZIP") from exc


def validate_zip_safety_path(path: str | Path) -> None:
    try:
        with zipfile.ZipFile(Path(path)) as zf:
            _validate_zip_info(zf)
    except AppException:
        raise
    except zipfile.BadZipFile as exc:
        raise AppException("FILE_TYPE_MISMATCH", "ZIP 内容损坏或非合法 ZIP") from exc


def _ooxml_kind_from_names(names: set[str]) -> str:
    if "[Content_Types].xml" not in names:
        return "zip"
    if any(name.startswith("word/") for name in names):
        return "docx"
    if any(name.startswith("xl/") for name in names):
        return "xlsx"
    if any(name.startswith("ppt/") for name in names):
        return "pptx"
    return "zip"


def _ooxml_kind(data: bytes) -> str | None:
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            return _ooxml_kind_from_names(set(zf.namelist()))
    except zipfile.BadZipFile:
        return None


def _ooxml_kind_path(path: str | Path) -> str | None:
    try:
        with zipfile.ZipFile(Path(path)) as zf:
            return _ooxml_kind_from_names(set(zf.namelist()))
    except zipfile.BadZipFile:
        return None


def _validate_common(*, ext: str, declared_content_type: str | None, sniffed: str | None,
                     zip_kind: str | None, biz_type: str | None, source: str) -> str:
    ext = (ext or "").lower()
    biz = (biz_type or "").upper()
    if ext == "zip" and source == "USER" and not settings.FILE_ALLOW_ZIP and biz not in _SYSTEM_ZIP_BIZ:
        raise AppException("FILE_TYPE_NOT_ALLOWED", "普通附件默认禁用 ZIP，请联系管理员开通")
    expected = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif"}
    if ext in expected and sniffed != expected[ext]:
        raise AppException("FILE_TYPE_MISMATCH", f"文件内容与扩展名不一致（期望 {ext.upper()}）")
    if ext in {"zip", "docx", "xlsx", "pptx"}:
        if sniffed != "application/zip":
            raise AppException("FILE_TYPE_MISMATCH", "文件内容与扩展名不一致（期望 ZIP/OOXML）")
        if ext in {"docx", "xlsx", "pptx"} and zip_kind != ext:
            raise AppException("FILE_TYPE_MISMATCH", f"OOXML 容器与扩展名不一致（期望 {ext}）")
    if ext in {"txt", "csv"} and sniffed and sniffed != "text/plain":
        raise AppException("FILE_TYPE_MISMATCH", "文本文件内容异常")
    declared = (declared_content_type or "").split(";", 1)[0].strip().lower()
    allowed = _EXT_MIME.get(ext)
    if declared and allowed and declared not in allowed and declared != "application/octet-stream":
        if sniffed and declared.split("/", 1)[0] != sniffed.split("/", 1)[0]:
            raise AppException("FILE_TYPE_MISMATCH", "声明 Content-Type 与文件内容不一致")
    return sniffed or (next(iter(allowed)) if allowed else "application/octet-stream")


def validate_content(*, filename: str, declared_content_type: str | None, data: bytes,
                     ext: str, biz_type: str | None = None, source: str = "SYSTEM") -> tuple[str, str]:
    sniffed = sniff_mime(data[:512])
    kind = None
    if ext in {"zip", "docx", "xlsx", "pptx"}:
        validate_zip_safety(data)
        kind = _ooxml_kind(data)
    mime = _validate_common(ext=ext, declared_content_type=declared_content_type, sniffed=sniffed,
                            zip_kind=kind, biz_type=biz_type, source=source)
    status = FILE_STATUS_QUARANTINED if source == "USER" and is_scan_required_for_upload(ext) else FILE_STATUS_AVAILABLE
    return mime, status


def validate_content_path(*, filename: str, declared_content_type: str | None, path: str | Path,
                          ext: str, biz_type: str | None = None, source: str = "USER") -> tuple[str, str]:
    file_path = Path(path)
    with file_path.open("rb") as stream:
        head = stream.read(512)
    sniffed = sniff_mime(head)
    kind = None
    if ext in {"zip", "docx", "xlsx", "pptx"}:
        validate_zip_safety_path(file_path)
        kind = _ooxml_kind_path(file_path)
    mime = _validate_common(ext=ext, declared_content_type=declared_content_type, sniffed=sniffed,
                            zip_kind=kind, biz_type=biz_type, source=source)
    status = FILE_STATUS_QUARANTINED if source == "USER" and is_scan_required_for_upload(ext) else FILE_STATUS_AVAILABLE
    return mime, status


def is_downloadable_status(status: str | None) -> bool:
    value = (status or "").upper()
    if value in {FILE_STATUS_QUARANTINED, FILE_STATUS_REJECTED, FILE_STATUS_UPLOADING, FILE_STATUS_DELETED}:
        return False
    return value in _LEGACY_AVAILABLE or value == FILE_STATUS_AVAILABLE
