"""阶段 8：COS 精确对象直传、完成核验、分区迁移与短时下载。

永久密钥仅存在后端；浏览器只获得单一 quarantine objectKey、短有效期和最小动作的临时凭证。
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.services.storage import get_backend
from app.services.storage.config import effective_config
from app.services.storage.keys import assert_exact_object_key, build_object_key, normalize_zone

_STS_SECONDS = 900
_SESSION_SECONDS = 30 * 60
_MAX_DIRECT_BYTES = 5 * 1024 * 1024 * 1024
_MULTIPART_ACTIONS = [
    "name/cos:PutObject",
    "name/cos:PostObject",
    "name/cos:InitiateMultipartUpload",
    "name/cos:ListParts",
    "name/cos:UploadPart",
    "name/cos:CompleteMultipartUpload",
    "name/cos:AbortMultipartUpload",
]


def _tenant_id() -> int:
    value = int(current_tenant_id() or 0)
    if not value:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return value


def _actor_id(user: dict | None = None) -> int | None:
    from app.services.message_identity import resolve_message_user_id

    return resolve_message_user_id(user or get_current_user_ctx() or {}) or None


def _require_cos_backend():
    backend = get_backend()
    if getattr(backend, "kind", "") != "cos":
        raise AppException("FILE_STORAGE_NOT_COS", "当前未启用腾讯云 COS，不能创建直传会话", http_status=409)
    return backend


def _credential_for_exact_key(object_key: str) -> dict[str, Any]:
    cfg = effective_config()
    try:
        from sts.sts import Sts
    except ImportError as exc:  # noqa: BLE001
        raise AppException(
            "FILE_STORAGE_MISCONFIGURED",
            "服务器缺少 qcloud-python-sts，不能签发 COS 临时凭证",
        ) from exc
    config = {
        "duration_seconds": _STS_SECONDS,
        "secret_id": cfg["cosSecretId"],
        "secret_key": cfg["cosSecretKey"],
        "bucket": cfg["cosBucket"],
        "region": cfg["cosRegion"],
        # 只能是单个精确 Key，不允许目录通配符。
        "allow_prefix": [object_key],
        "allow_actions": _MULTIPART_ACTIONS,
    }
    raw = Sts(config).get_credential()
    credentials = raw.get("credentials") or {}
    if not credentials.get("tmpSecretId") or not credentials.get("tmpSecretKey") or not credentials.get("sessionToken"):
        raise AppException("FILE_STORAGE_STS_FAILED", "腾讯云 STS 未返回完整临时凭证")
    return {
        "tmpSecretId": credentials["tmpSecretId"],
        "tmpSecretKey": credentials["tmpSecretKey"],
        "sessionToken": credentials["sessionToken"],
        "startTime": int(raw.get("startTime") or 0),
        "expiredTime": int(raw.get("expiredTime") or 0),
    }


def create_upload_session(
    *,
    filename: str,
    size_bytes: int,
    sha256: str | None,
    biz_type: str,
    biz_id: str | None,
    client_type: str,
    idempotency_key: str,
    user: dict,
) -> dict:
    from app.models.file import FileUploadSession
    from app.services.file_service import sanitize_filename, validate_ext

    backend = _require_cos_backend()
    tenant_id = _tenant_id()
    actor_id = _actor_id(user)
    name = sanitize_filename(filename or "unnamed")
    ext = validate_ext(name)
    size = int(size_bytes or 0)
    if size <= 0 or size > _MAX_DIRECT_BYTES:
        raise AppException("FILE_TOO_LARGE", "直传文件必须大于 0 且不超过 5GB")
    digest = str(sha256 or "").lower().strip()
    if digest and (len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest)):
        raise AppException("VALIDATION_ERROR", "sha256 格式不正确")
    idem = str(idempotency_key or "").strip()
    if len(idem) < 8 or len(idem) > 100:
        raise AppException("VALIDATION_ERROR", "idempotencyKey 长度必须为 8-100")

    db = get_sessionmaker()()
    try:
        existing = db.scalars(select(FileUploadSession).where(
            FileUploadSession.tenant_id == tenant_id,
            FileUploadSession.source == "COS_STS",
            FileUploadSession.is_deleted.is_(False),
        )).all()
        for row in existing:
            meta = dict(row.metadata_json or {})
            if meta.get("idempotencyKey") == idem and str(meta.get("actorId") or "") == str(actor_id or ""):
                if row.expires_at and row.expires_at > datetime.utcnow() and row.status in {"CREATED", "UPLOADING"}:
                    object_key = assert_exact_object_key(meta.get("objectKey"), zone="QUARANTINE", tenant_id=tenant_id)
                    return _session_response(row, backend, object_key, _credential_for_exact_key(object_key))
                if row.status == "COMPLETED" and row.file_id:
                    return {"sessionId": row.session_key, "status": "COMPLETED", "fileId": str(row.file_id)}

        object_key = build_object_key(zone="QUARANTINE", tenant_id=tenant_id, ext=ext)
        session_key = secrets.token_hex(24)
        row = FileUploadSession(
            tenant_id=tenant_id,
            session_key=session_key,
            status="CREATED",
            source="COS_STS",
            file_name=name,
            expected_size=size,
            received_size=0,
            expires_at=datetime.utcnow() + timedelta(seconds=_SESSION_SECONDS),
            created_by=actor_id,
            metadata_json={
                "idempotencyKey": idem,
                "actorId": str(actor_id or ""),
                "objectKey": object_key,
                "bucketName": backend.bucket_name,
                "region": backend.region,
                "ext": ext,
                "sha256": digest or None,
                "bizType": str(biz_type or "ATTACHMENT").upper(),
                "bizId": str(biz_id) if biz_id not in (None, "") else None,
                "clientType": str(client_type or "UNKNOWN").upper(),
            },
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _session_response(row, backend, object_key, _credential_for_exact_key(object_key))
    finally:
        db.close()


def _session_response(row, backend, object_key: str, credentials: dict) -> dict:
    return {
        "sessionId": row.session_key,
        "status": row.status,
        "uploadMode": "COS_STS_MULTIPART" if int(row.expected_size or 0) >= 20 * 1024 * 1024 else "COS_STS",
        "bucketName": backend.bucket_name,
        "region": backend.region,
        "objectKey": object_key,
        "credentials": credentials,
        "expiresAt": row.expires_at.isoformat(timespec="seconds") if row.expires_at else None,
        "maxSizeBytes": _MAX_DIRECT_BYTES,
    }


def get_upload_session(session_id: str, *, user: dict) -> dict:
    from app.models.file import FileUploadSession

    tenant_id = _tenant_id()
    actor_id = _actor_id(user)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileUploadSession).where(
            FileUploadSession.tenant_id == tenant_id,
            FileUploadSession.session_key == str(session_id),
            FileUploadSession.is_deleted.is_(False),
        )).first()
        if not row or str((row.metadata_json or {}).get("actorId") or "") != str(actor_id or ""):
            raise not_found("上传会话不存在")
        return {
            "sessionId": row.session_key,
            "status": row.status,
            "fileId": str(row.file_id or ""),
            "fileName": row.file_name,
            "expectedSize": int(row.expected_size or 0),
            "receivedSize": int(row.received_size or 0),
            "expiresAt": row.expires_at.isoformat(timespec="seconds") if row.expires_at else None,
        }
    finally:
        db.close()


def complete_upload_session(session_id: str, *, etag: str | None, user: dict) -> dict:
    from app.models.file import FileObject, FileUploadSession
    from app.services.file_scan_service import enqueue_file_scan

    backend = _require_cos_backend()
    tenant_id = _tenant_id()
    actor_id = _actor_id(user)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileUploadSession).where(
            FileUploadSession.tenant_id == tenant_id,
            FileUploadSession.session_key == str(session_id),
            FileUploadSession.is_deleted.is_(False),
        ).with_for_update()).first()
        meta = dict(row.metadata_json or {}) if row else {}
        if not row or str(meta.get("actorId") or "") != str(actor_id or ""):
            raise not_found("上传会话不存在")
        if row.status == "COMPLETED" and row.file_id:
            return {"sessionId": row.session_key, "status": row.status, "fileId": str(row.file_id)}
        if row.expires_at and row.expires_at <= datetime.utcnow():
            row.status = "EXPIRED"
            db.commit()
            raise AppException("DATA_CONFLICT", "上传会话已过期，请重新创建")
        object_key = assert_exact_object_key(meta.get("objectKey"), zone="QUARANTINE", tenant_id=tenant_id)
        head = backend.head_object(object_key)
        if not head:
            raise AppException("FILE_UPLOAD_INCOMPLETE", "COS 中未找到上传对象")
        actual_size = int(head.get("sizeBytes") or 0)
        if actual_size != int(row.expected_size or 0):
            raise AppException(
                "FILE_UPLOAD_SIZE_MISMATCH",
                "COS 对象大小与上传会话不一致",
                details={"expected": int(row.expected_size or 0), "actual": actual_size},
            )
        actual_etag = str(head.get("etag") or "").strip('"')
        supplied_etag = str(etag or "").strip('"')
        if supplied_etag and actual_etag and supplied_etag != actual_etag:
            raise AppException("FILE_UPLOAD_ETAG_MISMATCH", "COS 对象 ETag 与客户端完成信息不一致")

        file_obj = FileObject(
            tenant_id=tenant_id,
            file_key=object_key,
            object_key=object_key,
            bucket_name=backend.bucket_name,
            etag=actual_etag or None,
            file_name=row.file_name or "unnamed",
            ext=meta.get("ext"),
            mime_type=None,
            size_bytes=actual_size,
            sha256=meta.get("sha256"),
            biz_type=meta.get("bizType") or "ATTACHMENT",
            biz_id=meta.get("bizId"),
            owner_user_id=actor_id,
            visibility="BIZ_SCOPED",
            security_level="NORMAL",
            status="QUARANTINED",
            storage_backend="cos",
            storage_zone="QUARANTINE",
            upload_source="COS_STS",
            scan_required=True,
            scan_status="PENDING",
            scan_attempts=0,
            created_by=actor_id,
        )
        db.add(file_obj)
        db.flush()
        enqueue_file_scan(db, file_obj)
        row.file_id = file_obj.id
        row.status = "COMPLETED"
        row.received_size = actual_size
        row.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(file_obj)
        return {
            "sessionId": row.session_key,
            "status": row.status,
            "fileId": str(file_obj.id),
            "fileName": file_obj.file_name,
            "sizeBytes": actual_size,
            "scanStatus": file_obj.scan_status,
            "readyForBusiness": False,
        }
    finally:
        db.close()


def abandon_upload_session(session_id: str, *, user: dict) -> dict:
    from app.models.file import FileUploadSession

    tenant_id = _tenant_id()
    actor_id = _actor_id(user)
    backend = _require_cos_backend()
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileUploadSession).where(
            FileUploadSession.tenant_id == tenant_id,
            FileUploadSession.session_key == str(session_id),
            FileUploadSession.is_deleted.is_(False),
        ).with_for_update()).first()
        meta = dict(row.metadata_json or {}) if row else {}
        if not row or str(meta.get("actorId") or "") != str(actor_id or ""):
            raise not_found("上传会话不存在")
        if row.status == "COMPLETED":
            raise AppException("DATA_CONFLICT", "已完成的上传会话不能放弃")
        object_key = assert_exact_object_key(meta.get("objectKey"), zone="QUARANTINE", tenant_id=tenant_id)
        backend.delete(object_key)
        row.status = "ABANDONED"
        db.commit()
        return {"sessionId": row.session_key, "status": row.status}
    finally:
        db.close()


def promote_file_object(file_obj, *, target_zone: str) -> dict:
    """复制→HEAD 核验→更新元数据→删除源对象；失败时源对象保留。"""
    zone = normalize_zone(target_zone)
    backend = get_backend()
    source_key = str(getattr(file_obj, "object_key", None) or file_obj.file_key)
    target_key = build_object_key(zone=zone, tenant_id=int(file_obj.tenant_id), ext=file_obj.ext or "bin")
    if getattr(backend, "kind", "") == "cos":
        copied = backend.copy_object(source_key, target_key)
        if int(copied.get("sizeBytes") or 0) != int(file_obj.size_bytes or 0):
            backend.delete(target_key)
            raise AppException("FILE_STORAGE_VERIFY_FAILED", "COS 分区复制后大小核验失败")
        backend.delete(source_key)
        file_obj.file_key = target_key
        file_obj.object_key = target_key
        file_obj.bucket_name = backend.bucket_name
        file_obj.etag = copied.get("etag") or file_obj.etag
    else:
        source = backend.fetch_local(source_key)
        if not source or not source.exists():
            raise AppException("FILE_STORAGE_OBJECT_MISSING", "源文件不存在")
        target = backend.staging_path(target_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)
        file_obj.file_key = target_key
        file_obj.object_key = target_key
        file_obj.bucket_name = None
        file_obj.etag = None
    file_obj.storage_zone = zone
    file_obj.storage_verified_at = datetime.utcnow()
    return {"objectKey": target_key, "storageZone": zone, "etag": file_obj.etag}


def presigned_download(file_obj, *, filename: str, expires_seconds: int = 180) -> str | None:
    backend = get_backend()
    if getattr(backend, "kind", "") != "cos" or not hasattr(backend, "presigned_download_url"):
        return None
    key = str(getattr(file_obj, "object_key", None) or file_obj.file_key)
    return backend.presigned_download_url(key, filename=filename, expires_seconds=expires_seconds)


def hash_local_path(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()
