"""职业教育国家标准库：学校检索/绑定与平台采集状态。"""
from fastapi import APIRouter, Body, Depends, Query

from app.api.v1.platform import require_platform_super_admin
from app.core.permissions import require_any_permission
from app.core.response import success
from app.services import national_standard_service as service

router = APIRouter(prefix="/national-standards", tags=["职业教育国家标准库"])
platform_router = APIRouter(prefix="/platform/national-standards", tags=["平台·国家标准库"])

_VIEW = require_any_permission("systemAdmin.implementation.preset.view",
                               "systemAdmin.implementation.view",
                               "academicAffairs.program.view")
_BIND = require_any_permission("systemAdmin.implementation.configure",
                               "academicAffairs.program.manage")


@router.get("/stats")
def stats(user=Depends(_VIEW)):
    return success(service.stats())


@router.get("/documents")
def documents(keyword: str = Query(default="", max_length=100),
              educationLevel: str = Query(default=""), categoryCode: str = Query(default=""),
              textStatus: str = Query(default=""), documentType: str = Query(default=""),
              page: int = Query(default=1, ge=1),
              pageSize: int = Query(default=20, ge=1, le=100), user=Depends(_VIEW)):
    return success(service.search_documents(keyword, educationLevel, categoryCode,
                                            textStatus, documentType, page, pageSize))


@router.get("/documents/{document_id}")
def document_detail(document_id: int, user=Depends(_VIEW)):
    return success(service.document_detail(document_id))


@router.get("/catalog")
def catalog(educationLevel: str = Query(default=""), categoryCode: str = Query(default=""),
            keyword: str = Query(default="", max_length=100), page: int = Query(default=1, ge=1),
            pageSize: int = Query(default=100, ge=1, le=300), user=Depends(_VIEW)):
    return success(service.catalog(educationLevel, categoryCode, keyword, page, pageSize))


@router.get("/bindings")
def bindings(user=Depends(_VIEW)):
    return success(service.school_bindings())


@router.post("/bindings")
def bind(body: dict = Body(...), user=Depends(_BIND)):
    return success(service.bind_school_major(user, body), message="学校专业已绑定国家教学标准")


@platform_router.get("/sources")
def source_status(user=Depends(require_platform_super_admin)):
    return success(service.source_status())


@platform_router.get("/stats")
def platform_stats(user=Depends(require_platform_super_admin)):
    return success(service.stats())
