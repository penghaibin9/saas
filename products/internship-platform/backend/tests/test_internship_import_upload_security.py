from __future__ import annotations

import io
import zipfile

import pytest
from fastapi import UploadFile

from app.core.exceptions import AppException
from app.modules.internship.services.internship_import_upload import (
    IMPORT_XLSX_MAX_BYTES,
    read_safe_xlsx_upload,
)


def _xlsx_bytes() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types />")
        zf.writestr("xl/workbook.xml", "<workbook />")
    return stream.getvalue()


@pytest.mark.anyio
async def test_safe_import_rejects_wrong_extension():
    upload = UploadFile(filename="students.xls", file=io.BytesIO(_xlsx_bytes()))
    with pytest.raises(AppException) as exc:
        await read_safe_xlsx_upload(upload)
    assert exc.value.code == "FILE_TYPE_NOT_ALLOWED"


@pytest.mark.anyio
async def test_safe_import_rejects_oversize_before_parser():
    upload = UploadFile(
        filename="students.xlsx",
        file=io.BytesIO(b"x" * (IMPORT_XLSX_MAX_BYTES + 1)),
    )
    with pytest.raises(AppException) as exc:
        await read_safe_xlsx_upload(upload)
    assert exc.value.code == "FILE_TOO_LARGE"


@pytest.mark.anyio
async def test_safe_import_accepts_structurally_valid_xlsx(monkeypatch):
    class Config:
        required = False
        enabled = False

    monkeypatch.setattr(
        "app.modules.internship.services.internship_import_upload.get_file_scan_config",
        lambda: Config(),
    )
    content = _xlsx_bytes()
    upload = UploadFile(filename="students.xlsx", file=io.BytesIO(content))
    assert await read_safe_xlsx_upload(upload) == content


def test_no_internship_router_reads_upload_whole_file_directly():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "backend/app/modules/internship/routers"
    offenders = []
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "await file.read()" in text:
            offenders.append(path.name)
    assert offenders == []
