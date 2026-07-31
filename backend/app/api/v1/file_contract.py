"""公共文件 API 权威合同；所有文件字节响应都收口在本模块。"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from fastapi import UploadFile
from fastapi.responses import FileResponse

from app.core.exceptions import AppException, not_found
from app.services import audit_log, file_service
from app.services import file_access_resolvers as _file_access_resolvers  # noqa: F401  注册内置 resolver
from app.services.file_access_service import (
    STATUS_TEXT,
    file_view,
    list_business_files,
    require_file_access,
    upsert_file_binding,
)


async def upload_contract(
    file: UploadFile,
    *,
    biz_type: str,
    biz_id: str | None,
    user: dict,
    visibility: str = "BIZ_SCOPED",
) -> dict:
    from app.core.token_store import rate_limit

    if not rate_limit(f"upload:{user.get('userId', '-')}", 20, 60):
        raise AppException("RATE_LIMITED", "上传过于频繁（每分钟最多 20 次），请稍后再试")
    normalized = str(biz_type or "ATTACHMENT").upper()
    if normalized == "GRADUATION_MATERIAL" and not biz_id:
        from app.modules.graduation.services.graduation_material_temp_service import cleanup_stale_temporary_materials
        cleanup_stale_temporary_materials(user, older_than_hours=24, limit=50)
    meta = await file_service.store_upload(
        file,
        normalized,
        biz_id=biz_id,
        user=user,
        visibility=visibility,
    )
    if biz_id:
        is_student = str(user.get("userType") or "").upper() == "STUDENT"
        subject_type = "STUDENT" if is_student else "USER"
        subject_id = (
            user.get("studentId") or user.get("studentNo")
            if is_student
            else user.get("userId") or user.get("id")
        )
        upsert_file_binding(
            meta["fileId"],
            biz_type=normalized,
            biz_id=str(biz_id),
            subject_type=subject_type,
            subject_id=str(subject_id) if subject_id else None,
            user=user,
        )
    scan_status = str(meta.get("scanStatus") or "NOT_REQUIRED").upper()
    result = {
        "fileId": meta["fileId"],
        "fileName": meta.get("fileName"),
        "size": meta.get("sizeBytes"),
        "sizeBytes": meta.get("sizeBytes"),
        "mimeType": meta.get("mimeType") or file.content_type,
        "hash": meta.get("sha256"),
        "sha256": meta.get("sha256"),
        "status": meta.get("status"),
        "scanRequired": meta.get("scanRequired", False),
        "scanStatus": scan_status,
        "statusText": STATUS_TEXT.get(scan_status, "状态未知"),
        "readyForBusiness": meta.get("readyForBusiness", False),
        "allowedActions": ["viewMetadata"] + (["preview", "download"] if meta.get("readyForBusiness") else []),
        "temporary": normalized == "GRADUATION_MATERIAL" and not biz_id,
    }
    audit_log.record(
        "FILE_UPLOAD",
        f"file:{result['fileId']}",
        {"fileName": result.get("fileName"), "size": result.get("sizeBytes")},
    )
    return result


def metadata_contract(file_id: str, *, user: dict) -> dict:
    row = require_file_access(file_id, user=user, action="meta")
    if isinstance(row, dict):
        scan_status = str(row.get("scanStatus") or "NOT_REQUIRED").upper()
        return {
            **row,
            "statusText": STATUS_TEXT.get(scan_status, "状态未知"),
            "allowedActions": ["viewMetadata"] + (["preview", "download"] if row.get("readyForBusiness") else []),
        }
    from app.db.session import get_sessionmaker
    from app.models.file import FileBinding
    from sqlalchemy import select

    db = get_sessionmaker()()
    try:
        bindings = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == row.tenant_id,
            FileBinding.file_id == row.id,
            FileBinding.is_deleted.is_(False),
        )).all()
        return file_view(row, user=user, bindings=list(bindings), db=db)
    finally:
        db.close()


def list_contract(biz_type: str, biz_id: str, *, user: dict) -> list[dict]:
    return list_business_files(biz_type, biz_id, user=user)


def _requires_audited_business_download(biz_type: str | None) -> bool:
    """强敏感或业务专用材料必须走代理/业务下载接口，不能发可转发直链。"""
    return str(biz_type or "").upper() == "GRADUATION_MATERIAL"


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
    """为已经通过业务授权、范围和安全门的本地对象构建唯一字节响应。

    调用方只能传入业务服务或一次性票据解析出的路径；本函数再次检查路径存在，
    统一 no-store/nosniff、审计和 Content-Disposition。生产代码不得在其他模块
    直接实例化 ``FileResponse``，避免绕过文件中心的响应治理。
    """
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
        detail={"fileName": filename, "delivery": "LOCAL_PROXY", **dict(audit_detail or {})},
    )
    return FileResponse(
        str(resolved),
        filename=filename,
        media_type=media_type,
        content_disposition_type="inline" if inline else "attachment",
        headers=safe_headers,
    )


def url_contract(file_id: str, *, user: dict) -> dict:
    row = require_file_access(file_id, user=user, action="download")
    if isinstance(row, dict):
        meta = metadata_contract(file_id, user=user)
        if not meta.get("readyForBusiness") or _requires_audited_business_download(meta.get("bizType")):
            raise not_found("文件不存在")
        return {
            "fileId": str(file_id),
            "fileName": meta.get("fileName"),
            "url": f"/api/v1/files/download/{file_id}",
            "expiresIn": 180,
            "delivery": "LOCAL_PROXY",
            "status": meta.get("status"),
            "scanStatus": meta.get("scanStatus"),
            "statusText": meta.get("statusText"),
            "allowedActions": meta.get("allowedActions") or [],
        }
    if _requires_audited_business_download(row.biz_type) or str(row.security_level or "").upper() in {"HIGHLY_SENSITIVE", "LEGAL_HOLD"}:
        raise not_found("文件不存在")
    from app.services.storage.production import presigned_download

    url = presigned_download(row, filename=row.file_name or "download", expires_seconds=180)
    meta = metadata_contract(file_id, user=user)
    return {
        "fileId": str(file_id),
        "fileName": row.file_name,
        "url": url or f"/api/v1/files/download/{file_id}",
        "expiresIn": 180,
        "delivery": "COS_PRESIGNED" if url else "LOCAL_PROXY",
        "status": row.status,
        "scanStatus": row.scan_status,
        "statusText": meta.get("statusText"),
        "allowedActions": meta.get("allowedActions") or [],
    }


def download_contract(file_id: str, *, user: dict) -> FileResponse:
    """兼容代理下载；普通 COS 客户端应先请求 /{fileId}/url 获取短时预签名。"""
    row = require_file_access(file_id, user=user, action="download")
    if isinstance(row, dict):
        if _requires_audited_business_download(row.get("bizType")):
            raise not_found("文件不存在")
        resolved = file_service.resolve_download(file_id, user=user)
        if not resolved:
            raise not_found("文件不存在")
        path, filename = resolved
    else:
        if _requires_audited_business_download(row.biz_type):
            raise not_found("文件不存在")
        from app.services.storage import get_backend

        key = str(getattr(row, "object_key", None) or row.file_key)
        path = get_backend().fetch_local(key)
        if not path or not path.exists():
            raise not_found("文件不存在")
        filename = row.file_name or path.name
    return validated_local_file_response(
        path,
        filename=filename,
        audit_action="FILE_DOWNLOAD",
        audit_target=filename,
        audit_detail={"fileId": file_id},
    )
