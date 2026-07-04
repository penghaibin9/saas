"""
文件中心（占位实现，对齐冻结契约 §十）
────────────────────────────────────────────────────────────
两步契约：POST /files 上传 → 返回 fileId；业务只提交 fileId。
本阶段不落盘、不接对象存储：读流计算大小与 sha256，元数据存内存注册表。
接 MinIO/OSS 时仅替换本文件内部实现，契约字段不变。
"""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.exceptions import AppException, not_found
from app.core.response import success
from app.core.security import get_current_user
from app.services import audit_log

router = APIRouter(prefix="/files", tags=["10·文件中心（占位）"])

MAX_SIZE = 50 * 1024 * 1024  # 契约 §十：默认单文件 ≤50MB
ALLOWED_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
               "png", "jpg", "jpeg", "gif", "zip", "txt", "csv"}

# 内存文件注册表：fileId → 元数据（接对象存储后替换为 t_file_object）
_REGISTRY: dict[str, dict] = {}


@router.post("", summary="上传文件（占位：不落盘，只登记元数据）")
async def upload_file(file: UploadFile = File(...), user=Depends(get_current_user)):
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
    _REGISTRY[file_id] = meta
    audit_log.record("FILE_UPLOAD", f"file:{file_id}",
                     {"fileName": file.filename, "size": size})
    return success(meta)


@router.get("/{file_id}/url", summary="获取预览/下载签名 URL（占位）")
def file_url(file_id: str, user=Depends(get_current_user)):
    meta = _REGISTRY.get(file_id)
    if not meta:
        raise not_found("文件不存在或已过期")
    # 占位签名 URL；接对象存储后返回真实短期签名地址
    return success({"fileId": file_id, "fileName": meta["fileName"],
                    "url": f"/mock-storage/{file_id}?sign=placeholder&expires=900",
                    "expiresIn": 900})
