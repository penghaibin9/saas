"""岗位实习域 API（/api/v1/internship/*）。真实走库；写操作落审计。"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.internship import (BatchCreate, BatchUpdate, BlacklistRequest, ContactCreate,
                                     ContactUpdate, CoopActionRequest, EnterpriseCreate,
                                     EnterpriseImport, EnterpriseReview, EnterpriseUpdate,
                                     ExceptionHandleRequest, ImportErrorsExport, ReportReviewRequest,
                                     VoidBatchRequest)
from app.services import audit_log
from app.services import internship_enterprise_service as ent
from app.services import internship_service as svc

# 企业库导入导出已全部迁至公共 Excel 底座（app.services.excel）：
# 字段/校验/模板/错误行/台账由 internship_enterprise_service 的 ImportSpec/ExportSpec 定义。

router = APIRouter(prefix="/internship", tags=["岗位实习"])


@router.get("/dashboard", summary="实习中心看板")
def dashboard(user=Depends(get_current_user)):
    return success(svc.get_dashboard_summary())


@router.get("/students", summary="实习学生列表（分页+筛选）")
def students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, classId: Optional[str] = None,
             status: Optional[str] = None, riskLevel: Optional[str] = None,
             user=Depends(get_current_user)):
    items, total = svc.list_internship_students(page, pageSize, keyword=keyword, class_id=classId,
                                                status=status, risk_level=riskLevel)
    return success(paginate(items, total, page, pageSize))


@router.get("/students/{record_id}", summary="实习学生详情（含打卡/周报/风险/留痕）")
def student_detail(record_id: str, user=Depends(get_current_user)):
    return success(svc.get_internship_student_detail(record_id))


@router.get("/exceptions", summary="打卡异常列表")
def exceptions(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               type: Optional[str] = None, status: Optional[str] = None,
               keyword: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_attendance_exceptions(page, pageSize, type=type, status=status,
                                                  keyword=keyword)
    return success(paginate(items, total, page, pageSize))


@router.get("/exceptions/{exception_id}", summary="打卡异常详情（含处理留痕）")
def exception_detail(exception_id: str, user=Depends(get_current_user)):
    return success(svc.get_exception_detail(exception_id))


@router.post("/exceptions/{exception_id}/handle", summary="处理打卡异常（合理/异常/转风险，意见≥5字）")
def handle_exception(exception_id: str, body: ExceptionHandleRequest,
                     user=Depends(get_current_user)):
    result = svc.handle_attendance_exception(exception_id, body.action, body.comment)
    audit_log.record("处理打卡异常", f"internship-exception:{exception_id}",
                     detail={"action": body.action})
    return success(result, message="已处理")


@router.get("/reports", summary="周报批阅列表")
def reports(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            status: Optional[str] = None, keyword: Optional[str] = None,
            user=Depends(get_current_user)):
    items, total = svc.list_weekly_reports(page, pageSize, status=status, keyword=keyword)
    return success(paginate(items, total, page, pageSize))


@router.get("/reports/{report_id}", summary="周报详情（含批阅留痕）")
def report_detail(report_id: str, user=Depends(get_current_user)):
    return success(svc.get_weekly_report_detail(report_id))


@router.post("/reports/{report_id}/review", summary="批阅周报（通过/退回，退回原因≥5字）")
def review_report(report_id: str, body: ReportReviewRequest, user=Depends(get_current_user)):
    result = svc.review_weekly_report(report_id, body.action, body.comment)
    audit_log.record("批阅周报", f"internship-report:{report_id}", detail={"action": body.action})
    return success(result, message="批阅完成")


@router.get("/risks", summary="实习风险学生列表")
def risks(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
          level: Optional[str] = None, status: Optional[str] = None,
          user=Depends(get_current_user)):
    items, total = svc.list_risk_students(page, pageSize, level=level, status=status)
    return success(paginate(items, total, page, pageSize))


# ═══════════ 实习批次（组织时间轴 + 规则骨架，状态机 DRAFT→RUNNING→CLOSED→ARCHIVED）═══════════
# 注意：静态子路由 export 声明在 /{bid} 之前，避免被动态段吞掉（同企业库范式）。

@router.post("/batches/export", summary="导出批次 Excel 台账（写审计）")
def batch_export(keyword: Optional[str] = None, status: Optional[str] = None,
                 user=Depends(get_current_user)):
    data = svc.export_batches(keyword=keyword, status=status)
    audit_log.record("导出实习批次台账", "internship-batch:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/batches", summary="实习批次列表（分页+筛选）")
def batches(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            keyword: Optional[str] = None, status: Optional[str] = None,
            user=Depends(get_current_user)):
    items, total = svc.list_batches(page, pageSize, keyword=keyword, status=status)
    return success(paginate(items, total, page, pageSize))


@router.post("/batches", summary="新建实习批次（草稿态，批次编号租户内唯一）")
def batch_create(body: BatchCreate, user=Depends(get_current_user)):
    result = svc.create_batch(body.model_dump())
    audit_log.record("新建实习批次", f"internship-batch:{result['id']}", detail={"batchName": body.batchName})
    return success(result, message="已新建")


@router.get("/batches/{bid}", summary="批次详情（含阶段时间轴/规则配置/审计留痕）")
def batch_detail(bid: str, user=Depends(get_current_user)):
    return success(svc.get_batch(bid))


@router.put("/batches/{bid}", summary="编辑批次（已结束/已归档/已作废不可编辑）")
def batch_update(bid: str, body: BatchUpdate, user=Depends(get_current_user)):
    result = svc.update_batch(bid, body.model_dump(exclude_unset=True))
    audit_log.record("编辑实习批次", f"internship-batch:{bid}")
    return success(result, message="已保存")


@router.post("/batches/{bid}/activate", summary="启用批次（草稿→进行中）")
def batch_activate(bid: str, user=Depends(get_current_user)):
    result = svc.activate_batch(bid)
    audit_log.record("启用实习批次", f"internship-batch:{bid}")
    return success(result, message="已启用")


@router.post("/batches/{bid}/close", summary="结束批次（进行中→已结束）")
def batch_close(bid: str, user=Depends(get_current_user)):
    result = svc.close_batch(bid)
    audit_log.record("结束实习批次", f"internship-batch:{bid}")
    return success(result, message="已结束")


@router.post("/batches/{bid}/archive", summary="归档批次（已结束→已归档）")
def batch_archive(bid: str, user=Depends(get_current_user)):
    result = svc.archive_batch(bid)
    audit_log.record("归档实习批次", f"internship-batch:{bid}")
    return success(result, message="已归档")


@router.post("/batches/{bid}/void", summary="作废批次（仅草稿可作废，原因≥5字）")
def batch_void(bid: str, body: VoidBatchRequest, user=Depends(get_current_user)):
    result = svc.void_batch(bid, body.reason)
    audit_log.record("作废实习批次", f"internship-batch:{bid}", detail={"reason": body.reason})
    return success(result, message="已作废")


# ═══════════ 企业库（共享企业主档 t_emp_company 之上的实习企业管理）═══════════
# 注意：静态子路由（stats / import / export）声明在 /{company_id} 之前，避免被动态段吞掉。

@router.get("/enterprises", summary="企业库列表（分页+筛选，联系电话脱敏）")
def enterprises(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                keyword: Optional[str] = None, coopStatus: Optional[str] = None,
                industry: Optional[str] = None, region: Optional[str] = None,
                blacklist: Optional[bool] = None, user=Depends(get_current_user)):
    items, total = ent.list_enterprises(page, pageSize, keyword=keyword, coop_status=coopStatus,
                                        industry=industry, region=region, blacklist=blacklist)
    return success(paginate(items, total, page, pageSize))


@router.get("/enterprises/stats", summary="企业库统计（按合作状态/行业/黑名单）")
def enterprise_stats(user=Depends(get_current_user)):
    return success(ent.enterprise_stats())


@router.post("/enterprises/import/dry-run", summary="企业库导入·预校验（不写库）")
def enterprise_import_dry_run(body: EnterpriseImport, user=Depends(get_current_user)):
    return success(ent.import_dry_run(body.rows))


@router.get("/enterprises/import/template", summary="企业库导入·下载 Excel 模板(.xlsx)")
def enterprise_import_template(user=Depends(get_current_user)):
    # 走公共 Excel 底座生成模板（字段/必填/示例/说明由 ImportSpec 统一定义）
    data = ent.import_template_bytes()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=enterprise_import_template.xlsx"})


@router.post("/enterprises/import/xlsx", summary="企业库导入·上传 Excel 解析+预校验（不写库，返回行数据供确认）")
async def enterprise_import_xlsx(file: UploadFile = File(...), user=Depends(get_current_user)):
    content = await file.read()
    rows = ent.import_read(content)          # 底座表头映射
    dry = ent.import_dry_run(rows)           # 底座统一预校验
    return success({"rows": rows, **dry})


@router.post("/enterprises/import/errors-xlsx", summary="企业库导入·下载错误行 Excel")
def enterprise_import_errors_xlsx(body: ImportErrorsExport, user=Depends(get_current_user)):
    packed = ent.import_errors_pack(body.rows, body.errors)   # 底座生成错误行 Excel
    return success(packed)


@router.post("/enterprises/import/confirm", summary="企业库导入·确认（整批事务，预校验须全通过）")
def enterprise_import_confirm(body: EnterpriseImport, user=Depends(get_current_user)):
    result = ent.import_confirm(body.rows)
    audit_log.record("导入企业库", "internship-enterprise:import", detail=result)
    return success(result, message="导入完成")


@router.post("/enterprises/export", summary="企业库导出 Excel 台账（脱敏，写审计）")
def enterprise_export(keyword: Optional[str] = None, coopStatus: Optional[str] = None,
                      industry: Optional[str] = None, region: Optional[str] = None,
                      user=Depends(get_current_user)):
    data = ent.export_enterprises(keyword=keyword, coop_status=coopStatus,
                                  industry=industry, region=region)
    audit_log.record("导出企业库", "internship-enterprise:export",
                     detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/enterprises", summary="新增企业（初始待审核）")
def create_enterprise(body: EnterpriseCreate, user=Depends(get_current_user)):
    result = ent.create_enterprise(body)
    audit_log.record("新增企业", f"internship-enterprise:{result['id']}", detail={"name": result["name"]})
    return success(result, message="已创建")


@router.get("/enterprises/{company_id}", summary="企业详情（含联系人/导师/合作资质/审计）")
def enterprise_detail(company_id: str, user=Depends(get_current_user)):
    return success(ent.get_enterprise(company_id))


@router.put("/enterprises/{company_id}", summary="编辑企业")
def update_enterprise(company_id: str, body: EnterpriseUpdate, user=Depends(get_current_user)):
    result = ent.update_enterprise(company_id, body)
    audit_log.record("编辑企业", f"internship-enterprise:{company_id}")
    return success(result, message="已保存")


@router.post("/enterprises/{company_id}/review", summary="企业资质审核（仅待审核可审：通过→合作中/驳回）")
def review_enterprise(company_id: str, body: EnterpriseReview, user=Depends(get_current_user)):
    result = ent.review_enterprise(company_id, body.action, body.comment or "")
    audit_log.record("企业资质审核", f"internship-enterprise:{company_id}", detail={"action": body.action})
    return success(result, message="审核完成")


@router.post("/enterprises/{company_id}/cooperation", summary="合作启停（暂停/恢复/归档）")
def cooperation(company_id: str, body: CoopActionRequest, user=Depends(get_current_user)):
    result = ent.set_cooperation(company_id, body.action, body.reason or "")
    audit_log.record("企业合作状态变更", f"internship-enterprise:{company_id}", detail={"action": body.action})
    return success(result, message="已更新")


@router.post("/enterprises/{company_id}/blacklist", summary="拉黑/移出黑名单（拉黑须原因）")
def blacklist(company_id: str, body: BlacklistRequest, user=Depends(get_current_user)):
    result = ent.set_blacklist(company_id, body.on, body.reason or "")
    audit_log.record("企业黑名单变更", f"internship-enterprise:{company_id}", detail={"on": body.on})
    return success(result, message="已更新")


@router.get("/enterprises/{company_id}/contacts", summary="企业联系人/导师列表（电话脱敏）")
def list_contacts(company_id: str, user=Depends(get_current_user)):
    return success({"items": ent.list_contacts(company_id)})


@router.post("/enterprises/{company_id}/contacts", summary="新增联系人/企业导师")
def add_contact(company_id: str, body: ContactCreate, user=Depends(get_current_user)):
    result = ent.add_contact(company_id, body)
    audit_log.record("新增企业联系人", f"internship-enterprise:{company_id}", detail={"name": result["name"]})
    return success(result, message="已新增")


@router.put("/enterprises/{company_id}/contacts/{contact_id}", summary="编辑联系人/企业导师")
def update_contact(company_id: str, contact_id: str, body: ContactUpdate,
                   user=Depends(get_current_user)):
    result = ent.update_contact(company_id, contact_id, body)
    audit_log.record("编辑企业联系人", f"internship-enterprise:{company_id}")
    return success(result, message="已保存")


@router.delete("/enterprises/{company_id}/contacts/{contact_id}", summary="删除联系人/企业导师（软删）")
def delete_contact(company_id: str, contact_id: str, user=Depends(get_current_user)):
    result = ent.delete_contact(company_id, contact_id)
    audit_log.record("删除企业联系人", f"internship-enterprise:{company_id}")
    return success(result, message="已删除")
