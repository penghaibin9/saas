"""阶段 6：毕业设计材料中心与旧路径优先接管 Router。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import FileResponse

from app.core.exceptions import AppException
from app.core.permissions import require_permission
from app.core.response import success
from app.core.security import get_current_user
from app.modules.graduation.schemas.graduation import ReviewBody
from app.modules.graduation.schemas.graduation_archive import ArchiveFileRequest
from app.modules.graduation.services import graduation_material_center_service as center
from app.services import audit_log

router = APIRouter(prefix="/graduation", tags=["毕业设计-材料版本中心"])


@router.get("/material-center/rules", summary="毕业设计材料规则与材料项")
def material_rules(batchId: int | None = Query(default=None, ge=1), user=Depends(get_current_user)):
    return success(center.list_rules(batch_id=batchId))


@router.post("/material-center/rules", summary="创建毕业设计材料规则新版本")
def create_material_rule(body: dict = Body(...), user=Depends(get_current_user)):
    return success(center.create_rule(body or {}, user), message="材料规则草稿已创建")


@router.post("/material-center/rules/{rule_id}/activate", summary="启用毕业设计材料规则")
def activate_material_rule(rule_id: int, user=Depends(get_current_user)):
    return success(center.activate_rule(rule_id, user), message="材料规则已启用")


@router.post("/material-center/backfill", summary="回填旧开题/成果 attachments_json 到公共版本链")
def backfill_materials(body: dict = Body(default={}), user=Depends(get_current_user)):
    result = center.backfill_legacy(user, limit=int((body or {}).get("limit") or 500))
    return success(result, message="旧毕业设计材料回填完成")


@router.get("/material-center/students/{gd_student_id}/library", summary="学生毕业设计材料库")
def material_library(
    gd_student_id: int,
    includeHistory: bool = Query(default=True),
    user=Depends(get_current_user),
):
    return success(center.student_material_library(
        gd_student_id, user, include_history=includeHistory,
    ))


@router.get("/material-center/proposals/{proposal_id}/versions", summary="开题公共版本时间线")
def proposal_versions(proposal_id: int, user=Depends(get_current_user)):
    return success({"items": center.record_versions("PROPOSAL", proposal_id),
                    "total": len(center.record_versions("PROPOSAL", proposal_id))})


@router.get("/material-center/finals/{final_id}/versions", summary="成果公共版本时间线")
def final_versions(final_id: int, user=Depends(get_current_user)):
    items = center.record_versions("FINAL", final_id)
    return success({"items": items, "total": len(items)})


@router.post("/material-center/templates/{template_id}/asset", summary="发布模板文件资产新版本")
def publish_template_asset(template_id: int, body: dict = Body(default={}), user=Depends(get_current_user)):
    raw = (body or {}).get("fileId")
    file_id = int(raw) if str(raw or "").isdigit() else None
    return success(center.publish_template_asset(template_id, file_id, user), message="模板资产版本已发布")


@router.get("/material-center/templates/{template_id}/versions", summary="模板资产版本历史")
def template_versions(template_id: int, user=Depends(get_current_user)):
    return success(center.template_versions(template_id))


@router.get("/material-center/archives/{gd_student_id}/manifest", summary="毕业设计真实归档 Manifest")
def archive_manifest(gd_student_id: int, user=Depends(get_current_user)):
    return success(center.get_manifest(gd_student_id, user))


@router.post("/material-center/archives/{gd_student_id}/package", summary="生成单个学生真实版本归档 ZIP")
def archive_package(gd_student_id: int, user=Depends(get_current_user)):
    return success(center.build_student_package(gd_student_id, user), message="毕业设计归档包已生成")


@router.post("/material-center/batches/{batch_id}/package", summary="生成批次真实版本 ZIP 与 Excel 索引")
def batch_archive_package(batch_id: int, user=Depends(get_current_user)):
    return success(center.build_batch_package(batch_id, user), message="批次归档 ZIP 与 Excel 已生成")


@router.get("/material-center/files/{file_id}/download", summary="审核预览/下载当前安全材料版本")
def download_material(file_id: int, user=Depends(get_current_user)):
    path, filename = center.resolve_material_download(file_id, user, student_mode=False)
    audit_log.record("GRADUATION_VERSIONED_MATERIAL_DOWNLOAD", f"graduation-file:{file_id}")
    response = FileResponse(str(path), filename=filename, content_disposition_type="attachment")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@router.get("/material-center/packages/{file_id}/download", summary="下载毕业设计归档 ZIP/Excel")
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
    proposal_id: int,
    body: ReviewBody,
    user=Depends(require_permission("graduationDesign.proposal.review")),
):
    return success(center.review_proposal(proposal_id, body.action, body.comment, user), message="已批阅")


@router.get("/finals/{final_id}", summary="成果批阅详情（含当前安全公共版本）")
def final_detail(final_id: int, user=Depends(get_current_user)):
    return success(center.final_detail(final_id))


@router.post("/finals/{final_id}/review", summary="批阅成果（锁定当前安全版本）")
def review_final(
    final_id: int,
    body: ReviewBody,
    user=Depends(require_permission("graduationDesign.final.review")),
):
    return success(center.review_final(final_id, body.action, body.comment, user), message="已批阅")


# 固定批量路径必须位于 /{gd_student_id} 动态路径之前。
@router.post("/gd-archives/batch-file", summary="批量备案并冻结真实文件版本 Manifest")
def batch_file(
    batchId: int = Query(..., ge=1),
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    archive_no = str((body or {}).get("archiveBatchNo") or "").strip()
    preview_token = str((body or {}).get("previewToken") or "").strip()
    if not archive_no or not preview_token:
        raise AppException("VALIDATION_ERROR", "归档批次号和预览凭证不能为空")
    result = center.batch_file(archive_no, batchId, preview_token, user)
    return success(result, message=f"已备案 {result['filed']} 份并冻结 Manifest")


@router.post("/gd-archives/{gd_student_id}/file", summary="核验备案并冻结真实文件版本 Manifest")
def file_archive(
    gd_student_id: int,
    body: ArchiveFileRequest,
    batchId: int = Query(..., ge=1),
    user=Depends(get_current_user),
):
    # batchId 仍由全局毕业设计权限门和 Student scope 共同校验；服务再次校验学生范围。
    result = center.file_archive(gd_student_id, body.archiveBatchNo, user)
    return success(result, message="已备案并冻结真实版本清单")
