"""岗位实习域 API（/api/v1/internship/*）。真实走库；写操作落审计。"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.internship import (BatchCreate, BatchUpdate, BlacklistRequest, ContactCreate,
                                     ContactUpdate, CoopActionRequest, EnterpriseCreate,
                                     EnterpriseImport, EnterpriseReview, EnterpriseUpdate,
                                     ExceptionBatchHandleRequest, ExceptionExportRequest,
                                     ExceptionHandleRequest, ImportErrorsExport,
                                     ReportBatchReviewRequest, ReportRemindRequest,
                                     ReportReviewRequest,
                                     VoidBatchRequest)
from app.services import audit_log
from app.services import internship_enterprise_service as ent
from app.services import internship_agreement_service as agr
from app.services import internship_archive_service as arch
from app.services import internship_enterprise_eval_service as ee
from app.services import internship_guidance_service as gd
from app.services import internship_leave_service as lv
from app.services import internship_makeup_service as mk
from app.services import internship_risk_service as risk
from app.services import internship_process_report_service as pr
from app.services import internship_change_service as chg
from app.services import internship_plan_service as plan
from app.services import internship_plan_task_service as plan_task
from app.services import internship_insurance_service as ins
from app.services import internship_score_service as score
from app.services import internship_service as svc
from app.services import internship_stats_service as stats
from app.services import internship_student_eval_service as se
from app.services import internship_visit_service as vis
from app.services import xlsx_util

_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# 企业库导入导出已全部迁至公共 Excel 底座（app.services.excel）：
# 字段/校验/模板/错误行/台账由 internship_enterprise_service 的 ImportSpec/ExportSpec 定义。

router = APIRouter(prefix="/internship", tags=["岗位实习"])


@router.get("/dashboard", summary="实习中心看板")
def dashboard(user=Depends(get_current_user)):
    return success(svc.get_dashboard_summary(user=user))


@router.get("/students", summary="实习学生列表（分页+筛选）")
def students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, classId: Optional[str] = None,
             status: Optional[str] = None, riskLevel: Optional[str] = None,
             user=Depends(get_current_user)):
    items, total = svc.list_internship_students(page, pageSize, keyword=keyword, class_id=classId,
                                                status=status, risk_level=riskLevel, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/students/{record_id}", summary="实习学生详情（含打卡/周报/风险/留痕）")
def student_detail(record_id: str, user=Depends(get_current_user)):
    return success(svc.get_internship_student_detail(record_id, user=user))


@router.get("/checkins", summary="打卡台账（按数据范围）")
def checkins(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             result: Optional[str] = None, keyword: Optional[str] = None,
             internshipId: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_checkins(page, pageSize, result=result, keyword=keyword,
                                     internship_id=internshipId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/checkins/export", summary="打卡台账导出 Excel(.xlsx)")
def checkins_export(result: Optional[str] = None, keyword: Optional[str] = None,
                    user=Depends(get_current_user)):
    data = svc.export_checkins(result=result, keyword=keyword, user=user)
    audit_log.record("导出打卡台账", "internship-checkin:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/exceptions", summary="打卡异常列表")
def exceptions(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               type: Optional[str] = None, status: Optional[str] = None,
               keyword: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_attendance_exceptions(page, pageSize, type=type, status=status,
                                                  keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/exceptions/export", summary="打卡异常台账导出 Excel(.xlsx)")
def exceptions_export(type: Optional[str] = None, status: Optional[str] = None,
                      keyword: Optional[str] = None,
                      body: Optional[ExceptionExportRequest] = Body(None),
                      user=Depends(get_current_user)):
    ids = body.ids if body else None
    data = svc.export_exceptions(type=type, status=status, keyword=keyword, ids=ids, user=user)
    audit_log.record("导出打卡异常台账", "internship-exception:export",
                     detail={"rowCount": data["rowCount"], "selectedOnly": bool(ids)})
    return success(data)


@router.post("/exceptions/batch-handle", summary="批量处理打卡异常（仅标记合理）")
def batch_handle_exceptions(body: ExceptionBatchHandleRequest, user=Depends(get_current_user)):
    result = svc.batch_handle_attendance_exceptions(body.ids, body.action, body.comment, user=user)
    audit_log.record("批量处理打卡异常", "internship-exception:batch-handle",
                     detail={"processedCount": result["processedCount"],
                             "skippedCount": result["skippedCount"]})
    return success(result, message=f"已处理 {result['processedCount']} 条，跳过 {result['skippedCount']} 条")


@router.get("/exceptions/{exception_id}", summary="打卡异常详情（含处理留痕）")
def exception_detail(exception_id: str, user=Depends(get_current_user)):
    return success(svc.get_exception_detail(exception_id, user=user))


@router.post("/exceptions/{exception_id}/handle", summary="处理打卡异常（合理/异常/转风险，意见≥5字）")
def handle_exception(exception_id: str, body: ExceptionHandleRequest,
                     user=Depends(get_current_user)):
    result = svc.handle_attendance_exception(exception_id, body.action, body.comment, user=user)
    audit_log.record("处理打卡异常", f"internship-exception:{exception_id}",
                     detail={"action": body.action})
    return success(result, message="已处理")


# ═══ 补卡审批（PC 管理端·owner+数据范围；学生申请/撤回在 /mobile/internship/makeup/*） ═══

@router.get("/makeups", summary="补卡审批台账（按数据范围）")
def makeups(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            status: Optional[str] = None, user=Depends(get_current_user)):
    items, total = mk.list_makeups(page, pageSize, status=status, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/makeups/{makeup_id}", summary="补卡申请详情（含审批留痕）")
def makeup_detail(makeup_id: str, user=Depends(get_current_user)):
    return success(mk.get_makeup(makeup_id, user=user))


@router.post("/makeups/{makeup_id}/approve", summary="补卡·通过（owner 校验，真实补写打卡）")
def makeup_approve(makeup_id: str, body: dict = Body(default={}), user=Depends(get_current_user)):
    result = mk.review(user, makeup_id, "APPROVE", (body or {}).get("comment") or "")
    audit_log.record("审批补卡·通过", f"internship-makeup:{makeup_id}", detail=result)
    return success(result, message="已通过")


@router.post("/makeups/{makeup_id}/reject", summary="补卡·驳回（owner 校验，原因≥5字）")
def makeup_reject(makeup_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = mk.review(user, makeup_id, "REJECT", (body or {}).get("comment") or "")
    audit_log.record("审批补卡·驳回", f"internship-makeup:{makeup_id}", detail=result)
    return success(result, message="已驳回")


@router.post("/makeups/export", summary="补卡审批台账导出 Excel(.xlsx)")
def makeups_export(status: Optional[str] = None, user=Depends(get_current_user)):
    data = mk.export_makeups(status=status, user=user)
    audit_log.record("导出补卡审批台账", "internship-makeup:export",
                     detail={"rowCount": data["rowCount"]})
    return success(data)


# ═══ 指导记录（owner + 数据范围） ═══

@router.get("/guidances", summary="指导记录列表（按数据范围）")
def guidances(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, user=Depends(get_current_user)):
    items, total = gd.list_guidances(page, pageSize, keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/guidances/stats", summary="指导频次统计（指导不足预警）")
def guidances_stats(threshold: int = Query(2, ge=1, le=50), user=Depends(get_current_user)):
    return success(gd.guidance_stats(threshold, user=user))


@router.get("/guidance-plans", summary="指导计划台账（批次规则 vs 实际频次）")
def guidance_plans(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                   keyword: Optional[str] = None, planStatus: Optional[str] = None,
                   insufficientOnly: bool = Query(False), user=Depends(get_current_user)):
    items, total = gd.list_guidance_plans(page, pageSize, keyword=keyword, plan_status=planStatus,
                                          insufficient_only=insufficientOnly, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/guidance-plans/export", summary="指导计划台账导出 Excel(.xlsx)")
def guidance_plans_export(keyword: Optional[str] = None, user=Depends(get_current_user)):
    data = gd.export_guidance_plans(keyword=keyword, user=user)
    audit_log.record("导出指导计划台账", "internship-guidance-plan:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/guidances", summary="新增指导记录（owner：仅本人指导学生）")
def create_guidance(body: dict = Body(...), user=Depends(get_current_user)):
    result = gd.create(user, body)
    audit_log.record("新增指导记录", f"internship-guidance:{result['id']}", detail=result)
    return success(result, message="已保存")


@router.get("/guidances/{guidance_id}", summary="指导记录详情")
def guidance_detail(guidance_id: str, user=Depends(get_current_user)):
    return success(gd.get_guidance(guidance_id, user=user))


@router.post("/guidances/{guidance_id}/void", summary="撤销指导记录（owner）")
def void_guidance(guidance_id: str, body: dict = Body(default={}), user=Depends(get_current_user)):
    result = gd.void_guidance(user, guidance_id, (body or {}).get("reason") or "")
    audit_log.record("撤销指导记录", f"internship-guidance:{guidance_id}", detail=result)
    return success(result, message="已撤销")


@router.post("/guidances/export", summary="指导记录台账导出 Excel(.xlsx)")
def guidances_export(keyword: Optional[str] = None, user=Depends(get_current_user)):
    data = gd.export_guidances(keyword=keyword, user=user)
    audit_log.record("导出指导记录台账", "internship-guidance:export", detail={"rowCount": data["rowCount"]})
    return success(data)


# ═══ 教师巡访（owner + 数据范围 + 整改跟进） ═══

@router.get("/visits", summary="巡访记录列表（按数据范围）")
def visits(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           keyword: Optional[str] = None, rectify: Optional[str] = None,
           user=Depends(get_current_user)):
    items, total = vis.list_visits(page, pageSize, keyword=keyword, rectify=rectify, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/visits/stats", summary="巡访整改统计")
def visits_stats(user=Depends(get_current_user)):
    return success(vis.visit_stats(user=user))


@router.post("/visits", summary="新增巡访记录（owner：仅本人指导学生）")
def create_visit(body: dict = Body(...), user=Depends(get_current_user)):
    result = vis.create(user, body)
    audit_log.record("新增巡访记录", f"internship-visit:{result['id']}", detail=result)
    return success(result, message="已保存")


@router.get("/visits/{visit_id}", summary="巡访记录详情（含月报/整改留痕）")
def visit_detail(visit_id: str, user=Depends(get_current_user)):
    return success(vis.get_visit(visit_id, user=user))


@router.post("/visits/{visit_id}/rectify", summary="巡访整改跟进（owner，说明必填）")
def visit_rectify(visit_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    b = body or {}
    result = vis.rectify_follow(user, visit_id, (b.get("status") or "").upper(), b.get("note") or "")
    audit_log.record("巡访整改跟进", f"internship-visit:{visit_id}", detail=result)
    return success(result, message="已跟进")


@router.post("/visits/export", summary="巡访记录台账导出 Excel(.xlsx)")
def visits_export(keyword: Optional[str] = None, user=Depends(get_current_user)):
    data = vis.export_visits(keyword=keyword, user=user)
    audit_log.record("导出巡访记录台账", "internship-visit:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/reports", summary="周报批阅列表")
def reports(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            status: Optional[str] = None, keyword: Optional[str] = None,
            user=Depends(get_current_user)):
    items, total = svc.list_weekly_reports(page, pageSize, status=status, keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/reports/export", summary="周报批阅台账导出 Excel(.xlsx)")
def reports_export(status: Optional[str] = None, keyword: Optional[str] = None,
                   user=Depends(get_current_user)):
    data = svc.export_weekly_reports(status=status, keyword=keyword, user=user)
    audit_log.record("导出周报批阅台账", "internship-report:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/reports/batch-review", summary="批量批阅周报（仅通过；风险/非待批阅跳过）")
def batch_review_reports(body: ReportBatchReviewRequest, user=Depends(get_current_user)):
    result = svc.batch_review_weekly_reports(body.ids, body.action, body.comment, user=user)
    audit_log.record("批量批阅周报", "internship-report:batch-review",
                     detail={"approvedCount": result["approvedCount"], "skippedCount": result["skippedCount"]})
    return success(result, message=f"已通过 {result['approvedCount']} 篇，跳过 {result['skippedCount']} 篇")


@router.post("/reports/{report_id}/remind", summary="催交逾期未交周报（写审计+站内信）")
def remind_report(report_id: str, body: ReportRemindRequest = Body(default=ReportRemindRequest()),
                  user=Depends(get_current_user)):
    result = svc.remind_weekly_report(report_id, body.channel or "站内消息", user=user)
    audit_log.record("催交实习周报", f"internship-report:{report_id}",
                     detail={"weekNumber": result.get("weekNumber"), "notified": result.get("notified")})
    return success(result, message="已催交")


@router.get("/reports/{report_id}", summary="周报详情（含批阅留痕）")
def report_detail(report_id: str, user=Depends(get_current_user)):
    return success(svc.get_weekly_report_detail(report_id, user=user))


@router.post("/reports/{report_id}/review", summary="批阅周报（通过/退回，退回原因≥5字）")
def review_report(report_id: str, body: ReportReviewRequest, user=Depends(get_current_user)):
    result = svc.review_weekly_report(report_id, body.action, body.comment, user=user)
    audit_log.record("批阅周报", f"internship-report:{report_id}", detail={"action": body.action})
    return success(result, message="批阅完成")


@router.get("/process-reports", summary="过程报告批阅列表（日报/月报/实习总结）")
def process_reports(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                    reportType: Optional[str] = None, status: Optional[str] = None,
                    keyword: Optional[str] = None, user=Depends(get_current_user)):
    items, total = pr.list_reports(page, pageSize, report_type=reportType, status=status,
                                   keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/process-reports/export", summary="过程报告台账导出 Excel(.xlsx)")
def process_reports_export(reportType: Optional[str] = None, status: Optional[str] = None,
                           keyword: Optional[str] = None, user=Depends(get_current_user)):
    data = pr.export_reports(report_type=reportType, status=status, keyword=keyword, user=user)
    audit_log.record("导出过程报告台账", "internship-process-report:export",
                     detail={"rowCount": data["rowCount"], "reportType": reportType})
    return success(data)


@router.get("/process-reports/{report_id}", summary="过程报告详情（含批阅留痕）")
def process_report_detail(report_id: str, user=Depends(get_current_user)):
    return success(pr.get_report(report_id, user=user))


@router.post("/process-reports/{report_id}/review", summary="批阅过程报告（通过/退回）")
def process_report_review(report_id: str, body: ReportReviewRequest, user=Depends(get_current_user)):
    result = pr.review_report(report_id, body.action, body.comment, user=user)
    audit_log.record("批阅过程报告", f"internship-process-report:{report_id}",
                     detail={"action": body.action})
    return success(result, message="批阅完成")


@router.get("/change-requests", summary="实习变更申请列表（换岗/换单位/自主实习）")
def change_requests(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                    status: Optional[str] = None, keyword: Optional[str] = None,
                    user=Depends(get_current_user)):
    items, total = chg.list_changes(page, pageSize, status=status, keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/change-requests/{change_id}", summary="实习变更申请详情")
def change_request_detail(change_id: str, user=Depends(get_current_user)):
    return success(chg.get_change(change_id, user=user))


@router.post("/change-requests/{change_id}/review", summary="审核实习变更（通过/驳回）")
def change_request_review(change_id: str, body: ReportReviewRequest, user=Depends(get_current_user)):
    action = "APPROVE" if body.action == "APPROVE" else "REJECT"
    result = chg.review_change(change_id, action, body.comment, user=user)
    audit_log.record("审核实习变更", f"internship-change:{change_id}", detail={"action": action})
    return success(result, message="审核完成")


@router.get("/risks", summary="实习风险学生列表")
def risks(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
          level: Optional[str] = None, status: Optional[str] = None,
          riskCode: Optional[str] = None,
          user=Depends(get_current_user)):
    items, total = svc.list_risk_students(page, pageSize, level=level, status=status,
                                          risk_code=riskCode, user=user)
    return success(paginate(items, total, page, pageSize))


# ═══════════ 风险处置闭环（P1-Stage3：受理/跟进/升级/关闭，owner + 审计）═══════════
# 静态子路由 export 声明在 /{rid} 之前，避免被动态段吞掉。

@router.post("/risks/export", summary="风险处置台账导出 Excel(.xlsx)")
def risks_export(keyword: Optional[str] = None, user=Depends(get_current_user)):
    data = risk.export_risks(keyword=keyword, user=user)
    audit_log.record("导出风险处置台账", "internship-risk:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/risks/{risk_id}", summary="风险单详情（含处置留痕）")
def risk_detail(risk_id: str, user=Depends(get_current_user)):
    return success(risk.get_risk(risk_id, user=user))


@router.post("/risks/{risk_id}/handle", summary="受理风险（PENDING→PROCESSING，owner）")
def risk_handle(risk_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    b = body or {}
    result = risk.handle(user, risk_id, owner_name=b.get("ownerName"),
                         deadline=b.get("deadline"), comment=b.get("comment") or "")
    audit_log.record("受理实习风险", f"internship-risk:{risk_id}", detail=result)
    return success(result, message="已受理")


@router.post("/risks/{risk_id}/follow", summary="风险跟进（追加跟进说明，owner）")
def risk_follow(risk_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = risk.follow(user, risk_id, (body or {}).get("note") or "")
    audit_log.record("跟进实习风险", f"internship-risk:{risk_id}", detail=result)
    return success(result, message="已跟进")


@router.post("/risks/{risk_id}/remind", summary="催办风险跟进（写审计）")
def risk_remind(risk_id: str, body: dict = Body(default={}), user=Depends(get_current_user)):
    b = body or {}
    result = risk.remind(user, risk_id, b.get("channel") or "站内消息")
    audit_log.record("催办实习风险", f"internship-risk:{risk_id}", detail=result)
    return success(result, message="已提醒")


@router.post("/risks/{risk_id}/escalate", summary="风险升级（提升等级，owner）")
def risk_escalate(risk_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    b = body or {}
    result = risk.escalate(user, risk_id, (b.get("level") or "").upper(), b.get("note") or "")
    audit_log.record("升级实习风险", f"internship-risk:{risk_id}", detail=result)
    return success(result, message="已升级")


@router.post("/risks/{risk_id}/close", summary="风险关闭（化解/关闭归档，owner）")
def risk_close(risk_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    b = body or {}
    result = risk.close(user, risk_id, (b.get("result") or "RESOLVED").upper(), b.get("comment") or "")
    audit_log.record("关闭实习风险", f"internship-risk:{risk_id}", detail=result)
    return success(result, message="已关闭")


# ═══════════ 实习请假审批（P1-Stage3：教师端 owner + 数据范围；学生端在 mobile）═══════════

@router.post("/leaves/export", summary="请假审批台账导出 Excel(.xlsx)")
def leaves_export(status: Optional[str] = None, keyword: Optional[str] = None,
                  user=Depends(get_current_user)):
    data = lv.export_leaves(status=status, keyword=keyword, user=user)
    audit_log.record("导出请假审批台账", "internship-leave:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/leaves", summary="实习请假列表（按数据范围）")
def leaves(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           status: Optional[str] = None, keyword: Optional[str] = None,
           user=Depends(get_current_user)):
    items, total = lv.list_leaves(page, pageSize, status=status, keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/leaves/{leave_id}", summary="请假详情（含附件/审批留痕）")
def leave_detail(leave_id: str, user=Depends(get_current_user)):
    return success(lv.get_leave(leave_id, user=user))


@router.post("/leaves/{leave_id}/review", summary="审批请假（通过/驳回，驳回原因≥5字，owner）")
def leave_review(leave_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    b = body or {}
    result = lv.review(user, leave_id, (b.get("action") or "").upper(), b.get("comment") or "")
    audit_log.record("审批实习请假", f"internship-leave:{leave_id}", detail=result)
    return success(result, message="审批完成")


# ═══════════ 三方协议签署实例（P2-A：三方确认状态机，owner + 数据范围）═══════════

@router.post("/agreements/export", summary="三方协议台账导出 Excel(.xlsx)")
def agreements_export(status: Optional[str] = None, keyword: Optional[str] = None,
                      user=Depends(get_current_user)):
    data = agr.export_agreements(status=status, keyword=keyword, user=user)
    audit_log.record("导出三方协议台账", "internship-agreement:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/agreements", summary="三方协议列表（按数据范围）")
def agreements(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               status: Optional[str] = None, keyword: Optional[str] = None,
               user=Depends(get_current_user)):
    items, total = agr.list_agreements(page, pageSize, status=status, keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/agreements", summary="生成协议实例（owner，DRAFT）")
def agreement_generate(body: dict = Body(...), user=Depends(get_current_user)):
    result = agr.generate(user, body)
    audit_log.record("生成三方协议", f"internship-agreement:{result['id']}", detail=result)
    return success(result, message="已生成协议草稿")


@router.get("/agreements/{agreement_id}", summary="协议详情（含附件/三方确认留痕）")
def agreement_detail(agreement_id: str, user=Depends(get_current_user)):
    return success(agr.get_agreement(agreement_id, user=user))


@router.post("/agreements/{agreement_id}/pdf", summary="三方协议 PDF 套打下载")
def agreement_pdf(agreement_id: str, user=Depends(get_current_user)):
    data = agr.export_agreement_pdf(agreement_id, user=user)
    audit_log.record("导出三方协议PDF套打", f"internship-agreement:{agreement_id}",
                     detail={"filename": data.get("filename")})
    return success(data)


@router.post("/agreements/{agreement_id}/issue", summary="下发协议（DRAFT→待学生确认）")
def agreement_issue(agreement_id: str, user=Depends(get_current_user)):
    return success(agr.issue(user, agreement_id), message="已下发")


@router.post("/agreements/{agreement_id}/enterprise-confirm", summary="记录企业签署（需上传扫描件→待学校确认）")
def agreement_enterprise_confirm(agreement_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = agr.enterprise_confirm(user, agreement_id, body)
    audit_log.record("记录企业签署三方协议", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message="已记录企业签署")


@router.post("/agreements/{agreement_id}/school-confirm", summary="学校确认（待学校确认→已生效）")
def agreement_school_confirm(agreement_id: str, user=Depends(get_current_user)):
    result = agr.school_confirm(user, agreement_id)
    audit_log.record("学校确认三方协议生效", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message="协议已生效")


@router.post("/agreements/{agreement_id}/reject", summary="驳回协议（原因≥5字）")
def agreement_reject(agreement_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = agr.reject(user, agreement_id, (body or {}).get("reason") or "")
    audit_log.record("驳回三方协议", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message="已驳回")


@router.post("/agreements/{agreement_id}/void", summary="作废协议")
def agreement_void(agreement_id: str, body: dict = Body(default={}), user=Depends(get_current_user)):
    result = agr.void(user, agreement_id, (body or {}).get("reason") or "")
    audit_log.record("作废三方协议", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message="已作废")


@router.post("/agreements/{agreement_id}/archive", summary="归档协议（已生效→已归档）")
def agreement_archive(agreement_id: str, user=Depends(get_current_user)):
    result = agr.archive(user, agreement_id)
    audit_log.record("归档三方协议", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message="已归档")


@router.post("/agreements/{agreement_id}/esign/start", summary="发起三方协议电子签（INTERNAL 校内签）")
def agreement_esign_start(agreement_id: str, user=Depends(get_current_user)):
    result = agr.start_esign(user, agreement_id)
    audit_log.record("发起协议电子签", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message=result.get("message") or "已发起")


@router.post("/agreements/{agreement_id}/esign/sign", summary="电子签签署（party=STUDENT/ENTERPRISE/SCHOOL）")
def agreement_esign_sign(agreement_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = agr.esign_sign(user, agreement_id, (body or {}).get("party") or "")
    audit_log.record("协议电子签签署", f"internship-agreement:{agreement_id}",
                     detail={"party": (body or {}).get("party"), "esignStatus": result.get("esignStatus")})
    return success(result, message="签署成功")


@router.get("/plans/batch/{batch_id}", summary="批次实习计划书")
def batch_plan_get(batch_id: str, user=Depends(get_current_user)):
    return success(plan.get_plan_by_batch(batch_id, user=user))


@router.put("/plans/batch/{batch_id}", summary="保存批次实习计划书（草稿）")
def batch_plan_save(batch_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = plan.save_plan(batch_id, body, user=user)
    audit_log.record("保存实习计划书", f"internship-plan:batch:{batch_id}", detail={"planId": result.get("id")})
    return success(result, message="计划已保存")


@router.post("/plans/batch/{batch_id}/publish", summary="发布实习计划书并下发学生确认")
def batch_plan_publish(batch_id: str, user=Depends(get_current_user)):
    result = plan.publish_plan(batch_id, user=user)
    audit_log.record("发布实习计划书", f"internship-plan:batch:{batch_id}",
                     detail={"ackCount": result.get("ackCount")})
    return success(result, message=f"已发布，待确认 {result.get('ackCount', 0)} 人")


@router.get("/plan-acks", summary="实习计划确认台账")
def plan_acks(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              batchId: Optional[str] = None, status: Optional[str] = None,
              keyword: Optional[str] = None, user=Depends(get_current_user)):
    items, total = plan.list_acks(page, pageSize, batch_id=batchId, status=status,
                                  keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/plan-task-progress", summary="实习计划任务完成度台账")
def plan_task_progress(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                       batchId: Optional[str] = None, status: Optional[str] = None,
                       taskSortOrder: Optional[int] = None, keyword: Optional[str] = None,
                       user=Depends(get_current_user)):
    items, total = plan_task.list_progress(page, pageSize, batch_id=batchId, status=status,
                                           keyword=keyword, task_sort_order=taskSortOrder, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/plan-task-progress/{progress_id}/review", summary="确认/退回任务完成")
def plan_task_review(progress_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = plan_task.review_progress(progress_id, (body or {}).get("action") or "",
                                       (body or {}).get("comment") or "", user=user)
    audit_log.record("任务完成度批阅", f"internship-plan-task:{progress_id}",
                     detail={"action": (body or {}).get("action"), "status": result.get("status")})
    return success(result, message="批阅成功")


@router.get("/plans/batch/{batch_id}/task-summary", summary="批次任务完成度汇总")
def plan_task_summary(batch_id: str, user=Depends(get_current_user)):
    return success(plan_task.batch_summary(batch_id, user=user))


@router.get("/insurances", summary="实习保险核验台账")
def insurances(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               status: Optional[str] = None, keyword: Optional[str] = None,
               user=Depends(get_current_user)):
    items, total = ins.list_insurances(page, pageSize, status=status, keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/insurances/{insurance_id}/verify", summary="核验实习保险（通过/驳回）")
def insurance_verify(insurance_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    action = "APPROVE" if (body or {}).get("action") == "APPROVE" else "REJECT"
    result = ins.verify_insurance(insurance_id, action, (body or {}).get("comment") or "", user=user)
    audit_log.record("核验实习保险", f"internship-insurance:{insurance_id}", detail={"action": action})
    return success(result, message="核验完成")


# ═══════════ 企业评价（P2-B：五维评价 + 学校审核，owner + 数据范围）═══════════
# 企业导师本人提交为门户权限预留（source=ENTERPRISE）；学校录入企业纸质评价 source=SCHOOL_RECORDED。

@router.post("/enterprise-evals/export", summary="企业评价台账导出 Excel(.xlsx)")
def enterprise_evals_export(reviewStatus: Optional[str] = None, keyword: Optional[str] = None,
                            user=Depends(get_current_user)):
    data = ee.export_evals(review_status=reviewStatus, keyword=keyword, user=user)
    audit_log.record("导出企业评价台账", "internship-enterprise-eval:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/enterprise-evals", summary="企业评价列表（按数据范围）")
def enterprise_evals(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                     reviewStatus: Optional[str] = None, keyword: Optional[str] = None,
                     user=Depends(get_current_user)):
    items, total = ee.list_evals(page, pageSize, review_status=reviewStatus, keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/enterprise-evals", summary="录入企业评价（学校录入企业纸质评价/企业导师提交）")
def enterprise_eval_create(body: dict = Body(...), user=Depends(get_current_user)):
    result = ee.create(user, body)
    audit_log.record("录入企业评价", f"internship-enterprise-eval:{result['id']}", detail=result)
    return success(result, message="已录入企业评价")


@router.get("/enterprise-evals/{eval_id}", summary="企业评价详情（含五维/评语/审核留痕）")
def enterprise_eval_detail(eval_id: str, user=Depends(get_current_user)):
    return success(ee.get_eval(eval_id, user=user))


@router.post("/enterprise-evals/{eval_id}/review", summary="学校审核企业评价（通过/退回，退回原因≥5字）")
def enterprise_eval_review(eval_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    b = body or {}
    result = ee.review(user, eval_id, (b.get("action") or "").upper(), b.get("comment") or "")
    audit_log.record("审核企业评价", f"internship-enterprise-eval:{eval_id}", detail=result)
    return success(result, message="审核完成")


# ═══════════ 学生鉴定/自评（P2-C：学生自评 + 教师意见 + 学校审核）═══════════

@router.post("/student-evals/export", summary="学生鉴定台账导出 Excel(.xlsx)")
def student_evals_export(reviewStatus: Optional[str] = None, keyword: Optional[str] = None,
                         user=Depends(get_current_user)):
    data = se.export_evals(review_status=reviewStatus, keyword=keyword, user=user)
    audit_log.record("导出学生鉴定台账", "internship-student-eval:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/student-evals", summary="学生鉴定列表（按数据范围）")
def student_evals(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                  reviewStatus: Optional[str] = None, keyword: Optional[str] = None,
                  user=Depends(get_current_user)):
    items, total = se.list_evals(page, pageSize, review_status=reviewStatus, keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/student-evals/{eval_id}", summary="学生鉴定详情（自评/意见/审核留痕）")
def student_eval_detail(eval_id: str, user=Depends(get_current_user)):
    return success(se.get_eval(eval_id, user=user))


@router.post("/student-evals/{eval_id}/advisor-comment", summary="指导教师填写意见（owner）")
def student_eval_advisor_comment(eval_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = se.advisor_comment(user, eval_id, body)
    audit_log.record("填写学生鉴定指导意见", f"internship-student-eval:{eval_id}", detail=result)
    return success(result, message="已保存意见")


@router.post("/student-evals/{eval_id}/review", summary="学校审核学生鉴定（通过/退回，退回原因≥5字）")
def student_eval_review(eval_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    b = body or {}
    result = se.review(user, eval_id, (b.get("action") or "").upper(), b.get("comment") or "")
    audit_log.record("审核学生鉴定", f"internship-student-eval:{eval_id}", detail=result)
    return success(result, message="审核完成")


# ═══════════ 实习成绩五项权重（P2-D：权重配置 + 加权核算 + 复核发布，owner + 数据范围）═══════════

@router.get("/scores/config", summary="成绩权重配置（五项权重，和=100）")
def score_config_get(user=Depends(get_current_user)):
    return success(score.get_config(user=user))


@router.post("/scores/config", summary="保存成绩权重配置（校验权重和=100）")
def score_config_save(body: dict = Body(...), user=Depends(get_current_user)):
    result = score.save_config(user, body)
    audit_log.record("保存实习成绩权重配置", "internship-score:config", detail=body)
    return success(result, message="配置已保存")


@router.post("/scores/export", summary="实习成绩台账导出 Excel(.xlsx)")
def scores_export(status: Optional[str] = None, keyword: Optional[str] = None,
                  user=Depends(get_current_user)):
    data = score.export_scores(status=status, keyword=keyword, user=user)
    audit_log.record("导出实习成绩台账", "internship-score:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/scores", summary="实习成绩列表（按数据范围）")
def scores(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           status: Optional[str] = None, keyword: Optional[str] = None,
           user=Depends(get_current_user)):
    items, total = score.list_scores(page, pageSize, status=status, keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/scores/compute", summary="核算成绩（五项加权，缺项标记，owner）")
def score_compute(body: dict = Body(...), user=Depends(get_current_user)):
    result = score.compute(user, body)
    audit_log.record("核算实习成绩", f"internship-score:{result['id']}", detail=result)
    return success(result, message="核算完成")


@router.get("/scores/{score_id}", summary="成绩详情（五项/权重/核算发布留痕）")
def score_detail(score_id: str, user=Depends(get_current_user)):
    return success(score.get_score(score_id, user=user))


@router.post("/scores/{score_id}/publish", summary="发布成绩（待复核→已发布，缺项拒绝）")
def score_publish(score_id: str, user=Depends(get_current_user)):
    result = score.publish(user, score_id)
    audit_log.record("发布实习成绩", f"internship-score:{score_id}", detail=result)
    return success(result, message="成绩已发布")


@router.post("/scores/{score_id}/return", summary="退回重算（待复核→待核算）")
def score_return(score_id: str, body: dict = Body(default={}), user=Depends(get_current_user)):
    result = score.return_recalc(user, score_id, (body or {}).get("reason") or "")
    audit_log.record("退回实习成绩重算", f"internship-score:{score_id}", detail=result)
    return success(result, message="已退回重算")


@router.post("/scores/{score_id}/withdraw", summary="撤回成绩（已发布→已撤回，原因≥5字）")
def score_withdraw(score_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = score.withdraw(user, score_id, (body or {}).get("reason") or "")
    audit_log.record("撤回实习成绩", f"internship-score:{score_id}", detail=result)
    return success(result, message="已撤回")


@router.post("/scores/{score_id}/archive", summary="归档成绩（已发布→已归档）")
def score_archive(score_id: str, user=Depends(get_current_user)):
    result = score.archive(user, score_id)
    audit_log.record("归档实习成绩", f"internship-score:{score_id}", detail=result)
    return success(result, message="已归档")


# ═══════════ 归档中心（P3-A：材料完整性 + 按学生/批次/企业聚合 + 归档动作，owner + 数据范围）═══════════

@router.post("/archive/export", summary="实习归档台账导出 Excel(.xlsx)")
def archive_export(keyword: Optional[str] = None, batchId: Optional[str] = None,
                   user=Depends(get_current_user)):
    data = arch.export_archives(user=user, keyword=keyword, batch_id=batchId)
    audit_log.record("导出实习归档台账", "internship-archive:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/archive/by-batch", summary="归档完整度·按批次聚合")
def archive_by_batch(user=Depends(get_current_user)):
    return success(arch.by_batch(user=user))


@router.get("/archive/by-enterprise", summary="归档完整度·按企业聚合")
def archive_by_enterprise(user=Depends(get_current_user)):
    return success(arch.by_enterprise(user=user))


@router.get("/archive", summary="归档中心·按学生（材料完整性 + 缺失提醒）")
def archive_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                 keyword: Optional[str] = None, batchId: Optional[str] = None,
                 onlyIncomplete: bool = False, user=Depends(get_current_user)):
    items, total = arch.list_by_student(page, pageSize, keyword=keyword, batch_id=batchId,
                                        only_incomplete=onlyIncomplete, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/archive/{internship_id}", summary="学生归档详情（材料清单 + 归档留痕）")
def archive_detail(internship_id: str, user=Depends(get_current_user)):
    return success(arch.get_archive(internship_id, user=user))


@router.post("/archive/{internship_id}/archive", summary="归档学生（完整性快照，缺失需 force）")
def archive_do(internship_id: str, body: dict = Body(default={}), user=Depends(get_current_user)):
    result = arch.archive_student(user, internship_id, force=bool((body or {}).get("force")))
    audit_log.record("归档实习学生", f"internship-archive:{internship_id}", detail=result)
    return success(result, message="已归档")


@router.post("/archive/{internship_id}/revoke", summary="撤销归档（原因≥5字）")
def archive_revoke(internship_id: str, body: dict = Body(...), user=Depends(get_current_user)):
    result = arch.revoke_archive(user, internship_id, (body or {}).get("reason") or "")
    audit_log.record("撤销实习归档", f"internship-archive:{internship_id}", detail=result)
    return success(result, message="已撤销归档")


@router.post("/archive/{internship_id}/package", summary="生成归档包 zip（manifest + 材料清单 + 已有扫描件）")
def archive_package(internship_id: str, user=Depends(get_current_user)):
    result = arch.build_package(user, internship_id)
    audit_log.record("生成实习归档包", f"internship-archive:{internship_id}", detail=result)
    return success(result, message="归档包已生成")


# ═══════════ 统计中心（P3-B：15 项指标 + 成绩分布 + 学院/专业/班级维度，owner + 数据范围）═══════════

@router.get("/stats/overview", summary="实习统计总览（指标口径对齐 06 矩阵，按数据范围）")
def stats_overview(college: Optional[str] = None, major: Optional[str] = None,
                   className: Optional[str] = None, user=Depends(get_current_user)):
    data = stats.overview(user, college=college, major=major, class_name=className)
    audit_log.record("查看实习统计", "internship-stats:overview",
                     detail={"dim": {"college": college, "major": major, "className": className}})
    return success(data)


@router.get("/stats/dimensions", summary="统计可选维度（数据范围内学院/专业/班级）")
def stats_dimensions(user=Depends(get_current_user)):
    return success(stats.dimension_options(user))


@router.post("/stats/export", summary="实习统计报表导出 Excel(.xlsx)")
def stats_export(college: Optional[str] = None, major: Optional[str] = None,
                 className: Optional[str] = None, user=Depends(get_current_user)):
    data = stats.export_stats(user, college=college, major=major, class_name=className)
    audit_log.record("导出实习统计报表", "internship-stats:export", detail={"rowCount": data["rowCount"]})
    return success(data)


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
