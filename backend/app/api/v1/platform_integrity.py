"""PLAT-A integrity center and four-client frozen package projections."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.context import current_tenant_id
from app.core.permissions import require_any_permission
from app.core.response import success
from app.core.security import get_current_user
from app.modules.graduation.materials import frozen_package_projection as graduation_package
from app.modules.platform_integrity.file_job_service import request_frozen_package_build
from app.modules.platform_integrity.integrity_service import (
    list_integrity_exceptions,
    recheck_integrity_exception,
    record_detector_page,
    run_registered_probe,
    scan_file_binding_page,
    scan_frozen_manifest_page,
    transition_integrity_exception,
)
from app.services.db_service import session
from app.services.message_identity import resolve_message_user_id

router = APIRouter(tags=["PLAT-A·冻结证据与一致性"])

_INTEGRITY_VIEW = require_any_permission(
    "systemAdmin.fileGovernance.view",
    "systemAdmin.audit.view",
)
_INTEGRITY_MANAGE = require_any_permission(
    "systemAdmin.file.manage",
)
_INTEGRITY_SCAN = require_any_permission(
    "systemAdmin.fileGovernance.view",
    "systemAdmin.file.manage",
)
_GRADUATION_PACKAGE = require_any_permission(
    "graduationDesign.archive.view",
    "graduationDesign.archive.file",
    "graduationDesign.archive.export",
)
_GRADUATION_PACKAGE_BUILD = require_any_permission(
    "graduationDesign.archive.file",
    "graduationDesign.archive.export",
)


class IntegrityTransitionBody(BaseModel):
    status: str = Field(..., description="ACKNOWLEDGED/RESOLVED/IGNORED")
    version: int = Field(..., ge=0)
    note: str | None = Field(None, max_length=4000)


class IntegrityScanBody(BaseModel):
    detector: str = Field("ALL", description="ALL/FROZEN_MANIFEST/FILE_BINDING/registered probe code")
    cursor: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=200)
    deepSha: bool = False
    deepShaLimit: int = Field(20, ge=0, le=20)
    timeoutMs: int = Field(2000, ge=100, le=5000)


class IntegrityRecheckBody(BaseModel):
    version: int = Field(..., ge=0)
    timeoutMs: int = Field(2000, ge=100, le=5000)


@router.get("/platform-integrity/exceptions", summary="Staff PC·完整性异常中心（游标分页）")
def integrity_exceptions(
    cursor: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    moduleCode: str | None = Query(None),
    user=Depends(_INTEGRITY_VIEW),
):
    return success(list_integrity_exceptions(
        after_id=cursor,
        limit=limit,
        status=status,
        module_code=moduleCode,
    ))


@router.post("/platform-integrity/exceptions/{exception_id}/status", summary="确认、解决或忽略完整性异常")
def integrity_exception_transition(
    body: IntegrityTransitionBody,
    exception_id: int = Path(..., ge=1),
    user=Depends(_INTEGRITY_MANAGE),
):
    return success(transition_integrity_exception(
        exception_id,
        status=body.status,
        expected_version=body.version,
        actor_id=resolve_message_user_id(user or {}) or None,
        note=body.note,
    ))


@router.post("/platform-integrity/exceptions/{exception_id}/recheck", summary="有界复检单个完整性异常")
def integrity_exception_recheck(
    body: IntegrityRecheckBody,
    exception_id: int = Path(..., ge=1),
    user=Depends(_INTEGRITY_MANAGE),
):
    return success(recheck_integrity_exception(
        exception_id,
        expected_version=body.version,
        actor_id=resolve_message_user_id(user or {}) or None,
        timeout_ms=body.timeoutMs,
    ))


@router.post("/platform-integrity/scans", summary="执行单页有界探测并写入异常读模型")
def integrity_scan(body: IntegrityScanBody, user=Depends(_INTEGRITY_SCAN)):
    tenant_id = int(current_tenant_id() or 0)
    detector = str(body.detector or "ALL").upper()
    pages = []
    with session() as db:
        if detector in {"ALL", "FROZEN_MANIFEST"}:
            pages.append(scan_frozen_manifest_page(
                db,
                tenant_id=tenant_id,
                after_id=body.cursor,
                limit=body.limit,
                deep_sha=body.deepSha,
                deep_sha_limit=body.deepShaLimit,
            ))
        if detector in {"ALL", "FILE_BINDING"}:
            pages.append(scan_file_binding_page(
                db,
                tenant_id=tenant_id,
                after_id=body.cursor,
                limit=body.limit,
            ))
        if detector not in {"ALL", "FROZEN_MANIFEST", "FILE_BINDING"}:
            pages.append(run_registered_probe(
                detector,
                tenant_id=tenant_id,
                after_id=body.cursor,
                limit=body.limit,
                timeout_ms=body.timeoutMs,
            ))
        persisted = sum(len(record_detector_page(db, page)) for page in pages)
        db.commit()
    return success({
        "detectors": [{
            "detectorCode": page.detector_code,
            "probeStatus": page.status,
            "scanned": page.scanned,
            "findingCount": len(page.findings),
            "nextCursor": str(page.next_cursor) if page.next_cursor is not None else None,
            "deepShaScanned": page.deep_sha_scanned,
            "error": page.error,
        } for page in pages],
        "persisted": persisted,
    })


@router.get("/graduation/manifests/{manifest_id}/frozen-package", summary="Staff PC·毕业归档冻结包状态")
def graduation_manifest_package(
    manifest_id: int = Path(..., ge=1),
    user=Depends(_GRADUATION_PACKAGE),
):
    return success(graduation_package.manifest_frozen_package(manifest_id, user))


@router.post("/graduation/manifests/{manifest_id}/frozen-package/build", summary="Staff PC·执行单个冻结包任务")
def graduation_manifest_package_build(
    manifest_id: int = Path(..., ge=1),
    user=Depends(_GRADUATION_PACKAGE_BUILD),
):
    package = graduation_package.manifest_frozen_package(manifest_id, user)
    job = request_frozen_package_build(
        manifest_id=manifest_id,
        profile_code="STANDARD_V1",
    )
    if not package.get("artifact"):
        package["packageStatus"] = job["status"]
    package["jobId"] = job["jobId"]
    return success(package)


@router.get("/portal/graduation/frozen-package", summary="学生 PC·本人冻结证据包")
def portal_my_frozen_package(user=Depends(get_current_user)):
    return success(graduation_package.my_frozen_package(user))


@router.get("/mobile/student/graduation/frozen-package", summary="学生小程序·本人冻结证据包")
def mobile_student_my_frozen_package(user=Depends(get_current_user)):
    return success(graduation_package.my_frozen_package(user))


@router.get("/mobile/teacher/platform-integrity/summary", summary="教师小程序·数据范围内异常摘要")
def mobile_teacher_integrity_summary(
    limit: int = Query(100, ge=1, le=100),
    user=Depends(get_current_user),
):
    return success(graduation_package.teacher_integrity_summary(user, limit=limit))


__all__ = ["router"]
