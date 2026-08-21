"""阶段 5 学工材料总览、旧数据回填、版本化 Reader 与真实档案 Manifest API。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.v1.file_contract import validated_local_file_response
from app.core.exceptions import AppException, not_found
from app.core.permissions import has_permission
from app.core.response import success
from app.core.security import get_current_user
from app.modules.student_affairs.services import affairs_material_center_service as center
from app.services import affairs_material_preview_access as material_tickets
from app.services.db_service import _tid, session

router = APIRouter(tags=["学工中心·公共材料与档案"])


class BackfillBody(BaseModel):
    limit: int = Field(500, ge=1, le=5000)


@router.get("/student-affairs/material-center", summary="学校端学工材料总览")
def material_center(
    status: str | None = Query(None),
    sensitivityLevel: str | None = Query(None),
    requirementId: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    user=Depends(get_current_user),
):
    return success(center.material_overview(
        user, status=status, sensitivity_level=sensitivityLevel, requirement_id=requirementId,
        page=page, page_size=pageSize,
    ))


@router.get("/student-affairs/material-center/biz-context",
            summary="解析业务记录的可读上下文（供业务详情发起补材料预填）")
def material_biz_context(
    bizType: str = Query(..., min_length=1),
    bizId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    return success(center.resolve_biz_context(user, bizType, bizId))


@router.get("/student-affairs/material-center/item-suggestions",
            summary="本校该业务域已用过的材料项（登记时选择，不用猜编码）")
def material_item_suggestions(
    bizType: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
):
    return success({"items": center.list_item_suggestions(user, bizType, limit=limit)})


@router.post("/student-affairs/material-center/backfill", summary="幂等回填旧学工材料与附件")
def material_backfill(body: BackfillBody, user=Depends(get_current_user)):
    return success(center.backfill_legacy(user, limit=body.limit), message="学工材料回填批次已完成")


@router.post("/student-affairs/material-center/files/{file_id}/ticket", summary="签发学工材料版本绑定预览/下载票据")
def material_file_ticket(
    file_id: int,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    raw_version_id = str((body or {}).get("fileVersionId") or "").strip()
    if not raw_version_id.isdigit():
        raise AppException("VALIDATION_ERROR", "fileVersionId 不能为空")
    action = str((body or {}).get("action") or "preview")
    return success(material_tickets.issue_ticket(file_id, int(raw_version_id), action, user))


@router.get("/student-affairs/material-center/files/{file_id}/preview", summary="按不可变 FileVersion 站内预览学工材料")
def preview_material(
    file_id: int,
    ticket: str = Query(...),
    user=Depends(get_current_user),
):
    path, filename, version_id = material_tickets.consume_ticket(file_id, "preview", ticket, user)
    return validated_local_file_response(
        path,
        filename=filename,
        audit_action="STUDENT_AFFAIRS_VERSIONED_MATERIAL_PREVIEW",
        audit_target=f"student-affairs-file:{file_id}:version:{version_id}",
        inline=True,
        audit_detail={
            "fileId": str(file_id),
            "fileVersionId": str(version_id),
            "surface": "STAFF_PC",
            "businessTicket": True,
        },
    )


@router.get("/student-affairs/material-center/files/{file_id}/download", summary="按不可变 FileVersion 下载学工材料")
def download_material(
    file_id: int,
    ticket: str = Query(...),
    user=Depends(get_current_user),
):
    path, filename, version_id = material_tickets.consume_ticket(file_id, "download", ticket, user)
    return validated_local_file_response(
        path,
        filename=filename,
        audit_action="STUDENT_AFFAIRS_VERSIONED_MATERIAL_DOWNLOAD",
        audit_target=f"student-affairs-file:{file_id}:version:{version_id}",
        audit_detail={
            "fileId": str(file_id),
            "fileVersionId": str(version_id),
            "surface": "STAFF_PC",
            "businessTicket": True,
        },
    )


@router.get("/student-affairs/material-center/students/{student_id}/manifest", summary="查看学生最新真实档案清单")
def latest_student_manifest(
    student_id: int = Path(..., ge=1),
    user=Depends(get_current_user),
):
    if not has_permission(user or {}, "studentAffairs.archive.view"):
        raise not_found("档案清单不存在")
    from app.models import ArchivePackage
    from app.models.file import ArchiveManifest

    with session() as db:
        center._require_student_scope(db, student_id, user, hide=True)
        package = db.scalars(select(ArchivePackage).where(
            ArchivePackage.tenant_id == _tid(),
            ArchivePackage.student_id == int(student_id),
            ArchivePackage.manifest_id.is_not(None),
            ArchivePackage.is_deleted.is_(False),
        ).order_by(ArchivePackage.id.desc())).first()
        if not package:
            return success({"manifest": None})
        manifest = db.get(ArchiveManifest, int(package.manifest_id))
        if not manifest or manifest.is_deleted or manifest.tenant_id != _tid():
            return success({"manifest": None})
        return success({
            "packageId": str(package.id),
            "studentId": str(student_id),
            "manifest": center._manifest_row(db, manifest),
        })


@router.get("/student-affairs/archive/packages/{package_id}/manifest", summary="查看学生真实档案版本清单")
def archive_package_manifest(
    package_id: int = Path(..., ge=1),
    user=Depends(get_current_user),
):
    return success(center.get_archive_manifest(package_id, user))
