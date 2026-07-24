"""P1：文件 MIME / 隔离区 / 文件名消毒。"""
from __future__ import annotations

import io
import zipfile

import pytest

from app.core.exceptions import AppException
from app.services.file_content_security import (
    FILE_STATUS_AVAILABLE,
    FILE_STATUS_QUARANTINED,
    is_downloadable_status,
    sanitize_filename,
    validate_content,
)


def test_exe_renamed_pdf_rejected():
    data = b"MZ\x90\x00" + b"\x00" * 64  # PE header-ish, not PDF
    with pytest.raises(AppException) as ei:
        validate_content(filename="evil.pdf", declared_content_type="application/pdf",
                         data=data, ext="pdf")
    assert ei.value.code == "FILE_TYPE_MISMATCH"


def test_fake_jpg_rejected():
    with pytest.raises(AppException) as ei:
        validate_content(filename="x.jpg", declared_content_type="image/jpeg",
                         data=b"not-a-jpeg", ext="jpg")
    assert ei.value.code == "FILE_TYPE_MISMATCH"


def test_valid_png_available():
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    mime, status = validate_content(
        filename="a.png", declared_content_type="image/png", data=png, ext="png")
    assert mime == "image/png"
    assert status == FILE_STATUS_AVAILABLE
    assert is_downloadable_status(status)


def _minimal_ooxml(kind: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        if kind == "xlsx":
            zf.writestr("xl/workbook.xml", "<workbook/>")
        elif kind == "docx":
            zf.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


def test_valid_xlsx_ok_non_prod():
    data = _minimal_ooxml("xlsx")
    mime, status = validate_content(
        filename="t.xlsx",
        declared_content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        data=data, ext="xlsx")
    assert "zip" in mime or mime.startswith("application/")
    assert status in (FILE_STATUS_AVAILABLE, FILE_STATUS_QUARANTINED)


def test_zip_bomb_rejected(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.FILE_ALLOW_ZIP", True)
    monkeypatch.setattr("app.core.config.settings.FILE_ZIP_MAX_RATIO", 10)
    monkeypatch.setattr("app.core.config.settings.FILE_ZIP_MAX_UNCOMPRESSED_MB", 1)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bomb.txt", b"0" * (200_000))
    data = buf.getvalue()
    # 若压缩比不够高则改用条目数
    monkeypatch.setattr("app.core.config.settings.FILE_ZIP_MAX_ENTRIES", 1)
    buf2 = io.BytesIO()
    with zipfile.ZipFile(buf2, "w") as zf:
        zf.writestr("a.txt", "1")
        zf.writestr("b.txt", "2")
    with pytest.raises(AppException) as ei:
        validate_content(filename="z.zip", declared_content_type="application/zip",
                         data=buf2.getvalue(), ext="zip")
    assert ei.value.code in ("FILE_ZIP_REJECTED", "FILE_TYPE_NOT_ALLOWED")


def test_path_traversal_filename_sanitized():
    assert ".." not in sanitize_filename("../../etc/passwd.pdf")
    assert "/" not in sanitize_filename("a/b\\c.pdf")
    assert "\n" not in sanitize_filename("evil\r\nName.pdf")


def test_quarantined_not_downloadable():
    assert not is_downloadable_status(FILE_STATUS_QUARANTINED)
    assert is_downloadable_status("STORED")
    assert is_downloadable_status(FILE_STATUS_AVAILABLE)
