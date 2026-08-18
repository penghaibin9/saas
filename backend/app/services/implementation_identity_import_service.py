"""Safe mixed identity workbook adapter for the school implementation center.

The implementation workflow is the only remaining consumer of the historical
mixed Student + Teacher + business-relation workbook.  It may keep that semantic
contract, but never the old upload-direct-parse trust boundary: every workbook is
first persisted as a DATA_IMPORT_SOURCE FileObject and, when production scanning
is enabled, remains unusable until the common File Center marks it CLEAN/AVAILABLE.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.identity_import_batch import IdentityImportBatch
from app.services import audit_log
from app.services import file_service
from app.services import identity_import_file_service as batch_service
from app.services import system_implementation_service as implementation
from app.services.file_access_service import upsert_file_binding
from app.services.file_scan_service import assert_file_ready_for_business
from app.services.identity_import_path_parser import parse_mixed_identity_xlsx_path
from app.services.message_identity import resolve_message_user_id
from app.services.storage import get_backend

BIZ_TYPE = "DATA_IMPORT_SOURCE"


def _project() -> dict:
    project = implementation.current_project()
    if not project:
        raise AppException("DATA_CONFLICT", "请先创建实施项目，再上传师生实施模板", http_status=409)
    return project


def _tenant_id() -> int:
    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return tenant_id


async def upload(file, *, user: dict) -> dict:
    project = _project()
    upload_ref = f"implementation:{project.get('id')}:{uuid4().hex}"
    meta = await file_service.store_upload(
        file,
        BIZ_TYPE,
        biz_id=upload_ref,
        user=user,
        visibility="PRIVATE",
        security_level="SENSITIVE",
    )
    file_id = str(meta.get("fileId") or "").strip()
    actor_id = int(resolve_message_user_id(user) or 0)
    if not file_id or not actor_id:
        raise AppException(
            "UPLOAD_FAILED",
            "实施导入文件未建立可验证的上传者身份，请重新登录后上传",
            http_status=500,
        )
    # store_upload 的通用兼容绑定仍保留 raw token subject；实施导入必须在进入
    # FileObject 校验前收敛到 resolver 使用的 canonical USER id。这里不放宽权限，
    # 只是让“上传者本人”写入与读取使用同一身份真值。
    upsert_file_binding(
        file_id,
        biz_type=BIZ_TYPE,
        biz_id=upload_ref,
        subject_type="USER",
        subject_id=str(actor_id),
        user=user,
    )
    audit_log.record(
        "IMPLEMENTATION_IDENTITY_FILE_UPLOAD",
        f"file:{file_id}",
        detail={
            "projectId": str(project.get("id") or ""),
            "fileName": meta.get("fileName"),
            "sha256": meta.get("sha256"),
            "scanRequired": bool(meta.get("scanRequired")),
            "moduleCode": "systemAdmin",
        },
    )
    return {
        **meta,
        "projectId": str(project.get("id") or ""),
        "validationEntry": f"/api/v1/system/implementation/identity-import/files/{file_id}/validate",
    }


def _existing_validated_batch(*, user: dict, sha256: str) -> dict | None:
    tenant_id = _tenant_id()
    operator_key = batch_service._user_key(user)  # same ownership contract as create/get/confirm
    db = get_sessionmaker()()
    try:
        row = db.scalars(
            select(IdentityImportBatch)
            .where(
                IdentityImportBatch.tenant_id == tenant_id,
                IdentityImportBatch.operator_key == operator_key,
                IdentityImportBatch.file_sha256 == sha256,
                IdentityImportBatch.status.in_(("VALIDATED", "CONFIRMING")),
                IdentityImportBatch.expires_at > datetime.utcnow(),
                IdentityImportBatch.is_deleted.is_(False),
            )
            .order_by(IdentityImportBatch.id.desc())
            .limit(1)
        ).first()
        batch_no = str(row.batch_no) if row else ""
    finally:
        db.close()
    if not batch_no:
        return None
    return batch_service.get_batch(user, tenant_id, batch_no)


def validate(file_id: str, *, user: dict) -> dict:
    project = _project()
    row = assert_file_ready_for_business(file_id, user=user, biz_type=BIZ_TYPE)
    sha256 = str(getattr(row, "sha256", "") or "").strip().lower()
    existing = _existing_validated_batch(user=user, sha256=sha256) if sha256 else None
    if existing is not None:
        return {
            **existing,
            "sourceFileId": str(file_id),
            "scanStatus": str(getattr(row, "scan_status", "") or ""),
            "reused": True,
        }

    local_path = get_backend().fetch_local(str(getattr(row, "file_key", "") or ""))
    if local_path is None or not local_path.exists():
        raise AppException("DATA_NOT_FOUND", "实施导入源文件不存在或已被清理", http_status=404)

    filename = str(getattr(row, "file_name", "") or "implementation-identity.xlsx")
    parsed = parse_mixed_identity_xlsx_path(local_path, filename)
    parsed_sha256 = str(parsed.get("fileSha256") or "").strip().lower()
    if sha256 and parsed_sha256 != sha256:
        raise AppException(
            "DATA_CONFLICT",
            "实施导入源文件完整性校验失败，请重新上传",
            http_status=409,
        )

    from app.services.identity_import_service import preview_identity_import

    payload = {
        "students": parsed["students"],
        "teachers": parsed["teachers"],
        "atomic": True,
    }
    report = preview_identity_import(user, payload, pre_errors=parsed["errors"])
    result = batch_service.create_batch(user, parsed, report)
    audit_log.record(
        "IMPLEMENTATION_IDENTITY_FILE_VALIDATED",
        f"identity-import:{result.get('batchNo')}",
        detail={
            "projectId": str(project.get("id") or ""),
            "sourceFileId": str(file_id),
            "sha256": sha256,
            "total": result.get("total"),
            "invalid": result.get("invalid"),
            "moduleCode": "systemAdmin",
        },
    )
    return {
        **result,
        "sourceFileId": str(file_id),
        "scanStatus": str(getattr(row, "scan_status", "") or ""),
        "reused": False,
    }
