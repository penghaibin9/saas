from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGED: list[str] = []


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        CHANGED.append(rel)


def add_import(text: str, anchor: str, line: str, label: str) -> str:
    if line in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"{label}: import anchor missing")
    return text.replace(anchor, anchor + line, 1)


def patch_router(rel: str) -> None:
    text = read(rel)
    import_line = (
        "from app.modules.internship.services.internship_import_upload import "
        "read_safe_xlsx_upload\n"
    )
    text = add_import(
        text,
        "from app.core.response import paginate, success\n",
        import_line,
        rel,
    )
    old = "    content = await file.read()\n"
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected one direct UploadFile.read, got {count}")
    text = text.replace(old, "    content = await read_safe_xlsx_upload(file)\n", 1)
    write(rel, text)


def add_helper() -> None:
    rel = "backend/app/modules/internship/services/internship_import_upload.py"
    content = '''"""岗位实习 Excel 导入上传安全门。

解析型导入端点不再一次性 ``UploadFile.read()``：按块读取、限制压缩前体积、
复用公共 OOXML/ZIP 结构检查，并在文件扫描启用或生产强制时同步调用 ClamAV。
后续异步导入任务中心仍复用同一门禁，不维护第二套文件安全规则。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import AppException
from app.services.clamav_client import ClamAVClient, ClamAVError, ClamAVUnavailable
from app.services.file_content_security import sanitize_filename, validate_content
from app.services.file_scan_config import get_file_scan_config

IMPORT_XLSX_MAX_BYTES = 10 * 1024 * 1024
IMPORT_READ_CHUNK_BYTES = 256 * 1024


async def read_safe_xlsx_upload(
    file: UploadFile,
    *,
    max_bytes: int = IMPORT_XLSX_MAX_BYTES,
) -> bytes:
    """Read one XLSX upload with size, magic, OOXML and optional malware checks."""
    filename = sanitize_filename(getattr(file, "filename", None))
    if Path(filename).suffix.lower() != ".xlsx":
        raise AppException("FILE_TYPE_NOT_ALLOWED", "岗位实习导入仅支持 .xlsx 文件")
    declared = str(getattr(file, "content_type", None) or "").strip() or None
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(IMPORT_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise AppException(
                "FILE_TOO_LARGE",
                f"岗位实习导入文件不得超过 {max_bytes // 1024 // 1024}MB",
                http_status=413,
            )
        chunks.append(chunk)
    if total == 0:
        raise AppException("VALIDATION_ERROR", "上传的 Excel 文件为空")
    content = b"".join(chunks)
    # 解析端点不持久化文件，因此先完成 magic、MIME、OOXML 类型、条目数、
    # 解压体积、压缩比与路径穿越检查；恶意内容检查在下方按环境 fail-closed。
    validate_content(
        filename=filename,
        declared_content_type=declared,
        data=content,
        ext="xlsx",
        biz_type="INTERNSHIP_IMPORT",
        source="SYSTEM",
    )
    config = get_file_scan_config()
    if config.required and not config.enabled:
        raise AppException(
            "FILE_SCAN_UNAVAILABLE",
            "生产环境文件安全扫描未启用，拒绝解析导入文件",
            http_status=503,
        )
    if config.enabled:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix="internship-import-", suffix=".xlsx", delete=False) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)
            result = ClamAVClient(config).scan_path(tmp_path)
        except (ClamAVUnavailable, ClamAVError) as exc:
            raise AppException(
                "FILE_SCAN_UNAVAILABLE",
                "文件安全扫描暂不可用，导入未执行",
                http_status=503,
            ) from exc
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
        if not result.clean:
            raise AppException(
                "FILE_REJECTED",
                "导入文件包含恶意内容，已拒绝",
                http_status=422,
            )
    return content
'''
    write(rel, content)


def add_tests() -> None:
    rel = "backend/tests/test_internship_import_upload_security.py"
    content = '''from __future__ import annotations

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
'''
    write(rel, content)


def patch_contract_checker() -> None:
    rel = "scripts/check/check-internship-production-contracts.py"
    text = read(rel)
    marker = '''positions = (ROOT / "backend/app/modules/internship/services/internship_position_service.py").read_text(encoding="utf-8")
if "请先完成正式调岗/退岗" not in positions:
    errors.append("occupied positions can still be archived")
'''
    addition = marker + '''
router_root = ROOT / "backend/app/modules/internship/routers"
for path in router_root.glob("*.py"):
    if "await file.read()" in path.read_text(encoding="utf-8"):
        errors.append(f"{path.relative_to(ROOT)}: bypasses safe import upload reader")

upload_guard = ROOT / "backend/app/modules/internship/services/internship_import_upload.py"
if not upload_guard.exists():
    errors.append("internship safe import upload guard is missing")
else:
    guard_text = upload_guard.read_text(encoding="utf-8")
    for token in ("IMPORT_XLSX_MAX_BYTES", "validate_content", "ClamAVClient"):
        if token not in guard_text:
            errors.append(f"internship import upload guard missing: {token}")
'''
    if "bypasses safe import upload reader" not in text:
        if marker not in text:
            raise RuntimeError("contract checker anchor missing")
        text = text.replace(marker, addition, 1)
    write(rel, text)


def main() -> None:
    add_helper()
    for rel in (
        "backend/app/modules/internship/routers/internship_position.py",
        "backend/app/modules/internship/routers/internship_student.py",
        "backend/app/modules/internship/routers/internship_match.py",
        "backend/app/modules/internship/routers/internship.py",
    ):
        patch_router(rel)
    add_tests()
    patch_contract_checker()
    for rel in CHANGED:
        if rel.endswith(".py"):
            ast.parse(read(rel), filename=rel)
    print("changed files:")
    for rel in CHANGED:
        print(f" - {rel}")
    if not CHANGED:
        print("import upload hardening already applied")


if __name__ == "__main__":
    main()
