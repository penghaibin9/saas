"""Standalone 文件字节响应合同。

W2-A 只暴露已经经过业务服务/一次性票据授权后的本地字节响应。
上传、元数据、通用文件浏览在后续学生/企业端接活时再按实际调用扩展，
避免把原 SaaS 完整文件中心和商业控制面拖入 Standalone。
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from fastapi.responses import FileResponse

from app.core.exceptions import not_found
from app.services import audit_log


def validated_local_file_response(
    path,
    *,
    filename: str,
    audit_action: str,
    audit_target: str,
    inline: bool = False,
    media_type: str | None = None,
    headers: Mapping[str, str] | None = None,
    audit_detail: dict | None = None,
) -> FileResponse:
    resolved = Path(path) if path is not None else None
    if not resolved or not resolved.is_file():
        raise not_found("文件不存在")
    safe_headers = {
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
        **dict(headers or {}),
    }
    audit_log.record(
        str(audit_action or "FILE_DOWNLOAD"),
        str(audit_target or filename),
        detail={
            "fileName": filename,
            "delivery": "LOCAL_PROXY",
            **dict(audit_detail or {}),
        },
    )
    return FileResponse(
        str(resolved),
        filename=filename,
        media_type=media_type,
        content_disposition_type="inline" if inline else "attachment",
        headers=safe_headers,
    )
