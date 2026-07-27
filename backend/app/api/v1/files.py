"""
文件中心正式契约（对齐冻结契约 §十）
两步：POST /files 上传 → 返回 fileId；GET /files/{fileId}/url 返回真实下载路径。
禁止内存假登记与 /mock-storage 假签名 URL。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.exceptions import not_found
from app.core.response import success
from app.core.security import get_current_user
from app.services import audit_log, file_service

router = APIRouter(prefix="/files", tags=["10·文件中心"])


@router.post("", summary="上传文件（真实落盘 + t_file_object + 对象级归属）")
async def upload_file(file: UploadFile = File(...),
                      bizType: str = Form("ATTACHMENT"),
                      bizId: str | None = Form(None),
                      user=Depends(get_current_user)):
    from app.core.exceptions import AppException
    from app.core.token_store import rate_limit
    if not rate_limit(f"upload:{user.get('userId', '-')}", 20, 60):
        raise AppException("RATE_LIMITED", "上传过于频繁（每分钟最多 20 次），请稍后再试")
    meta = await file_service.store_upload(file, bizType, biz_id=bizId, user=user,
                                           visibility="BIZ_SCOPED")
    audit_log.record("FILE_UPLOAD", f"file:{meta['fileId']}",
                     {"fileName": meta.get("fileName"), "size": meta.get("sizeBytes")})
    return success({
        "fileId": meta["fileId"], "fileName": meta.get("fileName"),
        "size": meta.get("sizeBytes"), "mimeType": file.content_type,
        "hash": meta.get("sha256"),
    })


@router.get("/{file_id}/url", summary="获取预览/下载 URL（真实路径，需对象级授权）")
def file_url(file_id: str, user=Depends(get_current_user)):
    meta = file_service.get_file_meta(file_id, user=user)
    if not meta:
        raise not_found("文件不存在或无权访问")
    # 兼容契约字段：返回同域真实下载接口，不再签发 mock-storage
    return success({
        "fileId": file_id, "fileName": meta.get("fileName"),
        "url": f"/api/v1/files/download/{file_id}",
        "expiresIn": 900,
    })
