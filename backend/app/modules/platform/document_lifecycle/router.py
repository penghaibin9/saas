"""Private PLAT-C routes; shared registration is deferred to C7."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.response import success
from app.core.security import get_current_user
from app.db.session import get_sessionmaker
from app.modules.platform.document_lifecycle.file_job_dag import enqueue_compare, enqueue_extract
from app.modules.platform.document_lifecycle.document_intelligence_service import (
    compare_result_view,
    extracted_artifact_view,
    job_view,
    version_timeline,
)
from app.modules.platform.document_lifecycle.lifecycle_projection_service import lifecycle_timeline
from app.modules.platform.document_lifecycle.schemas import ComparisonRequest, ExtractionRequest

router = APIRouter(prefix="/platform-c", tags=["PLAT-C 文档智能与生命周期投影"])


@router.post("/document-intelligence/extractions")
def create_extraction(body: ExtractionRequest, user=Depends(get_current_user)):
    row = enqueue_extract(
        file_version_id=body.fileVersionId,
        expected_sha256=body.expectedSha256, user=user,
    )
    return success({"jobId": str(row.id), "status": row.status})


@router.post("/document-intelligence/comparisons")
def create_comparison(body: ComparisonRequest, user=Depends(get_current_user)):
    row = enqueue_compare(
        left_file_version_id=body.leftFileVersionId,
        left_expected_sha256=body.leftExpectedSha256,
        right_file_version_id=body.rightFileVersionId,
        right_expected_sha256=body.rightExpectedSha256, user=user,
    )
    return success({"jobId": str(row.id), "status": row.status})


@router.get("/document-intelligence/jobs/{job_id}")
def get_document_job(job_id: int, user=Depends(get_current_user)):
    db = get_sessionmaker()()
    try:
        return success(job_view(db, job_id=job_id, user=user))
    finally:
        db.close()


@router.get("/document-intelligence/assets/{asset_id}/versions")
def get_version_timeline(asset_id: int, limit: int = Query(50, ge=1, le=100),
                         user=Depends(get_current_user)):
    db = get_sessionmaker()()
    try:
        return success(version_timeline(db, asset_id=asset_id, user=user, limit=limit))
    finally:
        db.close()


@router.get("/document-intelligence/extractions/{artifact_id}")
def get_extraction(artifact_id: int, offset: int = Query(0, ge=0),
                   limit: int = Query(100, ge=1, le=200), user=Depends(get_current_user)):
    db = get_sessionmaker()()
    try:
        return success(extracted_artifact_view(
            db, artifact_id=artifact_id, user=user, offset=offset, limit=limit,
        ))
    finally:
        db.close()


@router.get("/document-intelligence/comparisons/{result_id}")
def get_comparison(result_id: int, offset: int = Query(0, ge=0),
                   limit: int = Query(100, ge=1, le=200), user=Depends(get_current_user)):
    db = get_sessionmaker()()
    try:
        return success(compare_result_view(
            db, result_id=result_id, user=user, offset=offset, limit=limit,
        ))
    finally:
        db.close()


@router.get("/students/{student_id}/lifecycle")
def student_lifecycle(student_id: int, sourceModule: str | None = Query(None),
                      cursor: str | None = Query(None), pageSize: int = Query(20, ge=1, le=100),
                      user=Depends(get_current_user)):
    db = get_sessionmaker()()
    try:
        return success(lifecycle_timeline(
            db, student_id=student_id, user=user, source_module=sourceModule,
            cursor=cursor, page_size=pageSize,
        ))
    finally:
        db.close()
