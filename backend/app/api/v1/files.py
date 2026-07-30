"""公共文件中心正式 API；历史 /files/upload 仅作为兼容别名。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.api.v1.file_contract import (
    download_contract,
    list_contract,
    metadata_contract,
    upload_contract,
    url_contract,
)
from app.core.response import success
from app.core.security import get_current_user
from app.services.file_version_service import file_version_timeline as build_file_version_timeline

router = APIRouter(prefix="/files", tags=["10·文件中心"])


@router.post("", summary="上传文件（权威入口）")
async def upload_file(
    file: UploadFile = File(...),
    bizType: str = Form("ATTACHMENT"),
    bizId: str | None = Form(None),
    user=Depends(get_current_user),
):
    data = await upload_contract(
        file,
        biz_type=bizType,
        biz_id=bizId,
        user=user,
        visibility="BIZ_SCOPED",
    )
    return success(data, message="上传成功；高风险文件需等待安全扫描")


@router.get("", summary="按业务对象列出安全文件")
def list_files(
    bizType: str = Query(..., min_length=1),
    bizId: str = Query(..., min_length=1),
    user=Depends(get_current_user),
):
    return success({"items": list_contract(bizType, bizId, user=user)})


@router.get("/download/{file_id}", summary="下载文件（权威授权与审计入口）")
def download_file(file_id: str, user=Depends(get_current_user)):
    return download_contract(file_id, user=user)


@router.get("/{file_id}", summary="文件元数据、状态和允许动作")
def file_metadata(file_id: str, user=Depends(get_current_user)):
    return success(metadata_contract(file_id, user=user))


@router.get("/{file_id}/versions", summary="文件业务版本时间线")
def file_version_timeline(file_id: str, user=Depends(get_current_user)):
    return success({"items": build_file_version_timeline(file_id, user=user)})


@router.get("/{file_id}/url", summary="获取预览/下载 URL（仅安全可用文件）")
def file_url(file_id: str, user=Depends(get_current_user)):
    return success(url_contract(file_id, user=user))
