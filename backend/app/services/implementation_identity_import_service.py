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
from app.services.file_scan_service import assert_file_ready_for_business
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
    audit_log.record(
        "IMPLEMENTATION_IDENTITY_FILE_UPLOAD",
        f"file:{meta.get('fileId')}",
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
        "validationEntry": f"/api/v1/system/implementation/identity-import/files/{meta.get('fileId')}/validate",
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
    sha256 = str(getattr(row, "sha256", "") or "").strip()
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

    parsed = batch_service.parse_xlsx(
        local_path.read_bytes(),
        str(getattr(row, "file_name", "") or "implementation-identity.xlsx"),
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
