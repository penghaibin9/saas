"""岗位实习域 API（/api/v1/internship/*）。真实走库；写操作落审计。"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Query, Response, UploadFile
from fastapi.responses import StreamingResponse

from app.core.response import paginate, success
from app.core.permissions import require_permission
from app.modules.internship.schemas.internship import (BatchCreate, BatchUpdate, BlacklistRequest, ContactCreate,
                                     ContactUpdate, CoopActionRequest, EnterpriseCreate,
                                     EnterpriseImport, EnterpriseReview, EnterpriseUpdate,
                                     ExceptionHandleRequest, ImportErrorsExport, ReportReviewRequest,
                                     VoidBatchRequest)
from app.services import audit_log
from app.modules.internship.services import internship_enterprise_service as ent
from app.modules.internship.services import internship_agreement_service as agr
from app.modules.internship.services import internship_enterprise_eval_service as ee
from app.modules.internship.services import internship_guidance_service as gd
from app.modules.internship.services import internship_leave_service as lv
from app.modules.internship.services import internship_makeup_service as mk
from app.modules.internship.services import internship_risk_service as risk
from app.modules.internship.services import internship_score_service as score
from app.modules.internship.services import internship_service as svc
from app.modules.internship.services import internship_student_service as student_svc
from app.modules.internship.services import internship_student_eval_service as se
from app.modules.internship.services import internship_visit_service as vis
from app.services import xlsx_util

_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# 企业库导入导出已全部迁至公共 Excel 底座（app.services.excel）：
# 字段/校验/模板/错误行/台账由 internship_enterprise_service 的 ImportSpec/ExportSpec 定义。

router = APIRouter(prefix="/internship", tags=["岗位实习"])


@router.get("/dashboard", summary="实习中心看板")
def dashboard(batchId: Optional[str] = None, user=Depends(require_permission("internship.dashboard.view"))):
    return success(svc.get_dashboard_summary(user=user, batch_id=batchId))


@router.get("/students", summary="实习学生列表（分页+筛选）")
def students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, classId: Optional[str] = None,
             status: Optional[str] = None, riskLevel: Optional[str] = None,
             batchId: Optional[str] = None, response: Response = None,
             user=Depends(require_permission("internship.student.view"))):
    """Deprecated compatibility alias for the batch-scoped intern-students API."""
    items, total = student_svc.list_students(page, pageSize, keyword=keyword, class_id=classId,
        status=status, risk_level=riskLevel, batch_id=batchId, user=user)
    if response is not None:
        response.headers["Deprecation"] = "true"
        response.headers["Link"] = '</api/v1/internship/intern-students>; rel="successor-version"'
    payload = paginate(items, total, page, pageSize)
    payload["deprecated"] = True
    return success(payload)


@router.get("/students/{record_id}", summary="实习学生详情（兼容层，请改用 /intern-students/{id}）")
def student_detail(record_id: str, response: Response = None,
                   user=Depends(require_permission("internship.student.view"))):
    if response is not None:
        response.headers["Deprecation"] = "true"
        response.headers["Link"] = f'</api/v1/internship/intern-students/{record_id}>; rel="successor-version"'
    data = student_svc.get_student(record_id, user=user)
    if isinstance(data, dict):
        data["deprecated"] = True
    return success(data)


@router.get("/checkins", summary="打卡台账（按数据范围）")
def checkins(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             result: Optional[str] = None, keyword: Optional[str] = None,
             internshipId: Optional[str] = None, batchId: Optional[str] = None,
             user=Depends(require_permission("internship.attendance.view"))):
    items, total = svc.list_checkins(page, pageSize, result=result, keyword=keyword,
                                     internship_id=internshipId, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/checkins/export", summary="打卡台账导出 Excel(.xlsx)")
def checkins_export(result: Optional[str] = None, keyword: Optional[str] = None, batchId: Optional[str] = None,
                    user=Depends(require_permission("internship.attendance.export"))):
    data = svc.export_checkins(result=result, keyword=keyword, batch_id=batchId, user=user)
    audit_log.record("导出打卡台账", "internship-checkin:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/exceptions", summary="打卡异常列表")
def exceptions(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               type: Optional[str] = None, status: Optional[str] = None,
               keyword: Optional[str] = None, batchId: Optional[str] = None,
               user=Depends(require_permission("internship.attendance.view"))):
    items, total = svc.list_attendance_exceptions(page, pageSize, type=type, status=status,
                                                  keyword=keyword, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/exceptions/export", summary="打卡异常台账导出 Excel(.xlsx)")
def exceptions_export(type: Optional[str] = None, status: Optional[str] = None,
                      keyword: Optional[str] = None, batchId: Optional[str] = None,
                      user=Depends(require_permission("internship.attendance.export"))):
    data = svc.export_exceptions(type=type, status=status, keyword=keyword, batch_id=batchId, user=user)
    audit_log.record("导出打卡异常台账", "internship-exception:export",
                     detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/exceptions/{exception_id}", summary="打卡异常详情（含处理留痕）")
def exception_detail(exception_id: str, user=Depends(require_permission("internship.attendance.view"))):
    return success(svc.get_exception_detail(exception_id, user=user))


@router.post("/exceptions/{exception_id}/handle", summary="处理打卡异常（合理/异常/转风险，意见≥5字）")
def handle_exception(exception_id: str, body: ExceptionHandleRequest,
                     user=Depends(require_permission("internship.attendance.review"))):
    result = svc.handle_attendance_exception(
        exception_id, body.action, body.comment, user=user,
        expected_version=body.expectedVersion if body.expectedVersion is not None else body.version)
    audit_log.record("处理打卡异常", f"internship-exception:{exception_id}",
                     detail={"action": body.action})
    return success(result, message="已处理")


# ═══ 补卡审批（PC 管理端·owner+数据范围；学生申请/撤回在 /mobile/internship/makeup/*） ═══

@router.get("/makeups", summary="补卡审批台账（按数据范围，必须指定批次）")
def makeups(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            status: Optional[str] = None, batchId: Optional[str] = None,
            user=Depends(require_permission("internship.makeup.view"))):
    items, total = mk.list_makeups(page, pageSize, status=status, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/makeups/{makeup_id}", summary="补卡申请详情（含审批留痕）")
def makeup_detail(makeup_id: str, user=Depends(require_permission("internship.makeup.view"))):
    return success(mk.get_makeup(makeup_id, user=user))


@router.post("/makeups/{makeup_id}/approve", summary="补卡·通过（owner 校验，真实补写打卡）")
def makeup_approve(makeup_id: str, body: dict = Body(default={}), user=Depends(require_permission("internship.makeup.review"))):
    result = mk.review(user, makeup_id, "APPROVE", (body or {}).get("comment") or "",
                       expected_version=(body or {}).get("expectedVersion", (body or {}).get("version")))
    audit_log.record("审批补卡·通过", f"internship-makeup:{makeup_id}", detail=result)
    return success(result, message="已通过")


@router.post("/makeups/{makeup_id}/reject", summary="补卡·驳回（owner 校验，原因≥5字）")
def makeup_reject(makeup_id: str, body: dict = Body(...), user=Depends(require_permission("internship.makeup.review"))):
    result = mk.review(user, makeup_id, "REJECT", (body or {}).get("comment") or "",
                       expected_version=(body or {}).get("expectedVersion", (body or {}).get("version")))
    audit_log.record("审批补卡·驳回", f"internship-makeup:{makeup_id}", detail=result)
    return success(result, message="已驳回")


@router.post("/makeups/export", summary="补卡审批台账导出 Excel(.xlsx)")
def makeups_export(status: Optional[str] = None, batchId: Optional[str] = None,
                   user=Depends(require_permission("internship.makeup.export"))):
    data = mk.export_makeups(status=status, batch_id=batchId, user=user)
    audit_log.record("导出补卡审批台账", "internship-makeup:export",
                     detail={"rowCount": data["rowCount"], "batchId": batchId})
    return success(data)


# ═══ 指导记录（owner + 数据范围） ═══

@router.get("/guidances", summary="指导记录列表（按数据范围）")
def guidances(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, batchId: Optional[str] = None,
              user=Depends(require_permission("internship.guidance.view"))):
    items, total = gd.list_guidances(page, pageSize, keyword=keyword, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/guidances/stats", summary="指导记录统计（按数据范围）")
def guidance_stats(threshold: int = Query(2, ge=0, le=100), batchId: Optional[str] = None,
                   user=Depends(require_permission("internship.guidance.view"))):
    return success(gd.guidance_stats(threshold=threshold, batch_id=batchId, user=user))


@router.get("/guidance-plans", summary="指导计划达成列表（按批次规则实时聚合）")
def guidance_plans(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                   keyword: Optional[str] = None, planStatus: Optional[str] = None,
                   insufficientOnly: bool = False, batchId: Optional[str] = None,
                   user=Depends(require_permission("internship.guidance.view"))):
    items, total = gd.list_guidance_plans(page, pageSize, keyword=keyword,
                                          plan_status=planStatus,
                                          insufficient_only=insufficientOnly, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/guidance-plans/export", summary="导出指导计划达成台账")
def guidance_plans_export(keyword: Optional[str] = None, batchId: Optional[str] = None,
                          user=Depends(require_permission("internship.guidance.export"))):
    data = gd.export_guidance_plans(keyword=keyword, batch_id=batchId, user=user)
    audit_log.record("导出指导计划台账", "internship-guidance-plan:export",
                     detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/guidances", summary="新增指导记录（owner：仅本人指导学生）")
def create_guidance(body: dict = Body(...), user=Depends(require_permission("internship.guidance.manage"))):
    result = gd.create(user, body)
    audit_log.record("新增指导记录", f"internship-guidance:{result['id']}", detail=result)
    return success(result, message="已保存")


@router.post("/guidances/export", summary="指导记录台账导出 Excel(.xlsx)")
def guidances_export(keyword: Optional[str] = None, batchId: Optional[str] = None,
                     user=Depends(require_permission("internship.guidance.export"))):
    data = gd.export_guidances(keyword=keyword, batch_id=batchId, user=user)
    audit_log.record("导出指导记录台账", "internship-guidance:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/guidances/{guidance_id}", summary="指导记录详情")
def guidance_detail(guidance_id: str, user=Depends(require_permission("internship.guidance.view"))):
    return success(gd.get_guidance(guidance_id, user=user))


@router.post("/guidances/{guidance_id}/void", summary="撤销指导记录（owner）")
def void_guidance(guidance_id: str, body: dict = Body(default={}), user=Depends(require_permission("internship.guidance.manage"))):
    result = gd.void_guidance(user, guidance_id, (body or {}).get("reason") or "")
    audit_log.record("撤销指导记录", f"internship-guidance:{guidance_id}", detail=result)
    return success(result, message="已撤销")


# ═══ 教师巡访（owner + 数据范围 + 整改跟进） ═══

@router.get("/visits", summary="巡访记录列表（按数据范围）")
def visits(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           keyword: Optional[str] = None, rectify: Optional[str] = None,
           batchId: Optional[str] = None, user=Depends(require_permission("internship.visit.view"))):
    items, total = vis.list_visits(page, pageSize, keyword=keyword, rectify=rectify, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/visits/stats", summary="巡访与整改统计（按数据范围）")
def visit_stats(batchId: Optional[str] = None, user=Depends(require_permission("internship.visit.view"))):
    return success(vis.visit_stats(batch_id=batchId, user=user))


@router.post("/visits", summary="新增巡访记录（owner：仅本人指导学生）")
def create_visit(body: dict = Body(...), user=Depends(require_permission("internship.visit.manage"))):
    result = vis.create(user, body)
    audit_log.record("新增巡访记录", f"internship-visit:{result['id']}", detail=result)
    return success(result, message="已保存")


@router.post("/visits/export", summary="巡访记录台账导出 Excel(.xlsx)")
def visits_export(keyword: Optional[str] = None, batchId: Optional[str] = None,
                  user=Depends(require_permission("internship.visit.export"))):
    data = vis.export_visits(keyword=keyword, batch_id=batchId, user=user)
    audit_log.record("导出巡访记录台账", "internship-visit:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/visits/{visit_id}", summary="巡访记录详情（含月报/整改留痕）")
def visit_detail(visit_id: str, user=Depends(require_permission("internship.visit.view"))):
    return success(vis.get_visit(visit_id, user=user))


@router.post("/visits/{visit_id}/rectify", summary="巡访整改跟进（owner，说明必填）")
def visit_rectify(visit_id: str, body: dict = Body(...), user=Depends(require_permission("internship.visit.manage"))):
    b = body or {}
    result = vis.rectify_follow(user, visit_id, (b.get("status") or "").upper(), b.get("note") or "")
    audit_log.record("巡访整改跟进", f"internship-visit:{visit_id}", detail=result)
    return success(result, message="已跟进")


@router.get("/reports", summary="周报批阅列表")
def reports(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            status: Optional[str] = None, keyword: Optional[str] = None,
            batchId: Optional[str] = None, user=Depends(require_permission("internship.report.view"))):
    items, total = svc.list_weekly_reports(page, pageSize, status=status, keyword=keyword, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/reports/export", summary="导出周报台账")
def reports_export(status: Optional[str] = None, keyword: Optional[str] = None,
                   batchId: Optional[str] = None, user=Depends(require_permission("internship.report.export"))):
    data = svc.export_weekly_reports(status=status, keyword=keyword, batch_id=batchId, user=user)
    audit_log.record("导出周报台账", "internship-report:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/reports/{report_id}", summary="周报详情（含批阅留痕）")
def report_detail(report_id: str, user=Depends(require_permission("internship.report.view"))):
    return success(svc.get_weekly_report_detail(report_id, user=user))


@router.post("/reports/{report_id}/remind", summary="提醒学生处理周报（5分钟防重复）")
def report_remind(report_id: str, body: dict = Body(default={}), user=Depends(require_permission("internship.report.review"))):
    b = body or {}
    return success(svc.remind_weekly_report(report_id, b.get("channel") or "站内消息", user=user),
                   message="提醒已发送")


@router.post("/reports/{report_id}/review", summary="批阅周报（通过/退回，退回原因≥5字）")
def review_report(report_id: str, body: ReportReviewRequest, user=Depends(require_permission("internship.report.review"))):
    result = svc.review_weekly_report(
        report_id, body.action, body.comment, user=user,
        expected_version=body.expectedVersion if body.expectedVersion is not None else body.version)
    audit_log.record("批阅周报", f"internship-report:{report_id}", detail={"action": body.action})
    return success(result, message="批阅完成")


@router.post("/reports/batch-review", summary="批量批阅周报（每条必须带 expectedVersion）")
def reports_batch_review(body: dict = Body(...), user=Depends(require_permission("internship.report.review"))):
    result = svc.batch_review_weekly_reports(body, user=user)
    audit_log.record("批量批阅周报", "internship-report:batch-review",
                     detail={"action": (body or {}).get("action"), "approved": result.get("approvedCount"),
                             "skipped": result.get("skippedCount")})
    return success(result, message="批量批阅完成")


@router.get("/risks", summary="实习风险学生列表")
def risks(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
          level: Optional[str] = None, status: Optional[str] = None,
          keyword: Optional[str] = None, riskCode: Optional[str] = None,
          batchId: Optional[str] = None,
          user=Depends(require_permission("internship.risk.view"))):
    items, total = svc.list_risk_students(
        page, pageSize, level=level, status=status,
        keyword=keyword, risk_code=riskCode, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


# ═══════════ 风险处置闭环（P1-Stage3：受理/跟进/升级/关闭，owner + 审计）═══════════
# 静态子路由 export 声明在 /{rid} 之前，避免被动态段吞掉。

@router.post("/risks/export", summary="风险处置台账导出 Excel(.xlsx)")
def risks_export(keyword: Optional[str] = None, batchId: Optional[str] = None,
                 level: Optional[str] = None, status: Optional[str] = None,
                 user=Depends(require_permission("internship.risk.export"))):
    data = risk.export_risks(keyword=keyword, batch_id=batchId, level=level, status=status, user=user)
    audit_log.record("导出风险处置台账", "internship-risk:export",
                     detail={"rowCount": data["rowCount"], "batchId": batchId})
    return success(data)


@router.get("/risks/{risk_id}", summary="风险单详情（含处置留痕）")
def risk_detail(risk_id: str, user=Depends(require_permission("internship.risk.view"))):
    return success(risk.get_risk(risk_id, user=user))


@router.post("/risks/{risk_id}/handle", summary="受理风险（PENDING→PROCESSING，owner）")
def risk_handle(risk_id: str, body: dict = Body(...), user=Depends(require_permission("internship.risk.handle"))):
    b = body or {}
    result = risk.handle(
        user, risk_id, owner_name=b.get("ownerName"),
        deadline=b.get("deadline"), comment=b.get("comment") or "",
        expected_version=b.get("expectedVersion", b.get("version")))
    audit_log.record("受理实习风险", f"internship-risk:{risk_id}", detail=result)
    return success(result, message="已受理")


@router.post("/risks/{risk_id}/follow", summary="风险跟进（追加跟进说明，owner）")
def risk_follow(risk_id: str, body: dict = Body(...), user=Depends(require_permission("internship.risk.handle"))):
    b = body or {}
    result = risk.follow(user, risk_id, b.get("note") or "",
                         expected_version=b.get("expectedVersion", b.get("version")))
    audit_log.record("跟进实习风险", f"internship-risk:{risk_id}", detail=result)
    return success(result, message="已跟进")


@router.post("/risks/{risk_id}/remind", summary="风险催办（站内提醒责任人，5分钟防重复）")
def risk_remind(risk_id: str, body: dict = Body(default={}),
                user=Depends(require_permission("internship.risk.handle"))):
    result = risk.remind(user, risk_id, (body or {}).get("channel") or "站内消息")
    audit_log.record("催办实习风险", f"internship-risk:{risk_id}", detail=result)
    return success(result, message="已催办")


@router.post("/risks/{risk_id}/escalate", summary="风险升级（提升等级，owner）")
def risk_escalate(risk_id: str, body: dict = Body(...), user=Depends(require_permission("internship.risk.handle"))):
    b = body or {}
    result = risk.escalate(
        user, risk_id, (b.get("level") or "").upper(), b.get("note") or "",
        expected_version=b.get("expectedVersion", b.get("version")))
    audit_log.record("升级实习风险", f"internship-risk:{risk_id}", detail=result)
    return success(result, message="已升级")


@router.post("/risks/{risk_id}/close", summary="风险关闭（化解/关闭归档，owner）")
def risk_close(risk_id: str, body: dict = Body(...), user=Depends(require_permission("internship.risk.handle"))):
    b = body or {}
    result = risk.close(
        user, risk_id, (b.get("result") or "RESOLVED").upper(), b.get("comment") or "",
        expected_version=b.get("expectedVersion", b.get("version")))
    audit_log.record("关闭实习风险", f"internship-risk:{risk_id}", detail=result)
    return success(result, message="已关闭")


# ═══════════ 实习请假审批（P1-Stage3：教师端 owner + 数据范围；学生端在 mobile）═══════════

@router.post("/leaves/export", summary="请假审批台账导出 Excel(.xlsx)")
def leaves_export(status: Optional[str] = None, keyword: Optional[str] = None,
                  batchId: Optional[str] = None, user=Depends(require_permission("internship.leave.export"))):
    data = lv.export_leaves(status=status, keyword=keyword, batch_id=batchId, user=user)
    audit_log.record("导出请假审批台账", "internship-leave:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/leaves/overdue/refresh", summary="刷新请假超期并生成风险单（可由定时任务幂等调用）")
def leave_overdue_refresh(user=Depends(require_permission("internship.leave.review"))):
    result = lv.refresh_overdue(user=user)
    audit_log.record("刷新实习请假超期", "internship-leave:overdue-refresh", detail=result)
    return success(result, message="超期状态已刷新")


@router.get("/leaves", summary="实习请假列表（按数据范围）")
def leaves(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           status: Optional[str] = None, keyword: Optional[str] = None,
           batchId: Optional[str] = None, user=Depends(require_permission("internship.leave.view"))):
    items, total = lv.list_leaves(page, pageSize, status=status, keyword=keyword, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/leaves/{leave_id}", summary="请假详情（含附件/审批留痕）")
def leave_detail(leave_id: str, user=Depends(require_permission("internship.leave.view"))):
    return success(lv.get_leave(leave_id, user=user))


@router.post("/leaves/{leave_id}/review", summary="审批请假（通过/驳回，驳回原因≥5字，owner）")
def leave_review(leave_id: str, body: dict = Body(...), user=Depends(require_permission("internship.leave.review"))):
    b = body or {}
    result = lv.review(
        user, leave_id, (b.get("action") or "").upper(), b.get("comment") or "",
        expected_version=b.get("expectedVersion", b.get("version")))
    audit_log.record("审批实习请假", f"internship-leave:{leave_id}", detail=result)
    return success(result, message="审批完成")


# ═══════════ 三方协议签署实例（P2-A：三方确认状态机，owner + 数据范围）═══════════

@router.post("/agreements/export", summary="三方协议台账导出 Excel(.xlsx)")
def agreements_export(status: Optional[str] = None, keyword: Optional[str] = None,
                      batchId: Optional[str] = None, user=Depends(require_permission("internship.agreement.export"))):
    data = agr.export_agreements(status=status, keyword=keyword, batch_id=batchId, user=user)
    audit_log.record("导出三方协议台账", "internship-agreement:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/agreements", summary="三方协议列表（按数据范围）")
def agreements(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               status: Optional[str] = None, keyword: Optional[str] = None,
               batchId: Optional[str] = None, user=Depends(require_permission("internship.agreement.view"))):
    items, total = agr.list_agreements(page, pageSize, status=status, keyword=keyword, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/agreements", summary="生成协议实例（owner，DRAFT）")
def agreement_generate(body: dict = Body(...), user=Depends(require_permission("internship.agreement.manage"))):
    result = agr.generate(user, body)
    audit_log.record("生成三方协议", f"internship-agreement:{result['id']}", detail=result)
    return success(result, message="已生成协议草稿")


@router.get("/agreements/{agreement_id}", summary="协议详情（含附件/三方确认留痕）")
def agreement_detail(agreement_id: str, user=Depends(require_permission("internship.agreement.view"))):
    return success(agr.get_agreement(agreement_id, user=user))


@router.post("/agreements/{agreement_id}/issue", summary="下发协议（DRAFT→待学生确认）")
def agreement_issue(agreement_id: str, body: dict | None = Body(default=None),
                    user=Depends(require_permission("internship.agreement.manage"))):
    return success(agr.issue(user, agreement_id, body), message="已下发")


@router.post("/agreements/{agreement_id}/enterprise-confirm", summary="记录企业签署（需上传扫描件→待学校确认）")
def agreement_enterprise_confirm(agreement_id: str, body: dict = Body(...), user=Depends(require_permission("internship.agreement.manage"))):
    result = agr.enterprise_confirm(user, agreement_id, body)
    audit_log.record("记录企业签署三方协议", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message="已记录企业签署")


@router.post("/agreements/{agreement_id}/school-confirm", summary="学校确认（待学校确认→已生效）")
def agreement_school_confirm(agreement_id: str, body: dict | None = Body(default=None),
                             user=Depends(require_permission("internship.agreement.manage"))):
    result = agr.school_confirm(user, agreement_id, body)
    audit_log.record("学校确认三方协议生效", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message="协议已生效")


@router.post("/agreements/{agreement_id}/reject", summary="驳回协议（原因≥5字）")
def agreement_reject(agreement_id: str, body: dict = Body(...), user=Depends(require_permission("internship.agreement.manage"))):
    result = agr.reject(user, agreement_id, (body or {}).get("reason") or "", body)
    audit_log.record("驳回三方协议", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message="已驳回")


@router.post("/agreements/{agreement_id}/void", summary="作废协议")
def agreement_void(agreement_id: str, body: dict = Body(default={}), user=Depends(require_permission("internship.agreement.manage"))):
    result = agr.void(user, agreement_id, (body or {}).get("reason") or "", body)
    audit_log.record("作废三方协议", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message="已作废")


@router.post("/agreements/{agreement_id}/archive", summary="归档协议（已生效→已归档）")
def agreement_archive(agreement_id: str, body: dict | None = Body(default=None),
                      user=Depends(require_permission("internship.agreement.manage"))):
    result = agr.archive(user, agreement_id, body)
    audit_log.record("归档三方协议", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message="已归档")


@router.post("/agreements/{agreement_id}/esign/start", summary="发起三方协议电子签（教师/管理端）")
def agreement_esign_start(agreement_id: str, user=Depends(require_permission("internship.agreement.sign"))):
    result = agr.esign_start(user, agreement_id)
    audit_log.record("发起电子签", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message="电子签已发起")


@router.post("/agreements/{agreement_id}/esign/sign", summary="企业/学校电子签署三方协议（教师/管理端）")
def agreement_esign_sign(agreement_id: str, body: dict = Body(default={}), user=Depends(require_permission("internship.agreement.sign"))):
    result = agr.esign_sign(user, agreement_id, (body or {}).get("party", ""))
    audit_log.record("电子签署", f"internship-agreement:{agreement_id}", detail=result)
    return success(result, message="签署完成")


# ═══════════ 企业评价（P2-B：五维评价 + 学校审核，owner + 数据范围）═══════════
# 企业导师本人提交为门户权限预留（source=ENTERPRISE）；学校录入企业纸质评价 source=SCHOOL_RECORDED。

@router.post("/enterprise-evals/export", summary="企业评价台账导出 Excel(.xlsx)")
def enterprise_evals_export(reviewStatus: Optional[str] = None, keyword: Optional[str] = None,
                            batchId: Optional[str] = None,
                            user=Depends(require_permission("internship.eval.enterprise.export"))):
    data = ee.export_evals(review_status=reviewStatus, keyword=keyword, batch_id=batchId, user=user)
    audit_log.record("导出企业评价台账", "internship-enterprise-eval:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/enterprise-evals", summary="企业评价列表（按数据范围）")
def enterprise_evals(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                     reviewStatus: Optional[str] = None, keyword: Optional[str] = None,
                     batchId: Optional[str] = None, user=Depends(require_permission("internship.eval.enterprise.view"))):
    items, total = ee.list_evals(page, pageSize, review_status=reviewStatus, keyword=keyword, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/enterprise-evals", summary="录入企业评价（学校录入企业纸质评价/企业导师提交）")
def enterprise_eval_create(body: dict = Body(...), user=Depends(require_permission("internship.eval.enterprise.manage"))):
    result = ee.create(user, body)
    audit_log.record("录入企业评价", f"internship-enterprise-eval:{result['id']}", detail=result)
    return success(result, message="已录入企业评价")


@router.get("/enterprise-evals/{eval_id}", summary="企业评价详情（含五维/评语/审核留痕）")
def enterprise_eval_detail(eval_id: str, user=Depends(require_permission("internship.eval.enterprise.view"))):
    return success(ee.get_eval(eval_id, user=user))


@router.post("/enterprise-evals/{eval_id}/review", summary="学校审核企业评价（通过/退回，退回原因≥5字）")
def enterprise_eval_review(eval_id: str, body: dict = Body(...), user=Depends(require_permission("internship.eval.enterprise.review"))):
    b = body or {}
    result = ee.review(user, eval_id, (b.get("action") or "").upper(), b.get("comment") or "")
    audit_log.record("审核企业评价", f"internship-enterprise-eval:{eval_id}", detail=result)
    return success(result, message="审核完成")


# ═══════════ 学生鉴定/自评（P2-C：学生自评 + 教师意见 + 学校审核）═══════════

@router.post("/student-evals/export", summary="学生鉴定台账导出 Excel(.xlsx)")
def student_evals_export(reviewStatus: Optional[str] = None, keyword: Optional[str] = None,
                         batchId: Optional[str] = None, user=Depends(require_permission("internship.eval.self.export"))):
    data = se.export_evals(review_status=reviewStatus, keyword=keyword, batch_id=batchId, user=user)
    audit_log.record("导出学生鉴定台账", "internship-student-eval:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/student-evals", summary="学生鉴定列表（按数据范围）")
def student_evals(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                  reviewStatus: Optional[str] = None, keyword: Optional[str] = None,
                  view: Optional[str] = None,
                  batchId: Optional[str] = None, user=Depends(require_permission("internship.eval.self.view"))):
    items, total = se.list_evals(page, pageSize, review_status=reviewStatus, keyword=keyword,
                                 view=view, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/student-evals/{eval_id}", summary="学生鉴定详情（自评/意见/审核留痕）")
def student_eval_detail(eval_id: str, user=Depends(require_permission("internship.eval.self.view"))):
    return success(se.get_eval(eval_id, user=user))


@router.post("/student-evals/{eval_id}/advisor-comment", summary="指导教师填写意见（owner）")
def student_eval_advisor_comment(eval_id: str, body: dict = Body(...), user=Depends(require_permission("internship.eval.advisor.manage"))):
    result = se.advisor_comment(user, eval_id, body)
    audit_log.record("填写学生鉴定指导意见", f"internship-student-eval:{eval_id}", detail=result)
    return success(result, message="已保存意见")


@router.post("/student-evals/{eval_id}/review", summary="学校审核学生鉴定（通过/退回，退回原因≥5字）")
def student_eval_review(eval_id: str, body: dict = Body(...), user=Depends(require_permission("internship.eval.self.review"))):
    b = body or {}
    result = se.review(user, eval_id, (b.get("action") or "").upper(), b.get("comment") or "")
    audit_log.record("审核学生鉴定", f"internship-student-eval:{eval_id}", detail=result)
    return success(result, message="审核完成")


# ═══════════ 实习成绩五项权重（P2-D：权重配置 + 加权核算 + 复核发布，owner + 数据范围）═══════════

@router.get("/scores/config", summary="成绩权重配置（五项权重，和=100）")
def score_config_get(user=Depends(require_permission("internship.score.view"))):
    return success(score.get_config(user=user))


@router.post("/scores/config", summary="保存成绩权重配置（校验权重和=100）")
def score_config_save(body: dict = Body(...), user=Depends(require_permission("internship.score.config"))):
    result = score.save_config(user, body)
    audit_log.record("保存实习成绩权重配置", "internship-score:config", detail=body)
    return success(result, message="配置已保存")


@router.post("/scores/export", summary="实习成绩台账导出 Excel(.xlsx)")
def scores_export(status: Optional[str] = None, keyword: Optional[str] = None,
                  batchId: Optional[str] = None, user=Depends(require_permission("internship.score.export"))):
    data = score.export_scores(status=status, keyword=keyword, batch_id=batchId, user=user)
    audit_log.record("导出实习成绩台账", "internship-score:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/scores", summary="实习成绩列表（按数据范围）")
def scores(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           status: Optional[str] = None, keyword: Optional[str] = None,
           batchId: Optional[str] = None, user=Depends(require_permission("internship.score.view"))):
    items, total = score.list_scores(page, pageSize, status=status, keyword=keyword, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/scores/compute", summary="核算成绩（五项加权，缺项标记，owner）")
def score_compute(body: dict = Body(...), user=Depends(require_permission("internship.score.manage"))):
    result = score.compute(user, body)
    audit_log.record("核算实习成绩", f"internship-score:{result['id']}", detail=result)
    return success(result, message="核算完成")


@router.get("/scores/{score_id}", summary="成绩详情（五项/权重/核算发布留痕）")
def score_detail(score_id: str, user=Depends(require_permission("internship.score.view"))):
    return success(score.get_score(score_id, user=user))


@router.post("/scores/{score_id}/publish", summary="发布成绩（待复核→已发布，缺项拒绝）")
def score_publish(score_id: str, body: dict | None = Body(default=None),
                  user=Depends(require_permission("internship.score.publish"))):
    result = score.publish(user, score_id, (body or {}).get("expectedVersion", (body or {}).get("version")))
    audit_log.record("发布实习成绩", f"internship-score:{score_id}", detail=result)
    return success(result, message="成绩已发布")


@router.post("/scores/{score_id}/return", summary="退回重算（待复核→待核算）")
def score_return(score_id: str, body: dict = Body(default={}), user=Depends(require_permission("internship.score.manage"))):
    result = score.return_recalc(user, score_id, (body or {}).get("reason") or "",
                                 (body or {}).get("expectedVersion", (body or {}).get("version")))
    audit_log.record("退回实习成绩重算", f"internship-score:{score_id}", detail=result)
    return success(result, message="已退回重算")


@router.post("/scores/{score_id}/withdraw", summary="撤回成绩（已发布→已撤回，原因≥5字）")
def score_withdraw(score_id: str, body: dict = Body(...), user=Depends(require_permission("internship.score.publish"))):
    result = score.withdraw(user, score_id, (body or {}).get("reason") or "",
                            (body or {}).get("expectedVersion", (body or {}).get("version")))
    audit_log.record("撤回实习成绩", f"internship-score:{score_id}", detail=result)
    return success(result, message="已撤回")


@router.post("/scores/{score_id}/archive", summary="归档成绩（已发布→已归档）")
def score_archive(score_id: str, body: dict | None = Body(default=None),
                  user=Depends(require_permission("internship.score.manage"))):
    result = score.archive(user, score_id, (body or {}).get("expectedVersion", (body or {}).get("version")))
    audit_log.record("归档实习成绩", f"internship-score:{score_id}", detail=result)
    return success(result, message="已归档")


# ═══════════ 实习批次（组织时间轴 + 规则骨架，状态机 DRAFT→RUNNING→CLOSED→ARCHIVED）═══════════
# 注意：静态子路由 export 声明在 /{bid} 之前，避免被动态段吞掉（同企业库范式）。

@router.post("/batches/export", summary="导出批次 Excel 台账（写审计）")
def batch_export(keyword: Optional[str] = None, status: Optional[str] = None,
                 user=Depends(require_permission("internship.batch.export"))):
    data = svc.export_batches(keyword=keyword, status=status)
    audit_log.record("导出实习批次台账", "internship-batch:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/batches", summary="实习批次列表（分页+筛选）")
def batches(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            keyword: Optional[str] = None, status: Optional[str] = None,
            user=Depends(require_permission("internship.batch.view"))):
    items, total = svc.list_batches(page, pageSize, keyword=keyword, status=status)
    return success(paginate(items, total, page, pageSize))


@router.post("/batches", summary="新建实习批次（草稿态，批次编号租户内唯一）")
def batch_create(body: BatchCreate, user=Depends(require_permission("internship.batch.manage"))):
    result = svc.create_batch(body.model_dump(), user=user)
    audit_log.record("新建实习批次", f"internship-batch:{result['id']}", detail={"batchName": body.batchName})
    return success(result, message="已新建")


@router.get("/batches/{bid}", summary="批次详情（含阶段时间轴/规则配置/审计留痕）")
def batch_detail(bid: str, user=Depends(require_permission("internship.batch.view"))):
    return success(svc.get_batch(bid))


@router.put("/batches/{bid}", summary="编辑批次（已结束/已归档/已作废不可编辑）")
def batch_update(bid: str, body: BatchUpdate, user=Depends(require_permission("internship.batch.manage"))):
    result = svc.update_batch(bid, body.model_dump(exclude_unset=True), user=user)
    audit_log.record("编辑实习批次", f"internship-batch:{bid}")
    return success(result, message="已保存")


@router.post("/batches/{bid}/activate", summary="启用批次（草稿→进行中）")
def batch_activate(bid: str, body: dict | None = Body(default=None),
                   user=Depends(require_permission("internship.batch.manage"))):
    b = body or {}
    result = svc.activate_batch(
        bid, user=user, expected_version=b.get("expectedVersion", b.get("version")))
    audit_log.record("启用实习批次", f"internship-batch:{bid}")
    return success(result, message="已启用")


@router.post("/batches/{bid}/close", summary="结束批次（进行中→已结束；含就绪闸门）")
def batch_close(bid: str, body: dict | None = Body(default=None),
                user=Depends(require_permission("internship.batch.manage"))):
    b = body or {}
    result = svc.close_batch(
        bid, user=user,
        force=bool(b.get("force")),
        force_reason=(b.get("forceReason") or b.get("reason") or ""),
        expected_version=b.get("expectedVersion", b.get("version")),
    )
    audit_log.record("结束实习批次", f"internship-batch:{bid}",
                     detail={"forced": result.get("forced"), "blockingCount": (result.get("readiness") or {}).get("blockingCount")})
    return success(result, message="已强制结束" if result.get("forced") else "已结束")


@router.post("/batches/{bid}/archive", summary="归档批次（已结束→已归档；含就绪闸门）")
def batch_archive(bid: str, body: dict | None = Body(default=None),
                  user=Depends(require_permission("internship.batch.manage"))):
    b = body or {}
    result = svc.archive_batch(
        bid, user=user,
        force=bool(b.get("force")),
        force_reason=(b.get("forceReason") or b.get("reason") or ""),
        expected_version=b.get("expectedVersion", b.get("version")),
    )
    audit_log.record("归档实习批次", f"internship-batch:{bid}",
                     detail={"forced": result.get("forced")})
    return success(result, message="已强制归档" if result.get("forced") else "已归档")


@router.get("/batches/{bid}/readiness", summary="批次结束/归档就绪报告（只读）")
def batch_readiness(bid: str, user=Depends(require_permission("internship.batch.view"))):
    return success(svc.batch_readiness(bid, user=user))


@router.post("/batches/{bid}/void", summary="作废批次（仅草稿，原因≥5字，须带 expectedVersion）")
def batch_void(bid: str, body: VoidBatchRequest, user=Depends(require_permission("internship.batch.manage"))):
    result = svc.void_batch(
        bid, body.reason, user=user,
        expected_version=body.expectedVersion if body.expectedVersion is not None else body.version)
    audit_log.record("作废实习批次", f"internship-batch:{bid}", detail={"reason": body.reason})
    return success(result, message="已作废")


# ═══════════ 企业库（共享企业主档 t_emp_company 之上的实习企业管理）═══════════
# 注意：静态子路由（stats / import / export）声明在 /{company_id} 之前，避免被动态段吞掉。

@router.get("/enterprises", summary="企业库列表（分页+筛选，联系电话脱敏）")
def enterprises(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                keyword: Optional[str] = None, coopStatus: Optional[str] = None,
                industry: Optional[str] = None, region: Optional[str] = None,
                blacklist: Optional[bool] = None, user=Depends(require_permission("internship.enterprise.view"))):
    items, total = ent.list_enterprises(page, pageSize, keyword=keyword, coop_status=coopStatus,
                                        industry=industry, region=region, blacklist=blacklist)
    return success(paginate(items, total, page, pageSize))


@router.get("/enterprises/stats", summary="企业库统计（按合作状态/行业/黑名单）")
def enterprise_stats(user=Depends(require_permission("internship.enterprise.view"))):
    return success(ent.enterprise_stats())


@router.post("/enterprises/import/dry-run", summary="企业库导入·预校验（不写库）")
def enterprise_import_dry_run(body: EnterpriseImport, user=Depends(require_permission("internship.enterprise.manage"))):
    return success(ent.import_dry_run(body.rows))


@router.get("/enterprises/import/template", summary="企业库导入·下载 Excel 模板(.xlsx)")
def enterprise_import_template(user=Depends(require_permission("internship.enterprise.manage"))):
    # 走公共 Excel 底座生成模板（字段/必填/示例/说明由 ImportSpec 统一定义）
    data = ent.import_template_bytes()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=enterprise_import_template.xlsx"})


@router.post("/enterprises/import/xlsx", summary="企业库导入·上传 Excel 解析+预校验（不写库，返回行数据供确认）")
async def enterprise_import_xlsx(file: UploadFile = File(...), user=Depends(require_permission("internship.enterprise.manage"))):
    content = await file.read()
    rows = ent.import_read(content)          # 底座表头映射
    dry = ent.import_dry_run(rows)           # 底座统一预校验
    return success({"rows": rows, **dry})


@router.post("/enterprises/import/errors-xlsx", summary="企业库导入·下载错误行 Excel")
def enterprise_import_errors_xlsx(body: ImportErrorsExport, user=Depends(require_permission("internship.enterprise.manage"))):
    packed = ent.import_errors_pack(body.rows, body.errors)   # 底座生成错误行 Excel
    return success(packed)


@router.post("/enterprises/import/confirm", summary="企业库导入·确认（整批事务，预校验须全通过）")
def enterprise_import_confirm(body: EnterpriseImport, user=Depends(require_permission("internship.enterprise.manage"))):
    result = ent.import_confirm(body.rows)
    audit_log.record("导入企业库", "internship-enterprise:import", detail=result)
    return success(result, message="导入完成")


@router.post("/enterprises/export", summary="企业库导出 Excel 台账（脱敏，写审计）")
def enterprise_export(keyword: Optional[str] = None, coopStatus: Optional[str] = None,
                      industry: Optional[str] = None, region: Optional[str] = None,
                      user=Depends(require_permission("internship.enterprise.export"))):
    data = ent.export_enterprises(keyword=keyword, coop_status=coopStatus,
                                  industry=industry, region=region)
    audit_log.record("导出企业库", "internship-enterprise:export",
                     detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/enterprises", summary="新增企业（初始待审核）")
def create_enterprise(body: EnterpriseCreate, user=Depends(require_permission("internship.enterprise.manage"))):
    result = ent.create_enterprise(body)
    audit_log.record("新增企业", f"internship-enterprise:{result['id']}", detail={"name": result["name"]})
    return success(result, message="已创建")


@router.get("/enterprises/{company_id}", summary="企业详情（含联系人/导师/合作资质/审计）")
def enterprise_detail(company_id: str, user=Depends(require_permission("internship.enterprise.view"))):
    return success(ent.get_enterprise(company_id))


@router.put("/enterprises/{company_id}", summary="编辑企业")
def update_enterprise(company_id: str, body: EnterpriseUpdate, user=Depends(require_permission("internship.enterprise.manage"))):
    result = ent.update_enterprise(company_id, body)
    audit_log.record("编辑企业", f"internship-enterprise:{company_id}")
    return success(result, message="已保存")


@router.post("/enterprises/{company_id}/review", summary="企业资质审核（仅待审核可审：通过→合作中/驳回）")
def review_enterprise(company_id: str, body: EnterpriseReview, user=Depends(require_permission("internship.enterprise.manage"))):
    result = ent.review_enterprise(company_id, body.action, body.comment or "")
    audit_log.record("企业资质审核", f"internship-enterprise:{company_id}", detail={"action": body.action})
    return success(result, message="审核完成")


@router.post("/enterprises/{company_id}/cooperation", summary="合作启停（暂停/恢复/归档）")
def cooperation(company_id: str, body: CoopActionRequest, user=Depends(require_permission("internship.enterprise.manage"))):
    result = ent.set_cooperation(company_id, body.action, body.reason or "")
    audit_log.record("企业合作状态变更", f"internship-enterprise:{company_id}", detail={"action": body.action})
    return success(result, message="已更新")


@router.post("/enterprises/{company_id}/blacklist", summary="拉黑/移出黑名单（拉黑须原因）")
def blacklist(company_id: str, body: BlacklistRequest, user=Depends(require_permission("internship.enterprise.manage"))):
    result = ent.set_blacklist(company_id, body.on, body.reason or "")
    audit_log.record("企业黑名单变更", f"internship-enterprise:{company_id}", detail={"on": body.on})
    return success(result, message="已更新")


@router.get("/enterprises/{company_id}/contacts", summary="企业联系人/导师列表（电话脱敏）")
def list_contacts(company_id: str, user=Depends(require_permission("internship.enterprise.view"))):
    return success({"items": ent.list_contacts(company_id)})


@router.post("/enterprises/{company_id}/contacts", summary="新增联系人/企业导师")
def add_contact(company_id: str, body: ContactCreate, user=Depends(require_permission("internship.enterprise.manage"))):
    result = ent.add_contact(company_id, body)
    audit_log.record("新增企业联系人", f"internship-enterprise:{company_id}", detail={"name": result["name"]})
    return success(result, message="已新增")


@router.put("/enterprises/{company_id}/contacts/{contact_id}", summary="编辑联系人/企业导师")
def update_contact(company_id: str, contact_id: str, body: ContactUpdate,
                   user=Depends(require_permission("internship.enterprise.manage"))):
    result = ent.update_contact(company_id, contact_id, body)
    audit_log.record("编辑企业联系人", f"internship-enterprise:{company_id}")
    return success(result, message="已保存")


@router.delete("/enterprises/{company_id}/contacts/{contact_id}", summary="删除联系人/企业导师（软删）")
def delete_contact(company_id: str, contact_id: str, user=Depends(require_permission("internship.enterprise.manage"))):
    result = ent.delete_contact(company_id, contact_id)
    audit_log.record("删除企业联系人", f"internship-enterprise:{company_id}")
    return success(result, message="已删除")
