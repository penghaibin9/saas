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


# ── P4 · 真实上传（本地 UPLOAD_DIR 落盘 + t_file_object 登记）──
from fastapi import File, UploadFile  # noqa: E402

from app.services import file_service  # noqa: E402


@router.post("/upload", summary="上传文件（真实：白名单校验 + sha256 + 落盘 + t_file_object 登记 + 审计）")
async def upload_real(file: UploadFile = File(...), bizType: str = "ATTACHMENT",
                      user=Depends(get_current_user)):
    from app.core.exceptions import AppException
    from app.core.token_store import rate_limit
    if not rate_limit(f"upload:{user.get('userId', '-')}", 20, 60):
        raise AppException("RATE_LIMITED", "上传过于频繁（每分钟最多 20 次），请稍后再试")
    meta = await file_service.store_upload(file, bizType)
    audit_log.record("FILE_UPLOAD", meta["fileName"],
                     detail={"fileId": meta["fileId"], "size": meta["sizeBytes"], "sha256": meta["sha256"][:16]})
    return success(meta, message="上传成功")


@router.get("/meta/{file_id}", summary="文件元数据")
def file_meta(file_id: str, user=Depends(get_current_user)):
    meta = file_service.get_file_meta(file_id)
    if not meta:
        from app.core.exceptions import not_found
        raise not_found("文件不存在")
    return success(meta)
