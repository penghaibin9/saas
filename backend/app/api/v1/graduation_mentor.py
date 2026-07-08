"""毕业设计中心 · 导师管理 + 导师分配 API（/api/v1/graduation/gd-mentors/*，/gd-mentor-assignments/*）。

独立 router；静态子路由（stats/import/export/unassigned-students）在 /{mid} 之前声明。
写操作落审计；Excel 导入接公共底座，台账导出 base64 返回。
"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.excel import ExcelErrorRows, ExcelImportRows
from app.schemas.graduation_mentor import (MentorAssignCancelRequest, MentorAssignRequest,
                                           MentorChangeRequest, MentorCreate, MentorDisableRequest,
                                           MentorReviewRequest, MentorUpdate)
from app.services import audit_log
from app.services import graduation_mentor_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-导师管理与分配"])


# ═══════════ 导师管理 ═══════════

@router.get("/gd-mentors/stats", summary="导师统计（资格分布/容量/未分配学生数）")
def gd_mentor_stats(user=Depends(get_current_user)):
    return success(svc.mentor_stats())


@router.get("/gd-mentors/import/template", summary="导师名单导入·下载 Excel 模板(.xlsx)")
def gd_mentor_import_template(user=Depends(get_current_user)):
    data = svc.import_template_bytes()
    return StreamingResponse(
        io.BytesIO(data), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=gd_mentor_import_template.xlsx"})


@router.post("/gd-mentors/import/xlsx", summary="导师名单导入·上传 Excel 解析+预校验（不写库）")
async def gd_mentor_import_xlsx(file: UploadFile = File(...), user=Depends(get_current_user)):
    content = await file.read()
    rows = svc.import_read(content)
    return success(svc.import_dry_run(rows))


@router.post("/gd-mentors/import/dry-run", summary="导师名单导入·预校验（粘贴行，不写库）")
def gd_mentor_import_dry_run(body: ExcelImportRows, user=Depends(get_current_user)):
    return success(svc.import_dry_run(body.rows))


@router.post("/gd-mentors/import/errors-xlsx", summary="导师名单导入·下载错误行 Excel")
def gd_mentor_import_errors_xlsx(body: ExcelErrorRows, user=Depends(get_current_user)):
    return success(svc.import_errors_pack(body.rows, [e.model_dump() for e in body.errors]))


@router.post("/gd-mentors/import/confirm", summary="导师名单导入·确认（整批事务，须预校验全通过）")
def gd_mentor_import_confirm(body: ExcelImportRows, user=Depends(get_current_user)):
    result = svc.import_confirm(body.rows)
    audit_log.record("导入毕设导师名单", "graduation-mentor:import", detail=result)
    return success(result, message=f"已导入 {result.get('created', 0)} 条")


@router.post("/gd-mentors/export", summary="导出导师名单与工作量台账 Excel（写审计）")
def gd_mentor_export(keyword: Optional[str] = None, qualificationStatus: Optional[str] = None,
                     mentorType: Optional[str] = None, user=Depends(get_current_user)):
    data = svc.export_mentors_xlsx(keyword=keyword, qualification_status=qualificationStatus,
                                   mentor_type=mentorType)
    audit_log.record("导出导师名单台账", "graduation-mentor:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/gd-mentors", summary="导师列表（分页+筛选）")
def gd_mentors(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, qualificationStatus: Optional[str] = None,
              mentorType: Optional[str] = None, hasCapacity: Optional[str] = None,
              user=Depends(get_current_user)):
    items, total = svc.list_mentors(page, pageSize, keyword=keyword,
                                    qualification_status=qualificationStatus, mentor_type=mentorType,
                                    has_capacity=hasCapacity)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-mentors", summary="申报导师（默认待审核）")
def gd_mentor_create(body: MentorCreate, user=Depends(get_current_user)):
    result = svc.create_mentor(body.model_dump())
    audit_log.record("申报毕设导师", f"graduation-mentor:{result['id']}", detail={"teacherName": body.teacherName})
    return success(result, message="已申报，待审核")


@router.get("/gd-mentors/conflicts", summary="分配冲突自动检测（超容量/进阶段无导师/导师非认证）")
def gd_mentor_conflicts(user=Depends(get_current_user)):
    return success(svc.detect_assignment_conflicts())


@router.post("/gd-mentors/batch-assign", summary="批量分配导师（逐条分配，冲突跳过记原因）")
def gd_mentor_batch_assign(body: dict = Body(...), user=Depends(get_current_user)):
    result = svc.batch_assign(body.get("assignments") or [])
    audit_log.record("批量分配导师", "graduation-mentor:batch-assign", detail={"assigned": result["assigned"]})
    return success(result, message=f"已分配 {result['assigned']} 人，跳过 {result['skipped']} 人")


@router.post("/gd-mentors/batch-archive", summary="批量归档导师（仅已停用/驳回且无在指导学生）")
def gd_mentor_batch_archive(body: dict = Body(...), user=Depends(get_current_user)):
    result = svc.batch_archive(body.get("mentorIds") or [])
    audit_log.record("批量归档导师", "graduation-mentor:batch-archive", detail={"archived": result["archived"]})
    return success(result, message=f"已归档 {result['archived']} 个，跳过 {result['skipped']} 个")


@router.get("/gd-mentors/{mid}", summary="导师详情（含在指导学生/审计/最新评价）")
def gd_mentor_detail(mid: str, user=Depends(get_current_user)):
    return success(svc.get_mentor(mid))


@router.put("/gd-mentors/{mid}", summary="编辑导师信息（已停用/已归档不可编辑）")
def gd_mentor_update(mid: str, body: MentorUpdate, user=Depends(get_current_user)):
    result = svc.update_mentor(mid, body.model_dump(exclude_unset=True))
    audit_log.record("编辑导师信息", f"graduation-mentor:{mid}")
    return success(result, message="已保存")


@router.post("/gd-mentors/{mid}/review", summary="审核导师资格（待审核→已认证/已驳回）")
def gd_mentor_review(mid: str, body: MentorReviewRequest, user=Depends(get_current_user)):
    result = svc.review_mentor(mid, body.action, body.comment)
    audit_log.record("审核导师资格", f"graduation-mentor:{mid}", detail={"action": body.action})
    return success(result, message="已审核")


@router.post("/gd-mentors/{mid}/disable", summary="停用导师（原因≥5字）")
def gd_mentor_disable(mid: str, body: MentorDisableRequest, user=Depends(get_current_user)):
    result = svc.disable_mentor(mid, body.reason)
    audit_log.record("停用导师", f"graduation-mentor:{mid}", detail={"reason": body.reason})
    return success(result, message="已停用")


@router.post("/gd-mentors/{mid}/enable", summary="启用导师（已停用→已认证）")
def gd_mentor_enable(mid: str, user=Depends(get_current_user)):
    result = svc.enable_mentor(mid)
    audit_log.record("启用导师", f"graduation-mentor:{mid}")
    return success(result, message="已启用")


@router.post("/gd-mentors/{mid}/archive", summary="归档导师（须无在指导学生）")
def gd_mentor_archive(mid: str, user=Depends(get_current_user)):
    result = svc.archive_mentor(mid)
    audit_log.record("归档导师", f"graduation-mentor:{mid}")
    return success(result, message="已归档")


@router.get("/gd-mentors/{mid}/evals", summary="导师评价历史")
def gd_mentor_evals(mid: str, user=Depends(get_current_user)):
    return success({"items": svc.list_evals(mid)})


@router.post("/gd-mentors/{mid}/evals", summary="新增导师评价（评分0-100+等级+意见）")
def gd_mentor_eval_create(mid: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = svc.create_eval(mid, body.get("score"), body.get("level"), body.get("note"), body.get("period"))
    audit_log.record("导师评价", f"graduation-mentor:{mid}", detail={"level": body.get("level")})
    return success(result, message="已评价")


# ═══════════ 导师分配 ═══════════

@router.get("/gd-mentor-assignments/unassigned-students", summary="未分配导师学生列表")
def gd_mentor_unassigned_students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                                  keyword: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.unassigned_students(page, pageSize, keyword=keyword)
    return success(paginate(items, total, page, pageSize))


@router.get("/gd-mentor-assignments", summary="导师分配记录列表（分页+筛选）")
def gd_mentor_assignments(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                          mentorId: Optional[str] = None, gdStudentId: Optional[str] = None,
                          status: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_assignments(page, pageSize, mentor_id=mentorId, gd_student_id=gdStudentId,
                                        status=status)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-mentor-assignments/assign", summary="分配导师（学生须尚无导师）")
def gd_mentor_assign(body: MentorAssignRequest, user=Depends(get_current_user)):
    result = svc.assign_mentor(body.gdStudentId, body.mentorId, body.reason)
    audit_log.record("分配导师", f"graduation-mentor-assign:{result['id']}",
                     detail={"studentId": body.gdStudentId, "mentorId": body.mentorId})
    return success(result, message="已分配")


@router.post("/gd-mentor-assignments/change", summary="调导师（原因≥5字，学生须已有导师）")
def gd_mentor_change(body: MentorChangeRequest, user=Depends(get_current_user)):
    result = svc.change_mentor(body.gdStudentId, body.newMentorId, body.reason)
    audit_log.record("调导师", f"graduation-mentor-assign:{result['id']}",
                     detail={"studentId": body.gdStudentId, "newMentorId": body.newMentorId,
                             "reason": body.reason})
    return success(result, message="已调整")


@router.post("/gd-mentor-assignments/{aid}/cancel", summary="取消分配（原因≥5字，仅生效中可取消）")
def gd_mentor_assignment_cancel(aid: str, body: MentorAssignCancelRequest, user=Depends(get_current_user)):
    result = svc.cancel_assignment(aid, body.reason)
    audit_log.record("取消导师分配", f"graduation-mentor-assign:{aid}", detail={"reason": body.reason})
    return success(result, message="已取消")
