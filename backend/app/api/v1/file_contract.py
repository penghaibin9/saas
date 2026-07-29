"""公共文件 API 权威合同；正式入口与历史兼容入口均委托这里。"""
from __future__ import annotations

from fastapi import UploadFile
from fastapi.responses import FileResponse

from app.core.exceptions import AppException, not_found
from app.services import audit_log, file_service
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
        subject_type = "STUDENT" if str(user.get("userType") or "").upper() == "STUDENT" else "BUSINESS_OBJECT"
        subject_id = (
            user.get("studentId") or user.get("studentNo")
            if subject_type == "STUDENT"
            else None
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


def url_contract(file_id: str, *, user: dict) -> dict:
    meta = metadata_contract(file_id, user=user)
    if not meta.get("readyForBusiness"):
        raise not_found("文件不存在")
    return {
        "fileId": str(file_id),
        "fileName": meta.get("fileName"),
        "url": f"/api/v1/files/download/{file_id}",
        "expiresIn": 900,
        "status": meta.get("status"),
        "scanStatus": meta.get("scanStatus"),
        "statusText": meta.get("statusText"),
        "allowedActions": meta.get("allowedActions") or [],
    }


def download_contract(file_id: str, *, user: dict) -> FileResponse:
    """授权成功后直接从存储抽象解析字节，避免再落回旧硬编码权限分支。"""
    row = require_file_access(file_id, user=user, action="download")
    if isinstance(row, dict):
        resolved = file_service.resolve_download(file_id, user=user)
        if not resolved:
            raise not_found("文件不存在")
        path, filename = resolved
    else:
        from app.services.storage import get_backend

        path = get_backend().fetch_local(row.file_key)
        if not path or not path.exists():
            raise not_found("文件不存在")
        filename = row.file_name or path.name
    audit_log.record("FILE_DOWNLOAD", filename, detail={"fileId": file_id})
    response = FileResponse(str(path), filename=filename, content_disposition_type="attachment")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response
