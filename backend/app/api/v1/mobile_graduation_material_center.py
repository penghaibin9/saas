"""阶段 6：学生 PC/小程序毕业设计材料公共版本入口。

与旧移动端保持相同 POST URL；本 Router 必须先于 mobile.router 注册。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import FileResponse

from app.core.permissions import require_module
from app.core.response import success
from app.core.security import get_current_user
from app.modules.graduation.services import graduation_material_center_service as center
from app.services import audit_log

router = APIRouter(
    prefix="/mobile/graduation",
    tags=["移动端-毕业设计材料版本中心"],
    dependencies=[Depends(require_module("graduation"))],
)


def _with_batch(user: dict, batch_id: int | None) -> dict:
    scoped = dict(user or {})
    if batch_id:
        scoped["graduationBatchId"] = str(batch_id)
    return scoped


@router.post("/proposal", summary="开题·本人提交/重交并生成公共文件版本")
def submit_proposal(
    body: dict = Body(...),
    batchId: int | None = Query(default=None, ge=1),
    user=Depends(get_current_user),
):
    result = center.submit_proposal(_with_batch(user, batchId), body or {})
    return success(result, message="开题报告已提交")


@router.post("/final", summary="成果·本人提交/重交并生成公共文件版本")
def submit_final(
    body: dict = Body(...),
    batchId: int | None = Query(default=None, ge=1),
    user=Depends(get_current_user),
):
    result = center.submit_final(_with_batch(user, batchId), body or {})
    return success(result, message="论文成果已提交")


@router.get("/material-center/library", summary="我的毕业设计材料库")
def material_library(
    includeHistory: bool = Query(default=True),
    batchId: int | None = Query(default=None, ge=1),
    user=Depends(get_current_user),
):
    return success(center.student_material_library(
        None, _with_batch(user, batchId), include_history=includeHistory,
    ))


@router.get("/material-center/manifest", summary="我的毕业设计归档 Manifest")
def material_manifest(
    batchId: int | None = Query(default=None, ge=1),
    user=Depends(get_current_user),
):
    scoped = _with_batch(user, batchId)
    from app.db.session import get_sessionmaker
    from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student

    db = get_sessionmaker()()
    try:
        student = resolve_current_gd_student(db, scoped)
        if not student:
            from app.core.exceptions import not_found
            raise not_found("毕业设计归档清单不存在")
        student_id = int(student.id)
    finally:
        db.close()
    return success(center.get_manifest(student_id, scoped))


@router.get("/material-center/files/{file_id}/download", summary="下载本人当前或历史毕业设计材料版本")
def download_material(file_id: int, user=Depends(get_current_user)):
    path, filename = center.resolve_material_download(file_id, user, student_mode=True)
    audit_log.record("STUDENT_GRADUATION_VERSIONED_MATERIAL_DOWNLOAD", f"graduation-file:{file_id}")
    response = FileResponse(str(path), filename=filename, content_disposition_type="attachment")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@router.get("/material-center/packages/{file_id}/download", summary="下载本人毕业设计归档包")
def download_package(file_id: int, user=Depends(get_current_user)):
    path, filename = center.resolve_package_download(file_id, user)
    audit_log.record("STUDENT_GRADUATION_ARCHIVE_PACKAGE_DOWNLOAD", f"graduation-package:{file_id}")
    response = FileResponse(str(path), filename=filename, content_disposition_type="attachment")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response
