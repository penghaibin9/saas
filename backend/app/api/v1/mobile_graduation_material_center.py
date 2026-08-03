"""阶段 6：学生 PC/小程序与教师小程序毕业设计材料公共版本入口。

旧开题/成果 POST URL 保持不变；大型论文、作品和源代码仍引导学生 PC 上传。
所有本地文件字节响应统一委托公共文件权威合同。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.api.v1.file_contract import validated_local_file_response
from app.core.exceptions import AppException, not_found
from app.core.permissions import require_module
from app.core.response import success
from app.core.security import get_current_user
from app.modules.graduation.materials import query_service as queries
from app.modules.graduation.services import graduation_material_catalog_service as catalog
from app.modules.graduation.services import graduation_material_center_service as center
from app.modules.graduation.services import graduation_material_export_service as archive_export
from app.modules.graduation.services import graduation_material_ticket_service as tickets

router = APIRouter(
    prefix="/mobile/graduation",
    tags=["移动端-毕业设计材料版本中心"],
    dependencies=[Depends(require_module("graduation"))],
)

LARGE_PC_ONLY_CODES = {"THESIS_DRAFT", "THESIS_FINAL", "DESIGN_WORK", "SOURCE_CODE", "WORK_DESCRIPTION"}


def _with_batch(user: dict, batch_id: int | None) -> dict:
    scoped = dict(user or {})
    if batch_id:
        scoped["graduationBatchId"] = str(batch_id)
    return scoped


def _current_student_id(user: dict) -> int:
    from app.db.session import get_sessionmaker
    from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student

    db = get_sessionmaker()()
    try:
        student = resolve_current_gd_student(db, user)
        if not student:
            raise not_found("毕业设计材料不存在")
        return int(student.id)
    finally:
        db.close()


@router.post("/proposal", summary="开题·本人提交/重交并生成公共文件版本")
def submit_proposal(
    body: dict = Body(...), batchId: int | None = Query(default=None, ge=1),
    user=Depends(get_current_user),
):
    scoped = _with_batch(user, batchId)
    result = center.submit_proposal(scoped, body or {})
    if str(result.get("id") or "").isdigit():
        catalog.sync_record("PROPOSAL", int(result["id"]), scoped)
    return success(result, message="开题报告已提交")


@router.post("/final", summary="成果·本人提交/重交并生成公共文件版本")
def submit_final(
    body: dict = Body(...), batchId: int | None = Query(default=None, ge=1),
    user=Depends(get_current_user),
):
    scoped = _with_batch(user, batchId)
    result = center.submit_final(scoped, body or {})
    if str(result.get("id") or "").isdigit():
        catalog.sync_record("FINAL", int(result["id"]), scoped)
    return success(result, message="论文成果已提交")


@router.post("/material-center/materials/{material_code}/submit", summary="小型材料补交")
def submit_material(
    material_code: str, body: dict = Body(...),
    batchId: int | None = Query(default=None, ge=1), user=Depends(get_current_user),
):
    code = str(material_code or "").upper()
    if str((body or {}).get("clientSurface") or "").upper() in {"MINIAPP", "MP_WEIXIN"} and code in LARGE_PC_ONLY_CODES:
        raise AppException("PC_REQUIRED", "论文、作品、源代码等大型材料请使用学生 PC 上传")
    file_id = (body or {}).get("fileId")
    if not str(file_id or "").isdigit():
        raise AppException("VALIDATION_ERROR", "fileId 不能为空")
    expected = (body or {}).get("expectedVersion")
    result = catalog.submit_material(
        _with_batch(user, batchId), code, int(file_id),
        expected_version=int(expected) if str(expected or "").isdigit() else None,
    )
    return success(result, message="材料新版本已提交")


@router.get("/material-center/library", summary="本人或教师数据范围内的毕业设计材料库")
def material_library(
    gdStudentId: int | None = Query(default=None, ge=1),
    includeHistory: bool = Query(default=True), batchId: int | None = Query(default=None, ge=1),
    user=Depends(get_current_user),
):
    scoped = _with_batch(user, batchId)
    target = gdStudentId if str((user or {}).get("userType") or "").upper() != "STUDENT" else None
    return success(queries.student_library(target, scoped, include_history=includeHistory))


@router.post("/material-center/materials/{material_id}/review", summary="教师小程序审核或退回具体版本")
def review_material(
    material_id: int, body: dict = Body(...), user=Depends(get_current_user),
):
    version_id = (body or {}).get("fileVersionId") or (body or {}).get("versionId")
    if not str(version_id or "").isdigit():
        raise AppException("VALIDATION_ERROR", "fileVersionId 不能为空")
    return success(catalog.review_material(
        material_id, int(version_id), str((body or {}).get("action") or ""),
        (body or {}).get("comment"), user,
    ), message="材料版本已审核")


@router.get("/material-center/manifest", summary="我的毕业设计归档 Manifest")
def material_manifest(
    batchId: int | None = Query(default=None, ge=1), user=Depends(get_current_user),
):
    scoped = _with_batch(user, batchId)
    return success(queries.latest_manifest(_current_student_id(scoped), scoped))


@router.post("/material-center/files/{file_id}/ticket", summary="签发小型材料预览/下载票据")
def material_ticket(file_id: int, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tickets.issue_ticket(file_id, str((body or {}).get("action") or "preview"), user))


@router.get("/material-center/files/{file_id}/preview", summary="使用票据预览小型 PDF/图片")
def preview_material(file_id: int, ticket: str = Query(...), user=Depends(get_current_user)):
    path, filename = tickets.consume_ticket(file_id, "preview", ticket, user)
    return validated_local_file_response(
        path,
        filename=filename,
        audit_action="MOBILE_GRADUATION_MATERIAL_PREVIEW",
        audit_target=f"graduation-file:{file_id}",
        inline=True,
        audit_detail={"fileId": str(file_id), "surface": "MOBILE"},
    )


@router.get("/material-center/files/{file_id}/download", summary="下载本人当前或历史毕业设计材料版本")
def download_material(
    file_id: int, ticket: str = Query(default=""), user=Depends(get_current_user),
):
    path, filename = (
        tickets.consume_ticket(file_id, "download", ticket, user)
        if ticket else center.resolve_material_download(file_id, user, student_mode=True)
    )
    return validated_local_file_response(
        path,
        filename=filename,
        audit_action="STUDENT_GRADUATION_VERSIONED_MATERIAL_DOWNLOAD",
        audit_target=f"graduation-file:{file_id}",
        audit_detail={"fileId": str(file_id), "ticketed": bool(ticket)},
    )


@router.get("/material-center/packages/{file_id}/download", summary="下载本人旧毕业设计归档包")
def download_package(file_id: int, user=Depends(get_current_user)):
    path, filename = center.resolve_package_download(file_id, user)
    return validated_local_file_response(
        path,
        filename=filename,
        audit_action="STUDENT_GRADUATION_ARCHIVE_PACKAGE_DOWNLOAD",
        audit_target=f"graduation-package:{file_id}",
        media_type="application/zip",
        audit_detail={"fileId": str(file_id)},
    )
