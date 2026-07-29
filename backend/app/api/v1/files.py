"""文件中心正式契约：POST /files 上传，GET /files/{fileId}/url 获取安全下载路径。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.exceptions import AppException, not_found
from app.core.response import success
from app.core.security import get_current_user
from app.services import audit_log, file_service

router = APIRouter(prefix="/files", tags=["10·文件中心"])


@router.post("", summary="上传文件（流式落盘 + 隔离扫描 + 对象级归属）")
async def upload_file(file: UploadFile = File(...), bizType: str = Form("ATTACHMENT"),
                      bizId: str | None = Form(None), user=Depends(get_current_user)):
    from app.core.token_store import rate_limit
    if not rate_limit(f"upload:{user.get('userId', '-')}", 20, 60):
        raise AppException("RATE_LIMITED", "上传过于频繁（每分钟最多 20 次），请稍后再试")
    normalized = (bizType or "ATTACHMENT").upper()
    if normalized == "GRADUATION_MATERIAL" and not bizId:
        from app.modules.graduation.services.graduation_material_temp_service import cleanup_stale_temporary_materials
        cleanup_stale_temporary_materials(user, older_than_hours=24, limit=50)
    meta = await file_service.store_upload(file, normalized, biz_id=bizId, user=user, visibility="BIZ_SCOPED")
    audit_log.record("FILE_UPLOAD", f"file:{meta['fileId']}", {"fileName": meta.get("fileName"), "size": meta.get("sizeBytes")})
    return success({
        "fileId": meta["fileId"], "fileName": meta.get("fileName"),
        "size": meta.get("sizeBytes"), "mimeType": meta.get("mimeType") or file.content_type,
        "hash": meta.get("sha256"), "status": meta.get("status"),
        "scanRequired": meta.get("scanRequired", False), "scanStatus": meta.get("scanStatus"),
        "readyForBusiness": meta.get("readyForBusiness", False),
        "temporary": normalized == "GRADUATION_MATERIAL" and not bizId,
    })


@router.get("/{file_id}/url", summary="获取预览/下载 URL（仅安全可用文件）")
def file_url(file_id: str, user=Depends(get_current_user)):
    meta = file_service.get_file_meta(file_id, user=user, require_ready=True)
    if not meta:
        raise not_found("文件不存在或无权访问")
    return success({"fileId": file_id, "fileName": meta.get("fileName"),
                    "url": f"/api/v1/files/download/{file_id}", "expiresIn": 900})
