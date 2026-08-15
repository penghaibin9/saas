"""Control Plane Data Exchange router.

The frozen bundle keeps every legacy route. I1/I2 replaces identity-import
creation/detail semantics: create is idempotent SCANNING-only, GET is pure read,
and parsing advances only through explicit /process or /retry commands.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.system_admin.routers import data_exchange_bundle as _bundle
from app.modules.system_admin.services import identity_import_control_plane_service as identity
from app.modules.system_admin.services import identity_import_idempotency_service as upload_idem

_replacements = APIRouter(prefix="/data-exchange", tags=["15·数据交换任务中心"])


def _message(item: dict) -> str:
    status = str(item.get("status") or "").upper()
    return {
        "SCANNING": "文件已登记；安全扫描和解析由后台 worker 显式推进",
        "PARSING": "文件安全扫描已通过，后台任务正在解析预检",
        "VALIDATED": "文件安全扫描与服务端预检已通过",
        "VALIDATION_FAILED": "服务端预检存在错误，请查看任务详情或下载错误回执",
        "FAILED": "导入任务失败，可执行显式重试",
    }.get(status, "身份导入任务已创建")


async def run_identity_import_upload(
    *,
    kind: Literal["students", "teachers"],
    file: UploadFile,
    user: dict,
    idempotency_key: str,
):
    """Reserve request identity before storing any sensitive FileObject bytes."""
    from app.core.import_export_auth import enforce_student_import
    from app.services import file_service

    import_kind = "STUDENT" if kind == "students" else "TEACHER"
    if import_kind == "STUDENT":
        enforce_student_import(user)
    reservation = upload_idem.prepare_request(
        kind=import_kind,
        idempotency_key=idempotency_key,
        filename=file.filename or f"{kind}.xlsx",
        user=user,
    )
    if reservation.get("replayJob"):
        item = {**dict(reservation["replayJob"]), "idempotentReplay": True}
        return success(item, message=_message(item))

    source_file_id = reservation.get("sourceFileId")
    if not source_file_id:
        try:
            file_meta = await file_service.store_upload(
                file,
                biz_type="DATA_IMPORT_SOURCE",
                biz_id=str(reservation["sessionKey"]),
                user=user,
                visibility="PRIVATE",
                security_level="SENSITIVE",
            )
            source_file_id = int(file_meta["fileId"])
            upload_idem.complete_request(
                session_key=str(reservation["sessionKey"]),
                source_file_id=source_file_id,
                user=user,
            )
        except Exception as exc:
            upload_idem.mark_failed(
                session_key=str(reservation["sessionKey"]),
                message=str(exc),
                user=user,
            )
            raise

    item = identity.create_identity_import_job(
        kind=import_kind,
        source_file_id=int(source_file_id),
        filename=str(reservation.get("fileName") or file.filename or f"{kind}.xlsx"),
        user=user,
        upload_session_key=str(reservation["sessionKey"]),
    )
    if reservation.get("idempotentReplay"):
        item = {**item, "idempotentReplay": True}
    return success(item, message=_message(item))


@_replacements.post(
    "/imports/identity/{kind}/validate-file",
    summary="上传学生/教师 XLSX；幂等登记 SCANNING 任务",
)
async def validate_identity_import(
    kind: Literal["students", "teachers"],
    file: UploadFile = File(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=16, max_length=200),
    user=Depends(require_permission("systemAdmin.user.import")),
):
    return await run_identity_import_upload(
        kind=kind,
        file=file,
        user=user,
        idempotency_key=idempotency_key,
    )


@_replacements.get("/imports/{job_id}", summary="导入任务详情（纯读）")
def import_job_detail(
    job_id: str,
    visibility: Literal["OWN", "MODULE", "TENANT"] = Query("OWN"),
    moduleCode: str = Query("", max_length=64),
    user=Depends(_bundle.require_any_permission_compat(*_bundle.VIEW_PERMISSIONS)),
):
    item = identity.read_identity_import_job(
        job_id,
        user=user,
        visibility=visibility,
        module_code=moduleCode,
    )
    return success(item, message=_message(item))


@_replacements.post("/imports/{job_id}/process", summary="显式推进身份导入扫描/解析 worker 命令")
def process_identity_import(
    job_id: str,
    user=Depends(_bundle.require_any_permission_compat(*_bundle.RETRY_PERMISSIONS)),
):
    item = identity.process_identity_import_job(job_id, user=user)
    return success(item, message=_message(item))


@_replacements.post("/imports/{job_id}/retry", summary="重试可安全重放的扫描或解析失败")
def retry_import(
    job_id: str,
    body: _bundle.RetryImportRequest,
    user=Depends(_bundle.require_any_permission_compat(*_bundle.RETRY_PERMISSIONS)),
):
    from app.services import data_exchange_job_service as jobs

    jobs.retry_import_job(
        job_id,
        expected_version=body.expectedVersion,
        user=user,
    )
    item = identity.process_identity_import_job(job_id, user=user)
    return success(item, message=_message(item))


def _key(route) -> tuple[str, str]:
    methods = tuple(sorted(getattr(route, "methods", set()) or set()))
    return (",".join(methods), getattr(route, "path", ""))


def _compose() -> APIRouter:
    replacement = {_key(route): route for route in _replacements.routes}
    composed = APIRouter()
    routes = []
    for route in _bundle.router.routes:
        routes.append(replacement.pop(_key(route), route))
    if replacement:
        new_keys = {key for key in replacement if key[1].endswith("/process")}
        unexpected = sorted(set(replacement) - new_keys)
        if unexpected:
            raise RuntimeError(f"Data Exchange replacement route has no frozen target: {unexpected}")
        routes.extend(replacement[key] for key in sorted(new_keys))
    composed.routes = routes
    return composed


router = _compose()
