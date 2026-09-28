"""Teacher Miniapp internship evidence and G16 teacher execution routes.

Mounted under the additive /teacher-mobile/internship surface. Teacher-owned activity facts
remain separate from student check-in/report facts.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.permissions import require_module, require_permission
from app.core.response import success
from app.modules.internship.services import internship_teacher_activity_service as activity_svc
from app.services import teacher_mobile_internship_evidence_service as svc

router = APIRouter(
    prefix="/internship",
    tags=["teacher-mobile-internship-v3"],
    dependencies=[Depends(require_module("internship"))],
)


class _StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VisitEvidenceBody(_StrictBody):
    planId: int = Field(gt=0)
    visitType: Literal["ONSITE", "ONLINE", "PHONE", "VIDEO", "OTHER"]
    contactPerson: str = Field(min_length=2, max_length=100)
    workStatus: str = Field(min_length=2, max_length=300)
    enterpriseFeedback: str = Field(min_length=2, max_length=1000)
    facts: str = Field(min_length=10, max_length=1600)
    issues: str | None = Field(default=None, max_length=500)
    advice: str | None = Field(default=None, max_length=500)
    needFollow: bool = False
    needRisk: bool = False
    riskLevel: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    riskReason: str | None = Field(default=None, max_length=500)
    fileIds: list[str] = Field(default_factory=list, max_length=1)
    location: None = None
    expectedVersion: int = Field(ge=0)


class TeacherCheckinBody(_StrictBody):
    batchId: int = Field(gt=0)
    timezoneName: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracyM: float | None = Field(default=None, ge=0)
    address: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)


class TeacherWorkReportBody(_StrictBody):
    batchId: int = Field(gt=0)
    reportDate: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    workContent: str = Field(min_length=10, max_length=8000)
    issueContent: str | None = Field(default=None, max_length=4000)
    nextPlan: str | None = Field(default=None, max_length=4000)
    studentCount: int | None = Field(default=None, ge=0)
    attachmentFileIds: list[str] = Field(default_factory=list, max_length=9)
    expectedVersion: int | None = Field(default=None, ge=0)


class TeacherPeriodReportBody(_StrictBody):
    batchId: int = Field(gt=0)
    reportType: Literal["WEEKLY", "MONTHLY", "SUMMARY"]
    periodKey: str = Field(min_length=4, max_length=32)
    content: str = Field(min_length=30, max_length=12000)
    issueContent: str | None = Field(default=None, max_length=4000)
    nextPlan: str | None = Field(default=None, max_length=4000)
    studentCount: int | None = Field(default=None, ge=0)
    attachmentFileIds: list[str] = Field(default_factory=list, max_length=9)
    expectedVersion: int | None = Field(default=None, ge=0)


class EmergencyNoticeBody(_StrictBody):
    batchId: int = Field(gt=0)
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=5, max_length=5000)


class NoticeWithdrawBody(_StrictBody):
    reason: str = Field(min_length=2, max_length=500)


@router.get(
    "/visit-targets",
    summary="教师端巡访计划执行目标（含实习记录版本）",
    name="teacher_mobile_v3_visit_targets",
)
def visit_targets(user=Depends(require_permission("internship.visit.view"))):
    return success(svc.list_visit_targets(user))


@router.post(
    "/weekly-reports/{report_id}/remind",
    summary="教师端逾期周报单学生站内催交",
    name="teacher_mobile_v3_weekly_report_remind",
)
def remind_weekly_report(
    report_id: int,
    user=Depends(require_permission("internship.report.review")),
):
    return success(
        svc.remind_overdue_weekly_report(user, report_id),
        message="催交提醒已进入站内消息队列",
    )


@router.post(
    "/visits/{internship_id}",
    summary="教师端巡访执行证据登记",
    name="teacher_mobile_v3_visit_evidence_create",
)
def create_visit_evidence(
    internship_id: int,
    body: VisitEvidenceBody,
    user=Depends(require_permission("internship.visit.manage")),
):
    return success(
        svc.create_visit_evidence(user, internship_id, body.model_dump(exclude_none=True)),
        message="巡访执行证据已保存",
    )


@router.get("/activity/checkins", summary="教师本人签到记录")
def my_teacher_checkins(
    batchId: int = Query(..., ge=1),
    limit: int = Query(31, ge=1, le=366),
    user=Depends(require_permission("internship.guidance.view")),
):
    return success(activity_svc.list_my_checkins(user, batch_id=batchId, limit=limit))


@router.post("/activity/checkins", summary="教师本人现场签到")
def teacher_checkin(
    body: TeacherCheckinBody,
    user=Depends(require_permission("internship.guidance.manage")),
):
    return success(
        activity_svc.checkin(user, body.model_dump(exclude_none=True)),
        message="教师签到已记录",
    )


@router.get("/activity/work-reports", summary="教师本人工作报告")
def my_teacher_work_reports(
    batchId: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("internship.guidance.view")),
):
    return success(
        activity_svc.list_my_work_reports(
            user, batch_id=batchId, page=page, page_size=pageSize
        )
    )


@router.post("/activity/work-reports", summary="提交或版本更新教师本人工作报告")
def save_teacher_work_report(
    body: TeacherWorkReportBody,
    user=Depends(require_permission("internship.guidance.manage")),
):
    return success(
        activity_svc.save_work_report(user, body.model_dump(exclude_none=True)),
        message="教师工作报告已保存",
    )


@router.get("/activity/period-reports", summary="教师本人周报/月报/总结")
def my_teacher_period_reports(
    batchId: int = Query(..., ge=1),
    reportType: Literal["WEEKLY", "MONTHLY", "SUMMARY"] | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("internship.guidance.view")),
):
    return success(
        activity_svc.list_my_period_reports(
            user,
            batch_id=batchId,
            report_type=reportType,
            page=page,
            page_size=pageSize,
        )
    )


@router.post("/activity/period-reports", summary="提交或版本更新教师本人周报/月报/总结")
def save_teacher_period_report(
    body: TeacherPeriodReportBody,
    user=Depends(require_permission("internship.guidance.manage")),
):
    return success(
        activity_svc.save_period_report(user, body.model_dump(exclude_none=True)),
        message="教师周期报告已保存",
    )


@router.get("/emergency-notices", summary="当前范围批次紧急通知")
def teacher_emergency_notices(
    batchId: int = Query(..., ge=1),
    includeWithdrawn: bool = Query(True),
    user=Depends(require_permission("internship.communication.view")),
):
    return success(
        activity_svc.list_teacher_notices(
            user, batch_id=batchId, include_withdrawn=includeWithdrawn
        )
    )


@router.post("/emergency-notices", summary="校级管理员发布批次紧急通知")
def publish_emergency_notice(
    body: EmergencyNoticeBody,
    user=Depends(require_permission("internship.communication.manage")),
):
    return success(
        activity_svc.publish_emergency_notice(user, body.model_dump()),
        message="紧急通知已持久发布",
    )


@router.post("/emergency-notices/{notice_id}/withdraw", summary="校级管理员撤回紧急通知")
def withdraw_emergency_notice(
    notice_id: int,
    body: NoticeWithdrawBody,
    user=Depends(require_permission("internship.communication.manage")),
):
    return success(
        activity_svc.withdraw_emergency_notice(user, notice_id, body.reason),
        message="紧急通知已撤回",
    )
