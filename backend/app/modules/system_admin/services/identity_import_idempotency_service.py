"""I1 request idempotency for identity-import uploads on existing schema.

FileUploadSession is the durable request-id anchor. It is reserved before
FileObject storage, survives ImportJob adapter transitions, and can recover the
small crash window between FileObject commit and reservation binding.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.data_exchange import ImportJob
from app.models.file import FileObject, FileUploadSession
from app.services import data_exchange_job_service as jobs

_SOURCE = "IDENTITY_IMPORT"
_STALE_SECONDS = 30 * 60


def _kind(value: str) -> str:
    normalized = str(value or "").upper()
    if normalized not in {"STUDENT", "TEACHER"}:
        raise AppException("VALIDATION_ERROR", "身份导入类型仅支持 STUDENT 或 TEACHER")
    return normalized


def _session_identity(idempotency_key: str) -> tuple[str, str]:
    raw = str(idempotency_key or "").strip()
    if len(raw) < 16 or len(raw) > 200:
        raise AppException("VALIDATION_ERROR", "Idempotency-Key 长度必须为 16-200 个字符", http_status=400)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"identity-{digest[:55]}", digest


def _actor(user: dict) -> tuple[int, int]:
    tenant_id = jobs._tenant_id()
    actor_id = jobs._actor_id(user)
    if not actor_id:
        raise AppException("UNAUTHORIZED", "身份导入缺少有效操作者", http_status=401)
    return tenant_id, actor_id


def _assert_same_request(row: FileUploadSession, *, kind: str, actor_id: int, digest: str) -> None:
    meta = dict(row.metadata_json or {})
    if str(row.source or "").upper() != _SOURCE:
        raise AppException("IDEMPOTENCY_CONFLICT", "该 Idempotency-Key 已被其他上传流程占用", http_status=409)
    if int(row.created_by or 0) != int(actor_id):
        raise AppException("IDEMPOTENCY_CONFLICT", "该 Idempotency-Key 已被其他操作者占用", http_status=409)
    if str(meta.get("kind") or "").upper() != kind:
        raise AppException("IDEMPOTENCY_CONFLICT", "同一 Idempotency-Key 不得跨学生/教师导入复用", http_status=409)
    if str(meta.get("idempotencyKeyHash") or "") != digest:
        raise AppException("IDEMPOTENCY_CONFLICT", "Idempotency-Key 校验失败", http_status=409)


def _job_for_file(db, *, tenant_id: int, file_id: int, kind: str, user: dict) -> dict | None:
    row = db.scalar(select(ImportJob).where(
        ImportJob.tenant_id == tenant_id,
        ImportJob.source_file_id == int(file_id),
        ImportJob.import_type == f"IDENTITY_{kind}",
        ImportJob.is_deleted.is_(False),
    ).order_by(ImportJob.id.desc()).limit(1))
    if row is None:
        return None
    jobs._assert_row_visible(row, user)
    return jobs._import_row(row)


def _recover_file(db, session: FileUploadSession, *, actor_id: int) -> None:
    if session.file_id:
        return
    file_obj = db.scalar(select(FileObject).where(
        FileObject.tenant_id == int(session.tenant_id),
        FileObject.biz_type == "DATA_IMPORT_SOURCE",
        FileObject.biz_id == str(session.session_key),
        FileObject.owner_user_id == actor_id,
        FileObject.is_deleted.is_(False),
    ).order_by(FileObject.id.desc()).limit(1))
    if file_obj is None:
        return
    session.file_id = int(file_obj.id)
    session.status = "COMPLETED"
    session.expected_size = int(file_obj.size_bytes or 0)
    session.received_size = int(file_obj.size_bytes or 0)
    session.completed_at = file_obj.created_at or datetime.utcnow()
    meta = dict(session.metadata_json or {})
    meta.update({"fileId": str(file_obj.id), "fileSha256": file_obj.sha256, "recoveredFileObject": True})
    session.metadata_json = meta
    session.version = int(session.version or 0) + 1
    db.commit()


def _consume(db, row: FileUploadSession, *, kind: str, actor_id: int, digest: str, filename: str, user: dict) -> dict:
    _assert_same_request(row, kind=kind, actor_id=actor_id, digest=digest)
    _recover_file(db, row, actor_id=actor_id)
    if row.file_id:
        return {
            "sessionKey": row.session_key,
            "sourceFileId": int(row.file_id),
            "replayJob": _job_for_file(db, tenant_id=int(row.tenant_id), file_id=int(row.file_id), kind=kind, user=user),
            "idempotentReplay": True,
            "fileName": row.file_name or filename,
        }
    updated_at = row.updated_at or row.created_at or datetime.utcnow()
    stale = (datetime.utcnow() - updated_at).total_seconds() >= _STALE_SECONDS
    status = str(row.status or "").upper()
    if status not in {"FAILED", "EXPIRED"} and not stale:
        raise AppException("IDEMPOTENCY_IN_PROGRESS", "同一导入请求正在上传或登记，请勿重复提交", http_status=409, details={"retryable": True})
    meta = dict(row.metadata_json or {})
    meta.update({"retryAt": datetime.utcnow().isoformat() + "Z", "lastError": None})
    row.status = "UPLOADING"
    row.file_name = str(filename or row.file_name or "identity_import.xlsx")
    row.metadata_json = meta
    row.expires_at = datetime.utcnow() + timedelta(hours=2)
    row.version = int(row.version or 0) + 1
    db.commit()
    return {"sessionKey": row.session_key, "sourceFileId": None, "replayJob": None, "idempotentReplay": True, "fileName": row.file_name}


def prepare_request(*, kind: str, idempotency_key: str, filename: str, user: dict) -> dict:
    kind_up = _kind(kind)
    tenant_id, actor_id = _actor(user)
    session_key, digest = _session_identity(idempotency_key)
    db = get_sessionmaker()()
    try:
        existing = db.scalar(select(FileUploadSession).where(
            FileUploadSession.tenant_id == tenant_id,
            FileUploadSession.session_key == session_key,
        ).with_for_update())
        if existing is not None:
            return _consume(db, existing, kind=kind_up, actor_id=actor_id, digest=digest, filename=filename, user=user)
        row = FileUploadSession(
            tenant_id=tenant_id,
            session_key=session_key,
            status="UPLOADING",
            source=_SOURCE,
            file_name=str(filename or "identity_import.xlsx"),
            received_size=0,
            expires_at=datetime.utcnow() + timedelta(hours=2),
            created_by=actor_id,
            metadata_json={"kind": kind_up, "idempotencyKeyHash": digest, "reservedAt": datetime.utcnow().isoformat() + "Z"},
        )
        db.add(row)
        db.commit()
        return {"sessionKey": session_key, "sourceFileId": None, "replayJob": None, "idempotentReplay": False, "fileName": row.file_name}
    except IntegrityError:
        db.rollback()
        winner = db.scalar(select(FileUploadSession).where(
            FileUploadSession.tenant_id == tenant_id,
            FileUploadSession.session_key == session_key,
        ).with_for_update())
        if winner is None:
            raise
        return _consume(db, winner, kind=kind_up, actor_id=actor_id, digest=digest, filename=filename, user=user)
    finally:
        db.close()


def complete_request(*, session_key: str, source_file_id: int, user: dict) -> None:
    tenant_id, actor_id = _actor(user)
    db = get_sessionmaker()()
    try:
        row = db.scalar(select(FileUploadSession).where(
            FileUploadSession.tenant_id == tenant_id,
            FileUploadSession.session_key == str(session_key),
        ).with_for_update())
        if row is None or int(row.created_by or 0) != actor_id:
            raise AppException("IDEMPOTENCY_CONFLICT", "身份导入上传会话不存在或不属于当前操作者", http_status=409)
        file_obj = db.scalar(select(FileObject).where(
            FileObject.id == int(source_file_id),
            FileObject.tenant_id == tenant_id,
            FileObject.biz_type == "DATA_IMPORT_SOURCE",
            FileObject.biz_id == str(session_key),
            FileObject.owner_user_id == actor_id,
            FileObject.is_deleted.is_(False),
        ))
        if file_obj is None:
            raise AppException("FILE_NOT_FOUND", "身份导入源文件与幂等会话不匹配", http_status=409)
        if row.file_id and int(row.file_id) != int(source_file_id):
            raise AppException("IDEMPOTENCY_CONFLICT", "同一 Idempotency-Key 已绑定其他文件", http_status=409)
        row.file_id = int(source_file_id)
        row.status = "COMPLETED"
        row.expected_size = int(file_obj.size_bytes or 0)
        row.received_size = int(file_obj.size_bytes or 0)
        row.completed_at = datetime.utcnow()
        meta = dict(row.metadata_json or {})
        meta.update({"fileId": str(file_obj.id), "fileSha256": file_obj.sha256, "completedAt": datetime.utcnow().isoformat() + "Z"})
        row.metadata_json = meta
        row.version = int(row.version or 0) + 1
        db.commit()
    finally:
        db.close()


def mark_failed(*, session_key: str, message: str, user: dict) -> None:
    tenant_id, actor_id = _actor(user)
    db = get_sessionmaker()()
    try:
        row = db.scalar(select(FileUploadSession).where(
            FileUploadSession.tenant_id == tenant_id,
            FileUploadSession.session_key == str(session_key),
        ).with_for_update())
        if row is None or int(row.created_by or 0) != actor_id or row.file_id:
            return
        meta = dict(row.metadata_json or {})
        meta.update({"lastError": str(message or "上传失败")[:500], "failedAt": datetime.utcnow().isoformat() + "Z"})
        row.status = "FAILED"
        row.metadata_json = meta
        row.version = int(row.version or 0) + 1
        db.commit()
    finally:
        db.close()
