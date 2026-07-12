"""岗位实习中心 · 实习学生 API（/api/v1/internship/intern-students/*）。

独立 router，前缀避开旧 /internship/students/*（保留兼容），零路由冲突。
核心：学生-岗位分配闭环（回填岗位库 allocated_count）+ 状态机 + 资格 + 去向 + 导入导出。
静态子路由（stats/import/export）声明在 /{record_id} 之前。
"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.internship.schemas.internship_student import (AssignPositionRequest, DestinationRequest,
                                            EligibilityRequest, StudentImport,
                                            StudentRecordCreate, StudentRecordUpdate,
                                            StudentStatusRequest, UnassignRequest)
from app.services import audit_log
from app.modules.internship.services import internship_student_service as svc
from app.services import xlsx_util

router = APIRouter(prefix="/internship", tags=["岗位实习-实习学生"])
_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/intern-students", summary="实习学生列表（分页+筛选：状态/资格/去向/是否已分配岗位）")
def intern_students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                    keyword: Optional[str] = None, classId: Optional[str] = None,
                    status: Optional[str] = None, riskLevel: Optional[str] = None,
                    eligibility: Optional[str] = None, destination: Optional[str] = None,
                    hasPosition: Optional[bool] = None, user=Depends(get_current_user)):
    items, total = svc.list_students(page, pageSize, keyword=keyword, class_id=classId,
                                     status=status, risk_level=riskLevel, eligibility=eligibility,
                                     destination=destination, has_position=hasPosition, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/intern-students/stats", summary="实习学生统计（状态/是否分配/资格）")
def intern_student_stats(user=Depends(get_current_user)):
    return success(svc.student_stats())


@router.post("/intern-students/import/dry-run", summary="按学号建档·预校验（不写库）")
def intern_import_dry_run(body: StudentImport, user=Depends(get_current_user)):
    return success(svc.import_dry_run(body.rows))


@router.post("/intern-students/import/confirm", summary="按学号建档·确认（整批事务）")
def intern_import_confirm(body: StudentImport, user=Depends(get_current_user)):
    result = svc.import_confirm(body.rows)
    audit_log.record("导入实习学生", "internship-student:import", detail=result)
    return success(result, message="导入完成")


@router.get("/intern-students/import/template", summary="实习学生导入·下载 Excel 模板(.xlsx)")
def intern_import_template(user=Depends(get_current_user)):
    data = xlsx_util.build_template_xlsx(svc.IMPORT_HEADERS, sample=svc.IMPORT_SAMPLE,
                                         notes=svc.IMPORT_NOTES, required=svc.IMPORT_REQUIRED)
    return StreamingResponse(io.BytesIO(data), media_type=_XLSX_MEDIA, headers={
        "Content-Disposition": "attachment; filename=intern_student_import_template.xlsx"})


@router.post("/intern-students/import/xlsx", summary="上传 Excel(.xlsx)·解析并预校验（不写库）")
async def intern_import_xlsx(file: UploadFile = File(...), user=Depends(get_current_user)):
    content = await file.read()
    rows = xlsx_util.read_xlsx(content, svc.IMPORT_HEADER_MAP)
    return success({**svc.import_dry_run(rows), "rows": rows})


@router.post("/intern-students/import/errors-xlsx", summary="下载错误行 Excel(.xlsx)")
def intern_import_errors_xlsx(body: dict = Body(...), user=Depends(get_current_user)):
    rows = body.get("rows") or []
    errors = body.get("errors") or []
    data = xlsx_util.build_error_rows_xlsx(svc.IMPORT_HEADERS, rows, errors, svc._row_values_for_error)
    return StreamingResponse(io.BytesIO(data), media_type=_XLSX_MEDIA, headers={
        "Content-Disposition": "attachment; filename=intern_student_import_errors.xlsx"})


@router.post("/intern-students/export", summary="实习学生台账导出 Excel(.xlsx)（脱敏+水印，写审计）")
def intern_export(keyword: Optional[str] = None, status: Optional[str] = None,
                  eligibility: Optional[str] = None, user=Depends(get_current_user)):
    data = svc.export_students(keyword=keyword, status=status, eligibility=eligibility, user=user)
    audit_log.record("导出实习学生", "internship-student:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/intern-students", summary="新增实习学生建档（初始准备中/资格待认定）")
def create_intern_student(body: StudentRecordCreate, user=Depends(get_current_user)):
    result = svc.create_student_record(body)
    audit_log.record("新增实习学生", f"internship-student:{result['id']}", detail={"studentId": result["studentId"]})
    return success(result, message="已建档")


@router.get("/intern-students/{record_id}", summary="实习学生详情（企业/岗位/导师/资格/去向/审计）")
def intern_student_detail(record_id: str, user=Depends(get_current_user)):
    return success(svc.get_student(record_id, user=user))


@router.put("/intern-students/{record_id}", summary="编辑实习学生（已归档不可编辑）")
def update_intern_student(record_id: str, body: StudentRecordUpdate, user=Depends(get_current_user)):
    result = svc.update_student_record(record_id, body)
    audit_log.record("编辑实习学生", f"internship-student:{record_id}")
    return success(result, message="已保存")


@router.post("/intern-students/{record_id}/assign", summary="分配岗位（校验上架/黑名单/满员；回填 allocated_count）")
def assign_position(record_id: str, body: AssignPositionRequest, user=Depends(get_current_user)):
    result = svc.assign_position(record_id, body.positionId)
    audit_log.record("分配实习岗位", f"internship-student:{record_id}", detail={"positionId": body.positionId})
    return success(result, message="已分配")


@router.post("/intern-students/{record_id}/unassign", summary="退岗（释放岗位名额）")
def unassign_position(record_id: str, body: UnassignRequest, user=Depends(get_current_user)):
    result = svc.unassign_position(record_id, body.reason or "")
    audit_log.record("实习退岗", f"internship-student:{record_id}")
    return success(result, message="已退岗")


@router.post("/intern-students/{record_id}/status", summary="实习状态机（待上岗/上岗/考核/归档）")
def student_status(record_id: str, body: StudentStatusRequest, user=Depends(get_current_user)):
    result = svc.set_status(record_id, body.action, body.reason or "")
    audit_log.record("实习状态变更", f"internship-student:{record_id}", detail={"action": body.action})
    return success(result, message="已更新")


@router.post("/intern-students/{record_id}/eligibility", summary="实习资格认定（合格/不合格）")
def student_eligibility(record_id: str, body: EligibilityRequest, user=Depends(get_current_user)):
    result = svc.set_eligibility(record_id, body.status, body.reason or "")
    audit_log.record("实习资格认定", f"internship-student:{record_id}", detail={"status": body.status})
    return success(result, message="已更新")


@router.post("/intern-students/{record_id}/destination", summary="实习去向（自主实习/免实习/未落实）")
def student_destination(record_id: str, body: DestinationRequest, user=Depends(get_current_user)):
    result = svc.set_destination(record_id, body.destination, body.reason or "")
    audit_log.record("实习去向变更", f"internship-student:{record_id}", detail={"destination": body.destination})
    return success(result, message="已更新")
