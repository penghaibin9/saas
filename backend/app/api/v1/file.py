"""
文件上传真实契约：POST /api/v1/files/upload、meta、download。
占位 upload-placeholder 仅挂在 placeholder_router，由 router 在非生产环境条件注册。
"""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.core.response import success
from app.core.security import get_current_user
from app.services import audit_log, file_service

router = APIRouter(tags=["S9·文件上传"])
placeholder_router = APIRouter(tags=["S9·文件上传占位（非生产）"])

MAX_SIZE = 50 * 1024 * 1024
ALLOWED_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
               "png", "jpg", "jpeg", "gif", "zip", "txt", "csv"}


@placeholder_router.post("/upload-placeholder", summary="文件上传占位（仅非生产；不落盘）")
async def upload_placeholder(file: UploadFile = File(...), user=Depends(get_current_user)):
    if settings.is_prod:
        raise not_found("接口不存在")
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
            "mimeType": file.content_type, "hash": sha.hexdigest(),
            "notice": "非生产占位：未落盘；请改用 POST /api/v1/files/upload"}
    audit_log.record("FILE_UPLOAD", f"file:{file_id}", {"fileName": file.filename, "size": size,
                                                        "placeholder": True})
    return success(meta)


@router.post("/upload", summary="上传文件（真实：白名单 + sha256 + 落盘 + t_file_object + 审计）")
async def upload_real(file: UploadFile = File(...),
                      bizType: str = Form("ATTACHMENT"),
                      bizId: str | None = Form(None),
                      user=Depends(get_current_user)):
    from app.core.token_store import rate_limit
    if not rate_limit(f"upload:{user.get('userId', '-')}", 20, 60):
        raise AppException("RATE_LIMITED", "上传过于频繁（每分钟最多 20 次），请稍后再试")
    meta = await file_service.store_upload(file, bizType, biz_id=bizId, user=user)
    audit_log.record("FILE_UPLOAD", meta["fileName"],
                     detail={"fileId": meta["fileId"], "size": meta["sizeBytes"],
                             "sha256": (meta.get("sha256") or "")[:16]})
    return success(meta, message="上传成功")


@router.get("/meta/{file_id}", summary="文件元数据（对象级授权）")
def file_meta(file_id: str, user=Depends(get_current_user)):
    meta = file_service.get_file_meta(file_id, user=user)
    if not meta:
        raise not_found("文件不存在或无权访问")
    return success(meta)


@router.get("/download/{file_id}", summary="下载附件（租户 + 对象级授权 + 审计）")
def download_file(file_id: str, user=Depends(get_current_user)):
    from fastapi.responses import FileResponse

    resolved = file_service.resolve_download(file_id, user=user)
    if not resolved:
        raise not_found("文件不存在或无权访问")
    path, filename = resolved
    audit_log.record("FILE_DOWNLOAD", filename, detail={"fileId": file_id})
    return FileResponse(str(path), filename=filename)
