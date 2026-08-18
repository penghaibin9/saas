"""I1/I2 thin adapters for deprecated /system/identity-import URLs.

Student/teacher uploads are redirected into the canonical Data Exchange
FileObject→scan→ImportJob chain. The obsolete mixed parser remains retired in
production. The implementation center keeps a narrowly-scoped non-production
migration adapter for its legacy contract tests, but even that path first stores
the workbook through FileObject/content-security rather than parsing upload bytes.
"""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Body, Depends, File, Header, UploadFile

from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.core.permissions import enforce_permission, require_permission
from app.core.response import success
from app.modules.system_admin.routers import data_exchange_router
from app.modules.system_admin.services import identity_import_control_plane_service as identity

router = APIRouter()


def _compat_preview(item: dict) -> dict:
    status = str(item.get("status") or "").upper()
    validated = status in {"VALIDATED", "VALIDATION_FAILED"}
    return {
        **item,
        "jobId": item.get("id"),
        "batchNo": item.get("adapterRef")
        if str(item.get("adapterType") or "") == "IDENTITY_IMPORT_BATCH"
        else None,
        "total": int(item.get("totalRows") or 0) if validated else None,
        "valid": int(item.get("validRows") or 0) if validated else None,
        "invalid": int(item.get("invalidRows") or 0) if validated else None,
        "errors": [],
        "async": True,
        "canonicalEntry": "/data-exchange/imports/identity/{kind}/validate-file",
    }


def _compat_idempotency_key(value: str | None) -> str:
    key = str(value or "").strip()
    if key:
        return key
    return f"legacy-identity-upload-{uuid.uuid4()}"


def _raise_mixed_retired() -> None:
    raise AppException(
        "LEGACY_IDENTITY_IMPORT_RETIRED",
        "混合师生直解析入口已停用；实施中心请使用其 FileObject 安全扫描入口，普通导入请分别使用学生/教师正式入口",
        http_status=410,
        details={
            "implementationEntry": "/api/v1/system/implementation/identity-import/files",
            "studentEntry": "/api/v1/data-exchange/imports/identity/students/validate-file",
            "teacherEntry": "/api/v1/data-exchange/imports/identity/teachers/validate-file",
        },
    )


@router.post("/system/identity-import/validate-file", summary="已停用：混合师生 direct parser")
async def legacy_mixed_validate_file(
    file: UploadFile = File(...),
    user=Depends(require_permission("systemAdmin.user.import")),
):
    # Production never revives the old upload-direct-parse endpoint.  A narrow
    # non-production implementation-center bridge is retained so the frozen
    # implementation regression exercises the same mixed workbook semantics while
    # still passing through FileObject/content-security first.
    if settings.is_prod:
        _raise_mixed_retired()
    from app.services import system_implementation_service as implementation
    from app.services.file_content_security import is_scan_required_for_upload

    if not implementation.current_project() or is_scan_required_for_upload("xlsx"):
        _raise_mixed_retired()
    enforce_permission(user, "systemAdmin.implementation.mapping.manage")
    from app.services import implementation_identity_import_service as implementation_identity

    uploaded = await implementation_identity.upload(file, user=user)
    result = implementation_identity.validate(str(uploaded.get("fileId") or ""), user=user)
    return success(result, message="实施中心兼容预检已通过统一文件安全入口")


@router.post("/system/identity-import/students/validate-file", summary="兼容入口：学生文件转 Data Exchange")
async def legacy_student_validate_file(
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user=Depends(require_permission("systemAdmin.user.import")),
):
    response = await data_exchange_router.run_identity_import_upload(
        kind="students",
        file=file,
        user=user,
        idempotency_key=_compat_idempotency_key(idempotency_key),
    )
    item = dict((response or {}).get("data") or {}) if isinstance(response, dict) else {}
    return success(_compat_preview(item), message="学生文件已进入安全扫描与后台预检任务")


@router.post("/system/identity-import/teachers/validate-file", summary="兼容入口：教师文件转 Data Exchange")
async def legacy_teacher_validate_file(
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user=Depends(require_permission("systemAdmin.user.import")),
):
    response = await data_exchange_router.run_identity_import_upload(
        kind="teachers",
        file=file,
        user=user,
        idempotency_key=_compat_idempotency_key(idempotency_key),
    )
    item = dict((response or {}).get("data") or {}) if isinstance(response, dict) else {}
    return success(_compat_preview(item), message="教师文件已进入安全扫描与后台预检任务")


def _legacy_confirm(body: dict, user: dict) -> dict:
    from app.services.data_exchange_confirm_service import confirm_identity_import_job

    reference = str(body.get("jobId") or body.get("batchNo") or "").strip()
    item = identity.find_identity_job_by_batch(reference, user=user)
    job_id = str(item.get("id") or "")
    expected = int(
        body.get("expectedVersion")
        if body.get("expectedVersion") is not None
        else item.get("version") or 0
    )
    idem = str(body.get("idempotencyKey") or "").strip()
    if not idem:
        tenant_part = str((user or {}).get("tenantId") or "tenant")
        idem = "legacy-confirm-" + hashlib.sha256(
            f"{tenant_part}:{job_id}:{reference}".encode()
        ).hexdigest()
    result = confirm_identity_import_job(
        job_id,
        expected_version=expected,
        user=user,
        idempotency_key=idem,
    )
    return {
        **result,
        "jobId": result.get("id"),
        "batchNo": result.get("adapterRef"),
        "receipt": "身份导入已由统一数据交换任务中心确认",
    }


def _mixed_implementation_batch(reference: str, user: dict) -> bool:
    if not reference:
        return False
    from app.services.identity_import_file_service import get_batch

    try:
        get_batch(user, current_tenant_id(), reference)
        return True
    except AppException as exc:
        if exc.code in {"DATA_NOT_FOUND", "BATCH_NOT_FOUND", "NO_PERMISSION"}:
            return False
        raise


@router.post("/system/identity-import/confirm-batch", summary="兼容确认：ImportJob 或实施中心 mixed batch")
def legacy_mixed_confirm(
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.user.import")),
):
    reference = str(body.get("jobId") or body.get("batchNo") or "").strip()
    if _mixed_implementation_batch(reference, user):
        enforce_permission(user, "systemAdmin.implementation.mapping.manage")
        from app.modules.system_admin.routers import system_bundle as frozen_bundle

        return frozen_bundle.identity_import_confirm_batch(body=body, user=user)
    return success(_legacy_confirm(body, user))


@router.post("/system/identity-import/students/confirm-batch", summary="兼容确认学生 ImportJob")
def legacy_student_confirm(
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.user.import")),
):
    return success(_legacy_confirm(body, user))


@router.post("/system/identity-import/teachers/confirm-batch", summary="兼容确认教师 ImportJob")
def legacy_teacher_confirm(
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.user.import")),
):
    return success(_legacy_confirm(body, user))
