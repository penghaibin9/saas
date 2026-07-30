"""阶段 6：毕业设计材料中心与旧路径优先接管 Router。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.core.permissions import has_permission, require_permission
from app.core.response import success
from app.core.security import get_current_user
from app.models import GraduationArchiveRecord, GraduationStudent
from app.modules.graduation.schemas.graduation import ReviewBody
from app.modules.graduation.schemas.graduation_archive import ArchiveFileRequest
from app.modules.graduation.services import graduation_material_catalog_service as catalog
from app.modules.graduation.services import graduation_material_center_service as center
from app.modules.graduation.services import graduation_material_delivery_service as archive_export
from app.modules.graduation.services import graduation_material_ticket_service as tickets
from app.services import audit_log
from app.services.data_exchange_job_service import create_download_ticket, revoke_export_job
from app.services.db_service import _tid, session

router = APIRouter(prefix="/graduation", tags=["毕业设计-材料版本中心"])


def _require_material_manager(user=Depends(get_current_user)):
    if not any(has_permission(user or {}, code) for code in (
        "graduationDesign.material.manage",
        "graduationDesign.riskArchive.manage",
        "graduationDesign.template.manage",
        "graduationDesign.student.manage",
    )):
        raise not_found("毕业设计材料不存在")
    return user


def _require_material_reviewer(user=Depends(get_current_user)):
    if not any(has_permission(user or {}, code) for code in (
        "graduationDesign.proposal.review",
        "graduationDesign.final.review",
        "graduationDesign.review.submit",
        "graduationDesign.defense.scoreConfirm",
        "graduationDesign.grade.review",
        "graduationDesign.riskArchive.manage",
    )):
        raise not_found("毕业设计材料不存在")
    return user


@router.get("/material-center/rules", summary="毕业设计材料规则与材料项")
def material_rules(batchId: int | None = Query(default=None, ge=1), user=Depends(get_current_user)):
    return success(catalog.list_rules(batch_id=batchId, user=user))


@router.post("/material-center/rules", summary="创建毕业设计材料规则新版本")
def create_material_rule(body: dict = Body(...), user=Depends(_require_material_manager)):
    result = center.create_rule(body or {}, user)
    return success(result, message="材料规则草稿已创建")


@router.post("/material-center/rules/{rule_id}/activate", summary="启用毕业设计材料规则")
def activate_material_rule(rule_id: int, user=Depends(_require_material_manager)):
    result = center.activate_rule(rule_id, user)
    return success(result, message="材料规则已启用")


@router.get("/material-center/overview", summary="毕业设计学生材料总览")
def material_overview(
    batchId: int = Query(..., ge=1), page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100), collegeId: str = Query(default=""),
    majorId: str = Query(default=""), classId: str = Query(default=""),
    advisor: str = Query(default=""), keyword: str = Query(default=""),
    stage: str = Query(default=""), materialCode: str = Query(default=""),
    missingStatus: str = Query(default=""), scanStatus: str = Query(default=""),
    reviewStatus: str = Query(default=""), archiveStatus: str = Query(default=""),
    user=Depends(get_current_user),
):
    return success(catalog.material_overview(
        user, batch_id=batchId, page=page, page_size=pageSize,
        college_id=collegeId, major_id=majorId, class_id=classId,
        advisor=advisor, keyword=keyword, stage=stage, material_code=materialCode,
        missing_status=missingStatus, scan_status=scanStatus,
        review_status=reviewStatus, archive_status=archiveStatus,
    ))


@router.post("/material-center/backfill", summary="分页回填旧毕业设计 attachments_json")
def backfill_materials(body: dict = Body(default={}), user=Depends(_require_material_manager)):
    payload = body or {}
    result = catalog.backfill_legacy(
        user, page_size=int(payload.get("pageSize") or payload.get("limit") or 200),
        cursor_model=str(payload.get("cursorModel") or "PROPOSAL"),
        cursor_id=int(payload.get("cursorId") or 0), dry_run=bool(payload.get("dryRun", False)),
    )
    return success(result, message="旧毕业设计材料回填页已处理")


@router.get("/material-center/students/{gd_student_id}/library", summary="学生毕业设计材料库")
def material_library(
    gd_student_id: int, includeHistory: bool = Query(default=True),
    user=Depends(get_current_user),
):
    return success(catalog.student_library(gd_student_id, user, include_history=includeHistory))


@router.post("/material-center/materials/{material_code}/submit", summary="学生提交或重交材料新版本")
def submit_material(
    material_code: str, body: dict = Body(...), user=Depends(get_current_user),
):
    spec = catalog.SPEC_BY_CODE.get(str(material_code or "").upper())
    if not spec:
        raise AppException("VALIDATION_ERROR", "未知毕业设计材料代码")
    if str((user or {}).get("userType") or "").upper() == "STUDENT" and spec["ownerRole"] != "STUDENT":
        raise not_found("毕业设计材料不存在")
    file_id = (body or {}).get("fileId")
    if not str(file_id or "").isdigit():
        raise AppException("VALIDATION_ERROR", "fileId 不能为空")
    expected = (body or {}).get("expectedVersion")
    result = catalog.submit_material(
        user, material_code, int(file_id),
        expected_version=int(expected) if str(expected or "").isdigit() else None,
    )
    return success(result, message="材料新版本已提交")


@router.post("/material-center/materials/{material_id}/review", summary="审核具体文件版本")
def review_material_item(
    material_id: int, body: dict = Body(...),
    user=Depends(_require_material_reviewer),
):
    version_id = (body or {}).get("fileVersionId") or (body or {}).get("versionId")
    if not str(version_id or "").isdigit():
        raise AppException("VALIDATION_ERROR", "fileVersionId 不能为空")
    result = catalog.review_material(
        material_id, int(version_id), str((body or {}).get("action") or ""),
        (body or {}).get("comment"), user,
    )
    return success(result, message="材料版本已审核")


@router.get("/material-center/proposals/{proposal_id}/versions", summary="开题公共版本时间线")
def proposal_versions(proposal_id: int, user=Depends(get_current_user)):
    items = center.record_versions("PROPOSAL", proposal_id)
    return success({"items": items, "total": len(items)})


@router.get("/material-center/finals/{final_id}/versions", summary="成果公共版本时间线")
def final_versions(final_id: int, user=Depends(get_current_user)):
    items = center.record_versions("FINAL", final_id)
    return success({"items": items, "total": len(items)})


@router.get("/material-center/templates", summary="毕业设计模板资产与版本目录")
def template_catalog(batchId: int | None = Query(default=None, ge=1), user=Depends(get_current_user)):
    return success(catalog.template_catalog(user, batch_id=batchId))


@router.post("/material-center/templates/{template_id}/asset", summary="发布模板文件资产新版本")
def publish_template_asset(
    template_id: int, body: dict = Body(default={}), user=Depends(_require_material_manager),
):
    raw = (body or {}).get("fileId")
    file_id = int(raw) if str(raw or "").isdigit() else None
    if not file_id:
        raise AppException("VALIDATION_ERROR", "模板 fileId 不能为空")
    return success(catalog.publish_template_policy(template_id, file_id, body or {}, user), message="模板资产版本已发布")


@router.post("/material-center/templates/policies/{policy_id}/status", summary="启用或停用模板资产策略")
def update_template_status(policy_id: int, body: dict = Body(...), user=Depends(_require_material_manager)):
    enabled = bool((body or {}).get("enabled"))
    expected = (body or {}).get("expectedVersion")
    if not str(expected or "").isdigit():
        raise AppException("VALIDATION_ERROR", "expectedVersion 不能为空")
    return success(catalog.update_template_policy_status(
        policy_id, enabled, int(expected), user,
    ), message="模板状态已更新")


@router.get("/material-center/templates/{template_id}/versions", summary="模板资产版本历史")
def template_versions(template_id: int, user=Depends(get_current_user)):
    return success(center.template_versions(template_id))


@router.get("/material-center/archives/{gd_student_id}/manifest", summary="毕业设计真实归档 Manifest")
def archive_manifest(gd_student_id: int, user=Depends(get_current_user)):
    return success(archive_export.latest_manifest(gd_student_id, user))


@router.post("/material-center/archives/{gd_student_id}/manifest", summary="冻结毕业设计完整真实版本 Manifest")
def freeze_archive_manifest(
    gd_student_id: int, body: dict = Body(default={}), user=Depends(_require_material_manager),
):
    archive_no = str((body or {}).get("archiveBatchNo") or f"GDARCH-{gd_student_id}").strip()
    return success(archive_export.freeze_manifest(gd_student_id, archive_no, user), message="真实版本 Manifest 已冻结")


@router.post("/material-center/archives/{gd_student_id}/revoke", summary="撤销归档并失效旧导出任务")
def revoke_archive_manifest(
    gd_student_id: int, body: dict = Body(...), user=Depends(_require_material_manager),
):
    return success(archive_export.revoke_manifest(gd_student_id, str((body or {}).get("reason") or ""), user),
                   message="归档已撤销，旧 ZIP 和票据已失效")


@router.post("/material-center/exports", summary="创建毕业设计 ZIP/XLSX 导出任务")
def create_archive_export(body: dict = Body(...), user=Depends(_require_material_manager)):
    payload = body or {}
    batch_id = payload.get("batchId")
    if not str(batch_id or "").isdigit():
        raise AppException("VALIDATION_ERROR", "batchId 不能为空")
    job = archive_export.create_export_job(
        batch_id=int(batch_id), scope_type=str(payload.get("scopeType") or "BATCH"),
        scope_value=str(payload.get("scopeValue") or ""), user=user,
    )
    return success(job, message="毕业设计归档任务已创建，可刷新或执行任务")


@router.get("/material-center/exports/{job_id}", summary="查询毕业设计归档任务")
def archive_export_job(job_id: int, user=Depends(get_current_user)):
    return success(archive_export.get_export_job(job_id, user))


@router.post("/material-center/exports/{job_id}/retry", summary="执行或重试毕业设计归档任务")
def retry_archive_export(job_id: int, user=Depends(_require_material_manager)):
    return success(archive_export.run_export_job(job_id, user), message="归档任务已执行")


@router.post("/material-center/exports/{job_id}/ticket", summary="创建短时一次性导出下载票据")
def archive_export_ticket(job_id: int, body: dict = Body(...), user=Depends(get_current_user)):
    return success(create_download_ticket(
        str(job_id), expected_version=int((body or {}).get("expectedVersion") or -1), user=user,
    ))


@router.post("/material-center/exports/{job_id}/revoke", summary="撤销毕业设计导出任务")
def revoke_archive_export(
    job_id: int, body: dict = Body(...), user=Depends(_require_material_manager),
):
    return success(revoke_export_job(
        str(job_id), expected_version=int((body or {}).get("expectedVersion") or -1),
        reason=str((body or {}).get("reason") or ""), user=user,
    ), message="导出任务已撤销")


@router.post("/material-center/archives/{gd_student_id}/package", summary="创建单学生 ExportJob 归档包")
def archive_package(gd_student_id: int, user=Depends(_require_material_manager)):
    with session() as db:
        student = db.get(GraduationStudent, int(gd_student_id))
        if not student or student.tenant_id != _tid() or student.is_deleted:
            raise not_found("毕业设计学生不存在")
        batch_id = int(student.batch_id or 0)
    job = archive_export.create_export_job(
        batch_id=batch_id, scope_type="STUDENT", scope_value=str(gd_student_id), user=user,
    )
    return success(job, message="学生归档任务已创建")


@router.post("/material-center/batches/{batch_id}/package", summary="创建批次 ExportJob ZIP 与 XLSX")
def batch_archive_package(batch_id: int, user=Depends(_require_material_manager)):
    job = archive_export.create_export_job(batch_id=batch_id, scope_type="BATCH", scope_value="", user=user)
    return success(job, message="批次归档任务已创建")


@router.post("/material-center/files/{file_id}/ticket", summary="签发毕业设计材料预览/下载票据")
def material_file_ticket(file_id: int, body: dict = Body(...), user=Depends(get_current_user)):
    return success(tickets.issue_ticket(file_id, str((body or {}).get("action") or "preview"), user))


@router.get("/material-center/files/{file_id}/preview", summary="使用短时票据预览当前安全材料")
def preview_material(file_id: int, ticket: str = Query(...), user=Depends(get_current_user)):
    path, filename = tickets.consume_ticket(file_id, "preview", ticket, user)
    audit_log.record("GRADUATION_VERSIONED_MATERIAL_PREVIEW", f"graduation-file:{file_id}")
    response = FileResponse(str(path), filename=filename, content_disposition_type="inline")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@router.get("/material-center/files/{file_id}/download", summary="下载当前安全材料版本（旧 URL 兼容）")
def download_material(
    file_id: int, ticket: str = Query(default=""), user=Depends(get_current_user),
):
    path, filename = (
        tickets.consume_ticket(file_id, "download", ticket, user)
        if ticket else center.resolve_material_download(file_id, user, student_mode=False)
    )
    audit_log.record("GRADUATION_VERSIONED_MATERIAL_DOWNLOAD", f"graduation-file:{file_id}")
    response = FileResponse(str(path), filename=filename, content_disposition_type="attachment")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@router.get("/material-center/packages/{file_id}/download", summary="旧毕业设计归档 ZIP/Excel 下载兼容")
def download_package(file_id: int, user=Depends(get_current_user)):
    path, filename = center.resolve_package_download(file_id, user)
    audit_log.record("GRADUATION_ARCHIVE_PACKAGE_DOWNLOAD", f"graduation-package:{file_id}")
    response = FileResponse(str(path), filename=filename, content_disposition_type="attachment")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


# 下列同 URL 路由必须先于旧 Router 注册，使正式审核和备案直接受公共版本门禁保护。
@router.get("/proposals/{proposal_id}", summary="开题批阅详情（含当前安全公共版本）")
def proposal_detail(proposal_id: int, user=Depends(get_current_user)):
    return success(center.proposal_detail(proposal_id))


@router.post("/proposals/{proposal_id}/review", summary="批阅开题（锁定当前安全版本）")
def review_proposal(
    proposal_id: int, body: ReviewBody,
    user=Depends(require_permission("graduationDesign.proposal.review")),
):
    result = center.review_proposal(proposal_id, body.action, body.comment, user)
    catalog.sync_record("PROPOSAL", proposal_id, user)
    return success(result, message="已批阅")


@router.get("/finals/{final_id}", summary="成果批阅详情（含当前安全公共版本）")
def final_detail(final_id: int, user=Depends(get_current_user)):
    return success(center.final_detail(final_id))


@router.post("/finals/{final_id}/review", summary="批阅成果（锁定当前安全版本）")
def review_final(
    final_id: int, body: ReviewBody,
    user=Depends(require_permission("graduationDesign.final.review")),
):
    result = center.review_final(final_id, body.action, body.comment, user)
    catalog.sync_record("FINAL", final_id, user)
    return success(result, message="已批阅")


# 固定批量路径必须位于 /{gd_student_id} 动态路径之前。
@router.post("/gd-archives/batch-file", summary="批量备案并冻结完整真实文件版本 Manifest")
def batch_file(
    batchId: int = Query(..., ge=1), body: dict = Body(...),
    user=Depends(_require_material_manager),
):
    archive_no = str((body or {}).get("archiveBatchNo") or "").strip()
    preview_token = str((body or {}).get("previewToken") or "").strip()
    if not preview_token:
        raise AppException("VALIDATION_ERROR", "执行前必须先完成归档预览")
    legacy_result = center.batch_file(archive_no or None, batchId, preview_token, user)
    archive_no = str(legacy_result.get("archiveBatchNo") or archive_no).strip()
    with session() as db:
        student_ids = list(db.scalars(select(GraduationStudent.id).join(
            GraduationArchiveRecord,
            GraduationArchiveRecord.gd_student_id == GraduationStudent.id,
        ).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(batchId),
            GraduationStudent.is_deleted.is_(False),
            GraduationArchiveRecord.tenant_id == _tid(),
            GraduationArchiveRecord.archive_batch_no == archive_no,
            GraduationArchiveRecord.status == "FILED",
            GraduationArchiveRecord.is_deleted.is_(False),
        )).all())
    manifests = [archive_export.freeze_manifest(int(student_id), archive_no, user) for student_id in student_ids]
    return success({**legacy_result, "completeManifestIds": [item["manifestId"] for item in manifests]},
                   message=f"已备案 {legacy_result['filed']} 份并冻结完整 Manifest")


@router.post("/gd-archives/{gd_student_id}/file", summary="核验备案并冻结完整真实版本 Manifest")
def file_archive(
    gd_student_id: int, body: ArchiveFileRequest,
    batchId: int = Query(..., ge=1), user=Depends(_require_material_manager),
):
    center.file_archive(gd_student_id, body.archiveBatchNo, user)
    result = archive_export.freeze_manifest(gd_student_id, body.archiveBatchNo, user)
    return success(result, message="已备案并冻结完整真实版本清单")
