"""毕业设计中心 · 毕设学生 API（/api/v1/graduation/gd-students/*）。

独立 router，前缀避开旧 /graduation/students/*（保留兼容只读），零路由冲突。
核心：学生-选题分配闭环（回填选题库 selected）+ 节点状态机 + 风险 + 公共 Excel 底座导入导出。
静态子路由（stats/import/export）声明在 /{record_id} 之前。
"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.excel import ExcelErrorRows, ExcelImportRows
from app.modules.graduation.schemas.graduation_student import (AssignAdvisorRequest, AssignTopicRequest, GdStudentBatchArchiveRequest,
                                            GdStudentBatchGroupRequest, GdStudentCreate, GdStudentDefenseGroupRequest,
                                            GdStudentEligibilityRequest, GdStudentGradQualRequest,
                                            GdStudentGroupRequest, GdStudentRiskRequest, GdStudentStageRequest,
                                            GdStudentUpdate, UnassignTopicRequest)
from app.services import audit_log
from app.modules.graduation.services import graduation_student_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-毕设学生"])


@router.get("/gd-students", summary="毕设学生列表（分页+筛选：批次/节点/风险/资格/分组/材料/答辩组/毕业资格/归档）")
def gd_students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                keyword: Optional[str] = None, classId: Optional[str] = None,
                batchId: Optional[str] = None, stage: Optional[str] = None,
                riskLevel: Optional[str] = None, advisorName: Optional[str] = None,
                hasTopic: Optional[bool] = None, eligibility: Optional[str] = None,
                studentGroup: Optional[str] = None, hasDefenseGroup: Optional[bool] = None,
                gradQualStatus: Optional[str] = None, materialComplete: Optional[bool] = None,
                archiveView: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_students(page, pageSize, keyword=keyword, class_id=classId,
                                     batch_id=batchId, stage=stage, risk_level=riskLevel,
                                     advisor_name=advisorName, has_topic=hasTopic,
                                     eligibility=eligibility, student_group=studentGroup,
                                     has_defense_group=hasDefenseGroup, grad_qual_status=gradQualStatus,
                                     material_complete=materialComplete, archive_view=archiveView)
    return success(paginate(items, total, page, pageSize))


@router.get("/gd-students/groups", summary="毕设学生过程分组名称列表（筛选用）")
def gd_student_groups(user=Depends(get_current_user)):
    return success(svc.list_student_groups())


@router.get("/gd-students/stats", summary="毕设学生统计（节点/选题/高风险）")
def gd_student_stats(user=Depends(get_current_user)):
    return success(svc.student_stats())


@router.post("/gd-students/import/dry-run", summary="毕设学生导入·预校验（粘贴行/高级，不写库）")
def gd_import_dry_run(body: ExcelImportRows, user=Depends(get_current_user)):
    return success(svc.import_dry_run(body.rows))


@router.get("/gd-students/import/template", summary="毕设学生导入·下载 Excel 模板(.xlsx)")
def gd_import_template(user=Depends(get_current_user)):
    data = svc.import_template_bytes()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=gd_student_import_template.xlsx"})


@router.post("/gd-students/import/xlsx", summary="毕设学生导入·上传 Excel 解析+预校验（不写库）")
async def gd_import_xlsx(file: UploadFile = File(...), user=Depends(get_current_user)):
    content = await file.read()
    rows = svc.import_read(content)
    dry = svc.import_dry_run(rows)
    return success({"rows": rows, **dry})


@router.post("/gd-students/import/errors-xlsx", summary="毕设学生导入·下载错误行 Excel")
def gd_import_errors_xlsx(body: ExcelErrorRows, user=Depends(get_current_user)):
    return success(svc.import_errors_pack(body.rows, [e.model_dump() for e in body.errors]))


@router.post("/gd-students/import/confirm", summary="毕设学生导入·确认（整批事务，须预校验全通过）")
def gd_import_confirm(body: ExcelImportRows, user=Depends(get_current_user)):
    result = svc.import_confirm(body.rows)
    audit_log.record("导入毕设学生", "graduation-student:import", detail=result)
    return success(result, message="导入完成")


@router.post("/gd-students/export", summary="毕设学生台账导出 Excel（脱敏，写审计）")
def gd_export(keyword: Optional[str] = None, batchId: Optional[str] = None,
              stage: Optional[str] = None, riskLevel: Optional[str] = None,
              user=Depends(get_current_user)):
    data = svc.export_students_xlsx(keyword=keyword, batch_id=batchId, stage=stage, risk_level=riskLevel)
    audit_log.record("导出毕设学生", "graduation-student:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/gd-students", summary="新增毕设学生建档（初始选题中）")
def create_gd_student(body: GdStudentCreate, user=Depends(get_current_user)):
    result = svc.create_student_record(body)
    audit_log.record("新增毕设学生", f"graduation-student:{result['id']}", detail={"studentId": result["studentId"]})
    return success(result, message="已建档")


@router.get("/gd-students/{record_id}", summary="毕设学生详情（批次/选题/材料/审计）")
def gd_student_detail(record_id: str, user=Depends(get_current_user)):
    return success(svc.get_student(record_id))


@router.put("/gd-students/{record_id}", summary="编辑毕设学生（已归档不可编辑）")
def update_gd_student(record_id: str, body: GdStudentUpdate, user=Depends(get_current_user)):
    result = svc.update_student_record(record_id, body)
    audit_log.record("编辑毕设学生", f"graduation-student:{record_id}")
    return success(result, message="已保存")


@router.post("/gd-students/{record_id}/assign-topic", summary="分配选题（校验已确认/满员；回填 selected）")
def assign_topic(record_id: str, body: AssignTopicRequest, user=Depends(get_current_user)):
    result = svc.assign_topic(record_id, body.topicId)
    audit_log.record("分配毕设选题", f"graduation-student:{record_id}", detail={"topicId": body.topicId})
    return success(result, message="已分配选题")


@router.post("/gd-students/{record_id}/unassign-topic", summary="退选（释放选题名额）")
def unassign_topic(record_id: str, body: UnassignTopicRequest, user=Depends(get_current_user)):
    result = svc.unassign_topic(record_id, body.reason or "")
    audit_log.record("毕设退选", f"graduation-student:{record_id}")
    return success(result, message="已退选")


@router.post("/gd-students/{record_id}/assign-advisor", summary="分配指导教师")
def assign_advisor(record_id: str, body: AssignAdvisorRequest, user=Depends(get_current_user)):
    result = svc.assign_advisor(record_id, body.advisorName)
    audit_log.record("分配毕设导师", f"graduation-student:{record_id}", detail={"advisor": body.advisorName})
    return success(result, message="已分配")


@router.post("/gd-students/{record_id}/stage", summary="节点状态机（推进/归档）")
def student_stage(record_id: str, body: GdStudentStageRequest, user=Depends(get_current_user)):
    result = svc.set_stage(record_id, body.action, body.reason or "")
    audit_log.record("毕设节点变更", f"graduation-student:{record_id}", detail={"action": body.action})
    return success(result, message="已更新")


@router.post("/gd-students/{record_id}/risk", summary="风险等级标记")
def student_risk(record_id: str, body: GdStudentRiskRequest, user=Depends(get_current_user)):
    result = svc.set_risk(record_id, body.riskLevel, body.reason or "")
    audit_log.record("毕设风险标记", f"graduation-student:{record_id}", detail={"risk": body.riskLevel})
    return success(result, message="已更新")


@router.post("/gd-students/{record_id}/eligibility", summary="毕设资格认定")
def student_eligibility(record_id: str, body: GdStudentEligibilityRequest, user=Depends(get_current_user)):
    result = svc.set_eligibility(record_id, body.status, body.reason or "")
    audit_log.record("毕设资格认定", f"graduation-student:{record_id}", detail={"status": body.status})
    return success(result, message="已更新")


@router.post("/gd-students/{record_id}/group", summary="设置过程分组")
def student_group(record_id: str, body: GdStudentGroupRequest, user=Depends(get_current_user)):
    result = svc.set_student_group(record_id, body.groupName, body.reason or "")
    audit_log.record("毕设学生分组", f"graduation-student:{record_id}", detail={"group": body.groupName})
    return success(result, message="已更新")


@router.post("/gd-students/batch-group", summary="批量设置过程分组")
def batch_student_group(body: GdStudentBatchGroupRequest, user=Depends(get_current_user)):
    result = svc.batch_set_student_group(body.recordIds, body.groupName, body.reason or "")
    audit_log.record("毕设学生批量分组", "graduation-student:batch-group", detail=result)
    return success(result, message="已更新")


@router.post("/gd-students/{record_id}/defense-group", summary="分配答辩组")
def student_defense_group(record_id: str, body: GdStudentDefenseGroupRequest, user=Depends(get_current_user)):
    result = svc.assign_defense_group(record_id, body.defenseGroupId, body.reason or "")
    audit_log.record("分配答辩组", f"graduation-student:{record_id}", detail={"groupId": body.defenseGroupId})
    return success(result, message="已分配")


@router.post("/gd-students/{record_id}/grad-qual", summary="毕业资格联动状态")
def student_grad_qual(record_id: str, body: GdStudentGradQualRequest, user=Depends(get_current_user)):
    result = svc.set_grad_qual(record_id, body.status, body.note or "", body.reason or "")
    audit_log.record("毕业资格联动", f"graduation-student:{record_id}", detail={"status": body.status})
    return success(result, message="已更新")


@router.post("/gd-students/batch-archive", summary="批量归档毕设学生")
def batch_archive(body: GdStudentBatchArchiveRequest, user=Depends(get_current_user)):
    result = svc.batch_archive(body.recordIds, body.reason or "")
    audit_log.record("毕设学生批量归档", "graduation-student:batch-archive", detail=result)
    return success(result, message="已归档")
