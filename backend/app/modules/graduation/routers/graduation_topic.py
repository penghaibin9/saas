"""毕业设计中心 · 题目库 API（/api/v1/graduation/gd-topics/*）。

独立 router；静态子路由（stats/import/export）在 /{topic_id} 之前声明。
旧 /graduation/topics 只读列表保留兼容。
"""
from __future__ import annotations

import hashlib
import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.core.permissions import require_permission
from app.schemas.excel import ExcelErrorRows, ExcelImportRows
from app.modules.graduation.schemas.graduation_topic import (GdTopicArchiveRequest, GdTopicAttachmentsUpdate, GdTopicCapacityUpdate,
                                          GdTopicCreate, GdTopicDisableRequest, GdTopicReviewRequest, GdTopicUpdate)
from app.services import audit_log
from app.services import xlsx_util
from app.modules.graduation.services import graduation_topic_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-题目库"])


@router.get("/gd-topics/stats", summary="题目库统计（含分类/容量/缺口）")
def gd_topic_stats(batchId: int | None = Query(default=None, ge=1),
                   user=Depends(get_current_user)):
    return success(svc.topic_stats(batch_id=batchId))


@router.get("/gd-topics/category-stats", summary="题目分类统计")
def gd_topic_category_stats(batchId: int | None = Query(default=None, ge=1),
                            user=Depends(get_current_user)):
    return success(svc.category_stats(batch_id=batchId))


@router.get("/gd-topics/history", summary="题目操作历史（审计链）")
def gd_topic_history(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                     keyword: Optional[str] = None, topicId: Optional[str] = None,
                     action: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_topic_history(page, pageSize, keyword=keyword, topic_id=topicId, action=action)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-topics/history/export", summary="题目操作历史导出 Excel（写审计）")
def gd_topic_history_export(keyword: Optional[str] = None, topicId: Optional[str] = None,
                            action: Optional[str] = None, user=Depends(get_current_user)):
    data = svc.export_topic_history_xlsx(keyword=keyword, topic_id=topicId, action=action)
    audit_log.record("导出题目操作历史", "graduation-topic:history-export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/gd-topics/import/dry-run", summary="题目库导入·预校验（粘贴行/高级，不写库）")
def gd_topic_import_dry_run(body: ExcelImportRows, user=Depends(get_current_user)):
    return success(svc.import_dry_run(body.rows))


@router.get("/gd-topics/import/template", summary="题目库导入·下载 Excel 模板(.xlsx)")
def gd_topic_import_template(user=Depends(get_current_user)):
    data = svc.import_template_bytes()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=gd_topic_import_template.xlsx"})


@router.post("/gd-topics/import/xlsx", summary="题目库导入·上传 Excel 解析+预校验（不写库）")
async def gd_topic_import_xlsx(file: UploadFile = File(...), user=Depends(get_current_user)):
    content = await xlsx_util.read_safe_upload(file)
    rows = svc.import_read(content)
    dry = svc.import_dry_run(rows, {
        "fileName": file.filename or "upload.xlsx",
        "fileSha256": hashlib.sha256(content).hexdigest(),
    })
    return success({"rows": rows, **dry})


@router.post("/gd-topics/import/errors-xlsx", summary="题目库导入·下载错误行 Excel")
def gd_topic_import_errors_xlsx(body: ExcelErrorRows, user=Depends(get_current_user)):
    return success(svc.import_errors_pack(body.rows, [e.model_dump() for e in body.errors]))


@router.post("/gd-topics/import/confirm", summary="题目库导入·确认（整批事务，须预校验全通过）")
def gd_topic_import_confirm(body: ExcelImportRows, user=Depends(get_current_user)):
    result = svc.import_confirm(body.rows, body.previewToken)
    audit_log.record("导入毕设题目", "graduation-topic:import", detail=result)
    return success(result, message="导入完成")


@router.post("/gd-topics/export", summary="题目库台账导出 Excel（写审计）")
def gd_topic_export(keyword: Optional[str] = None, batchId: Optional[str] = None,
                    sourceType: Optional[str] = None, category: Optional[str] = None,
                    reviewStatus: Optional[str] = None, status: Optional[str] = None,
              isFull: Optional[bool] = None, archiveView: Optional[str] = None,
              hasRequirements: Optional[bool] = None, hasAttachments: Optional[bool] = None,
              missingCategory: Optional[bool] = None,
              user=Depends(get_current_user)):
    data = svc.export_topics_xlsx(keyword=keyword, batch_id=batchId, source_type=sourceType,
                                  category=category, review_status=reviewStatus, status=status,
                                  is_full=isFull, archive_view=archiveView,
                                  has_requirements=hasRequirements, has_attachments=hasAttachments,
                                  missing_category=missingCategory)
    audit_log.record("导出题目库台账", "graduation-topic:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/gd-topics", summary="题目库列表（分页+筛选）")
def gd_topics(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, batchId: Optional[str] = None,
              sourceType: Optional[str] = None, category: Optional[str] = None,
              reviewStatus: Optional[str] = None, status: Optional[str] = None,
              isFull: Optional[bool] = None, archiveView: Optional[str] = None,
              hasRequirements: Optional[bool] = None, hasAttachments: Optional[bool] = None,
              missingCategory: Optional[bool] = None,
              user=Depends(get_current_user)):
    items, total = svc.list_topics(page, pageSize, keyword=keyword, batch_id=batchId,
                                   source_type=sourceType, category=category,
                                   review_status=reviewStatus, status=status,
                                   is_full=isFull, archive_view=archiveView,
                                   has_requirements=hasRequirements, has_attachments=hasAttachments,
                                   missing_category=missingCategory)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-topics", summary="申报题目（默认草稿，可创建并提交审核）")
def create_gd_topic(body: GdTopicCreate, user=Depends(get_current_user)):
    result = svc.create_topic(body)
    audit_log.record("申报毕设题目", f"graduation-topic:{result['id']}", detail={"title": result["title"]})
    return success(result, message="已保存")


@router.get("/gd-topics/{topic_id}", summary="题目详情（要求/附件/已选学生/审计）")
def gd_topic_detail(topic_id: str, user=Depends(get_current_user)):
    return success(svc.get_topic(topic_id))


@router.get("/gd-topics/{topic_id}/assigned-students", summary="已选学生列表")
def gd_topic_assigned_students(topic_id: str, user=Depends(get_current_user)):
    return success(svc.list_assigned_students(topic_id))


@router.put("/gd-topics/{topic_id}/attachments", summary="维护题目附件元数据")
def update_gd_topic_attachments(topic_id: str, body: GdTopicAttachmentsUpdate, user=Depends(get_current_user)):
    result = svc.update_attachments(topic_id, body.attachments)
    audit_log.record("维护题目附件", f"graduation-topic:{topic_id}", detail={"count": len(body.attachments or [])})
    return success(result, message="附件已保存")


@router.put("/gd-topics/{topic_id}/capacity", summary="调整题目容量")
def update_gd_topic_capacity(topic_id: str, body: GdTopicCapacityUpdate, user=Depends(get_current_user)):
    result = svc.update_capacity(topic_id, body.capacity)
    audit_log.record("调整题目容量", f"graduation-topic:{topic_id}", detail={"capacity": body.capacity})
    return success(result, message="容量已更新")


@router.put("/gd-topics/{topic_id}", summary="编辑题目（已入池且有学生不可改）")
def update_gd_topic(topic_id: str, body: GdTopicUpdate, user=Depends(get_current_user)):
    result = svc.update_topic(topic_id, body)
    audit_log.record("编辑毕设题目", f"graduation-topic:{topic_id}")
    return success(result, message="已保存")


@router.post("/gd-topics/{topic_id}/submit-review", summary="提交审核")
def submit_gd_topic_review(topic_id: str, user=Depends(require_permission("graduationDesign.topic.submit"))):
    result = svc.submit_review(topic_id)
    audit_log.record("提交题目审核", f"graduation-topic:{topic_id}")
    return success(result, message="已提交审核")


@router.post("/gd-topics/{topic_id}/review", summary="审核题目（通过/驳回，驳回≥5字）")
def review_gd_topic(topic_id: str, body: GdTopicReviewRequest, user=Depends(require_permission("graduationDesign.topic.review"))):
    result = svc.review_topic(topic_id, body.action, body.comment or "")
    audit_log.record("审核毕设题目", f"graduation-topic:{topic_id}", detail={"action": body.action})
    return success(result, message="已审核")


@router.post("/gd-topics/{topic_id}/disable", summary="停用题目（已选学生不受影响）")
def disable_gd_topic(topic_id: str, body: GdTopicDisableRequest, user=Depends(get_current_user)):
    result = svc.disable_topic(topic_id, body.reason)
    audit_log.record("停用毕设题目", f"graduation-topic:{topic_id}", detail={"reason": body.reason})
    return success(result, message="已停用")


@router.post("/gd-topics/{topic_id}/enable", summary="启用题目")
def enable_gd_topic(topic_id: str, user=Depends(get_current_user)):
    result = svc.enable_topic(topic_id)
    audit_log.record("启用毕设题目", f"graduation-topic:{topic_id}")
    return success(result, message="已启用")


@router.post("/gd-topics/{topic_id}/archive", summary="归档题目（须无关联学生）")
def archive_gd_topic(topic_id: str, body: GdTopicArchiveRequest, user=Depends(get_current_user)):
    result = svc.archive_topic(topic_id, body.reason or "")
    audit_log.record("归档毕设题目", f"graduation-topic:{topic_id}")
    return success(result, message="已归档")
