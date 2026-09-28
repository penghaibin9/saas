"""Yiyang C08/G17 formal printable document API."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from fastapi.responses import FileResponse

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.internship.services import internship_formal_document_service as svc

router = APIRouter(prefix="/internship/formal-documents", tags=["岗位实习-正式文书"])


@router.get("/by-internship/{internship_id}", summary="学生正式文书版本列表")
def documents(
    internship_id: int,
    user=Depends(require_permission("internship.archive.view")),
):
    return success(svc.list_documents(user, internship_id))


@router.post("/generate", summary="按正式业务事实生成版本化 PDF")
def generate(
    body: dict = Body(...),
    user=Depends(require_permission("internship.archive.execute")),
):
    return success(svc.generate(user, body or {}), message="正式文书已生成")


@router.get("/{document_id}/download", summary="下载正式 PDF")
def download(
    document_id: int,
    user=Depends(require_permission("internship.archive.view")),
):
    path, filename = svc.resolve_download(user, document_id)
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=filename,
    )
