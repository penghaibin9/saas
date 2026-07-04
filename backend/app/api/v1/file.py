"""
简化文件上传占位（P0 基线，POST /api/v1/files/upload-placeholder）
────────────────────────────────────────────────────────────
与 app/api/v1/files.py（POST /api/v1/files，正式两步契约 §十）并存：
本文件提供最小占位接口，便于 P0 基线联调与测试。不落盘、不接对象存储，
仅计算 sha256/大小并登记内存元数据，与 files.py 内部实现方式一致。
"""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.exceptions import AppException
from app.core.response import success
from app.core.security import get_current_user
from app.services import audit_log

router = APIRouter(tags=["S9·简化-文件上传"])

MAX_SIZE = 50 * 1024 * 1024
ALLOWED_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
               "png", "jpg", "jpeg", "gif", "zip", "txt", "csv"}


@router.post("/upload-placeholder", summary="文件上传占位（简化）")
async def upload_placeholder(file: UploadFile = File(...), user=Depends(get_current_user)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED_EXT:
        raise AppException("FILE_TYPE_NOT_ALLOWED", f"文件类型不允许：.{ext or '未知'}",
                           details={"allowed": sorted(ALLOWED_EXT)})

    sha, size = hashlib.sha256(), 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_SIZE:
            raise AppException("FILE_TOO_LARGE", "文件超过 50MB 上限")
        sha.update(chunk)

    file_id = f"file-{uuid.uuid4().hex[:20]}"
    meta = {"fileId": file_id, "fileName": file.filename, "size": size,
            "mimeType": file.content_type, "hash": sha.hexdigest()}
    audit_log.record("FILE_UPLOAD", f"file:{file_id}", {"fileName": file.filename, "size": size})
    return success(meta)
