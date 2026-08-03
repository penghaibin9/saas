"""岗位实习 Excel 导入上传安全门。

解析型导入端点按块写入临时隔离文件，限制压缩前体积，复用公共
OOXML/ZIP 结构检查，并在文件扫描启用或生产强制时同步调用 ClamAV。
只有全部校验通过后才读取最多 10MB 的受控内容交给现有解析器。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import AppException
from app.services.clamav_client import ClamAVClient, ClamAVError, ClamAVUnavailable
from app.services.file_content_security import sanitize_filename, validate_content_path
from app.services.file_scan_config import get_file_scan_config

IMPORT_XLSX_MAX_BYTES = 10 * 1024 * 1024
IMPORT_READ_CHUNK_BYTES = 256 * 1024


async def read_safe_xlsx_upload(
    file: UploadFile,
    *,
    max_bytes: int = IMPORT_XLSX_MAX_BYTES,
) -> bytes:
    """Stream one XLSX through size, OOXML and malware gates before parsing."""
    filename = sanitize_filename(getattr(file, "filename", None))
    if Path(filename).suffix.lower() != ".xlsx":
        raise AppException("FILE_TYPE_NOT_ALLOWED", "岗位实习导入仅支持 .xlsx 文件")
    declared = str(getattr(file, "content_type", None) or "").strip() or None
    tmp_path: Path | None = None
    total = 0
    try:
        with tempfile.NamedTemporaryFile(
            prefix="internship-import-",
            suffix=".xlsx",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
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
                tmp.write(chunk)
            tmp.flush()

        if total == 0:
            raise AppException("VALIDATION_ERROR", "上传的 Excel 文件为空")

        # 公共路径校验不把整个压缩包读入内存：完成 magic、MIME、OOXML
        # 类型、条目数、解压体积、压缩比和路径穿越检查。
        validate_content_path(
            filename=filename,
            declared_content_type=declared,
            path=tmp_path,
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
            try:
                result = ClamAVClient(config).scan_path(tmp_path)
            except (ClamAVUnavailable, ClamAVError) as exc:
                raise AppException(
                    "FILE_SCAN_UNAVAILABLE",
                    "文件安全扫描暂不可用，导入未执行",
                    http_status=503,
                ) from exc
            if not result.clean:
                raise AppException(
                    "FILE_REJECTED",
                    "导入文件包含恶意内容，已拒绝",
                    http_status=422,
                )

        # 现有业务解析器仍接收 bytes，但读取发生在全部门禁通过之后，且
        # 受 max_bytes 硬上限保护，不再保留分块列表或重复内存副本。
        with tmp_path.open("rb") as stream:
            content = stream.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise AppException(
                "FILE_TOO_LARGE",
                f"岗位实习导入文件不得超过 {max_bytes // 1024 // 1024}MB",
                http_status=413,
            )
        return content
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
