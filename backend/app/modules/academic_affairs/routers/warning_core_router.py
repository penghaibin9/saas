"""D9-S2 学业预警公开 Router：从 legacy academic_affairs Move Only。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.services import academic_affairs_warning_service as warn_svc


router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])

_WARN_VIEW = "academicAffairs.warning.view"
_WARN_HANDLE = "academicAffairs.warning.handle"
_WARN_RULE = "academicAffairs.warning.rule.manage"


class WarningAssignBody(BaseModel):
    ownerId: Optional[str] = None
    ownerName: str = Field(..., min_length=1)


class WarningInterventionBody(BaseModel):
    way: str = Field("TALK", description="TALK/PHONE/FAMILY/PLAN")
    content: str = Field(..., min_length=1)
    result: Optional[str] = ""
    nextPlan: Optional[str] = ""


class WarningReasonBody(BaseModel):
    reason: str = Field(..., min_length=1)


class WarningResultBody(BaseModel):
    result: str = Field(..., min_length=1)


class WarningRuleSaveBody(BaseModel):
    value: float = Field(..., description="规则阈值（int 规则取整数部分）")


@router.post("/warnings/scan", summary="学业预警扫描（挂科规则，幂等）")
def warning_scan(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_warnings(user))


@router.post("/warnings/scan/credit", summary="学分预警扫描（学分完成率，幂等）")
def warning_scan_credit(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_credit_warnings(user))


@router.post("/warnings/scan/gpa", summary="绩点预警扫描（幂等）")
def warning_scan_gpa(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_gpa_warnings(user))


@router.post("/warnings/scan/retake", summary="补考重修预警扫描（幂等）")
def warning_scan_retake(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_retake_warnings(user))


@router.post("/warnings/scan/graduation", summary="毕业风险预警扫描（联动毕业预审 SYSTEM_ABNORMAL，幂等）")
def warning_scan_graduation(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_graduation_warnings(user))


@router.post("/warnings/scan/attendance", summary="旷课预警扫描（课堂考勤已提交场次，幂等）")
def warning_scan_attendance(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_attendance_warnings(user))


@router.post("/warnings/scan/all", summary="预警看板一键扫描（挂科/学分/绩点/重修/毕业/旷课，幂等）")
def warning_scan_all(user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.scan_all(user))


@router.get("/warnings/rules", summary="预警规则阈值列表")
def warning_rules(user=Depends(require_permission(_WARN_RULE))):
    return success({"items": warn_svc.get_rules(user)})


@router.put("/warnings/rules/{key}", summary="保存预警规则阈值")
def warning_rule_save(body: WarningRuleSaveBody, key: str = Path(...),
                      user=Depends(require_permission(_WARN_RULE))):
    return success(warn_svc.save_rule(user, key, body.value), message="已保存")


@router.get("/warnings/summary", summary="预警看板/统计聚合（按来源/等级/状态分组）")
def warning_summary(user=Depends(require_permission(_WARN_VIEW))):
    return success(warn_svc.warning_summary(user))


# 静态子路径必须注册在 /warnings/{warningId} 之前，避免 Starlette 将字面量当 int 动态路径。
@router.get("/warnings/notifications", summary="预警通知台账（已推送的站内通知列表）")
def warning_notifications(warningId: Optional[int] = None, page: int = 1, pageSize: int = 20,
                          user=Depends(require_permission(_WARN_VIEW))):
    items, total = warn_svc.list_notifications(user, warningId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/warnings/notifications/summary", summary="预警通知台账统计（累计/未读/已读）")
def warning_notifications_summary(user=Depends(require_permission(_WARN_VIEW))):
    return success(warn_svc.notification_summary(user))


@router.get("/warnings", summary="学业预警列表（支持来源多维筛选：挂科/学分/绩点/补考重修/毕业风险）")
def warnings(level: Optional[str] = None, status: Optional[str] = None, sourceCode: Optional[str] = None,
             page: int = 1, pageSize: int = 20, user=Depends(require_permission(_WARN_VIEW))):
    items, total = warn_svc.list_warnings(user, level, status, sourceCode, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/warnings/{warningId}", summary="学业预警详情（含学生信息+跟进记录）")
def warning_detail(warningId: int = Path(...), user=Depends(require_permission(_WARN_VIEW))):
    return success(warn_svc.get_warning_detail(user, warningId))


@router.post("/warnings/{warningId}/assign", summary="指派预警跟进人")
def warning_assign(body: WarningAssignBody, warningId: int = Path(...),
                   user=Depends(require_permission(_WARN_HANDLE))):
    return success(warn_svc.assign_warning(user, warningId, body.ownerId, body.ownerName), message="已指派")


@router.post("/warnings/{warningId}/interventions", summary="新增预警跟进记录（内容≥5字）")
def warning_intervention(body: WarningInterventionBody, warningId: int = Path(...),
                         user=Depends(require_permission(_WARN_HANDLE))):
    return success(warn_svc.add_intervention(user, warningId, body.way, body.content, body.result or "",
                                             body.nextPlan or ""), message="已记录")


@router.post("/warnings/{warningId}/escalate", summary="升级预警（说明≥5字）")
def warning_escalate(body: WarningReasonBody, warningId: int = Path(...),
                     user=Depends(require_permission(_WARN_HANDLE))):
    return success(warn_svc.escalate_warning(user, warningId, body.reason), message="已升级")


@router.post("/warnings/{warningId}/close", summary="关闭预警（说明≥5字）")
def warning_close(body: WarningResultBody, warningId: int = Path(...),
                  user=Depends(require_permission(_WARN_HANDLE))):
    return success(warn_svc.close_warning(user, warningId, body.result), message="已关闭")


@router.post("/warnings/{warningId}/void", summary="作废预警（误报原因≥5字）")
def warning_void(body: WarningReasonBody, warningId: int = Path(...),
                 user=Depends(require_permission(_WARN_HANDLE))):
    return success(warn_svc.void_warning(user, warningId, body.reason), message="已作废")


@router.post("/warnings/{warningId}/remind", summary="提醒预警责任人")
def warning_remind(warningId: int = Path(...), user=Depends(require_permission(_WARN_HANDLE))):
    return success(warn_svc.remind_warning(user, warningId), message="已提醒")
