"""Control Plane Data Exchange router.

The frozen bundle keeps every legacy route. I1/I2 replaces only identity-import
creation/detail/retry semantics so HTTP GET is pure read and parsing is an
explicit command. Route registration remains untouched.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.system_admin.routers import data_exchange_bundle as _bundle
from app.modules.system_admin.services import identity_import_control_plane_service as identity

_replacements = APIRouter(prefix="/data-exchange", tags=["15·数据交换任务中心"])


def _message(item: dict) -> str:
    status = str(item.get("status") or "").upper()
    return {
        "SCANNING": "文件已进入安全扫描；GET 仅查询状态，解析由后台任务命令推进",
        "PARSING": "文件安全扫描已通过，后台任务正在解析预检",
        "VALIDATED": "文件安全扫描与服务端预检已通过",
        "VALIDATION_FAILED": "服务端预检存在错误，请查看任务详情或下载错误回执",
        "FAILED": "导入任务失败，可执行显式重试",
    }.get(status, "身份导入任务已创建")


@_replacements.post("/imports/identity/{kind}/validate-file", summary="上传学生/教师 XLSX；只登记扫描任务")
async def validate_identity_import(
    kind: Literal["students", "teachers"],
    file: UploadFile = File(...),
    user=Depends(require_permission("systemAdmin.user.import")),
):
    from app.core.import_export_auth import enforce_student_import
    from app.services import file_service

    import_kind = "STUDENT" if kind == "students" else "TEACHER"
    if import_kind == "STUDENT":
        enforce_student_import(user)
    file_meta = await file_service.store_upload(
        file,
        biz_type="DATA_IMPORT_SOURCE",
        user=user,
        visibility="PRIVATE",
        security_level="SENSITIVE",
    )
    item = identity.create_identity_import_job(
        kind=import_kind,
        source_file_id=int(file_meta["fileId"]),
        filename=file.filename or f"{kind}.xlsx",
        user=user,
    )
    return success(item, message=_message(item))


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
        # /process is intentionally new; all other replacement keys must exist in frozen bundle.
        new_keys = {key for key in replacement if key[1].endswith("/process")}
        unexpected = sorted(set(replacement) - new_keys)
        if unexpected:
            raise RuntimeError(f"Data Exchange replacement route has no frozen target: {unexpected}")
        routes.extend(replacement[key] for key in sorted(new_keys))
    composed.routes = routes
    return composed


router = _compose()
