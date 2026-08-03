"""岗位实习 Excel 导入上传安全门。

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
