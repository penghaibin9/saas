"""Academic course-material Reader endpoints.

This extension keeps the existing course material CRUD contract unchanged and adds only the
business-scoped read authority required by the shared PC document viewer.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel

from app.api.v1.file_contract import validated_local_file_response
from app.core.response import success
from app.modules.academic_affairs.routers import academic_affairs as legacy
from app.modules.academic_affairs.services import academic_affairs_course_material_preview_access as preview_svc

router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])
_COURSE_VIEW = legacy._COURSE_VIEW


class CourseMaterialTicketRequest(BaseModel):
    action: Literal["preview", "download"]


@router.get("/courses/{courseId}/materials/reader", summary="课程材料 Reader 清单（业务范围 + 文件安全态）")
def course_material_reader_list(
    courseId: int = Path(...),
    user=Depends(_COURSE_VIEW),
):
    return success({"items": preview_svc.list_reader_files(courseId, user)})


@router.post("/courses/{courseId}/materials/{materialId}/ticket", summary="签发课程材料预览/下载短时票据")
def course_material_ticket(
    body: CourseMaterialTicketRequest,
    courseId: int = Path(...),
    materialId: int = Path(...),
    user=Depends(_COURSE_VIEW),
):
    return success(preview_svc.issue_ticket(courseId, materialId, body.action, user))


@router.get("/courses/{courseId}/materials/{materialId}/preview", summary="使用课程材料票据站内预览")
def preview_course_material(
    courseId: int = Path(...),
    materialId: int = Path(...),
    ticket: str = Query(..., min_length=20),
    user=Depends(_COURSE_VIEW),
):
    path, filename, mime_type = preview_svc.consume_ticket(courseId, materialId, "preview", ticket, user)
    return validated_local_file_response(
        path,
        filename=filename,
        inline=True,
        media_type=mime_type,
        audit_action="ACADEMIC_COURSE_MATERIAL_PREVIEW",
        audit_target=f"academic-course:{courseId}:material:{materialId}",
        audit_detail={"courseId": str(courseId), "materialId": str(materialId)},
    )


@router.get("/courses/{courseId}/materials/{materialId}/download", summary="使用一次性课程材料票据下载")
def download_course_material(
    courseId: int = Path(...),
    materialId: int = Path(...),
    ticket: str = Query(..., min_length=20),
    user=Depends(_COURSE_VIEW),
):
    path, filename, mime_type = preview_svc.consume_ticket(courseId, materialId, "download", ticket, user)
    return validated_local_file_response(
        path,
        filename=filename,
        media_type=mime_type,
        audit_action="ACADEMIC_COURSE_MATERIAL_DOWNLOAD",
        audit_target=f"academic-course:{courseId}:material:{materialId}",
        audit_detail={"courseId": str(courseId), "materialId": str(materialId)},
    )
