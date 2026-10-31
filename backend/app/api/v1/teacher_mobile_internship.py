"""Teacher Miniapp internship evidence and G16 teacher execution routes.

Mounted under the additive /teacher-mobile/internship surface. Teacher-owned activity facts
remain separate from student check-in/report facts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.core.permissions import require_module, require_permission
from app.core.response import success
from app.modules.internship.services import internship_teacher_activity_service as activity_svc
from app.services import teacher_mobile_internship_evidence_service as svc
from app.modules.internship.schemas.internship_visit import VisitLocation
from app.modules.internship.services import internship_employment_service as employment_svc

router = APIRouter(
    prefix="/internship",
    tags=["teacher-mobile-internship-v3"],
    dependencies=[Depends(require_module("internship"))],
)

@router.get('/employment', summary='数据范围内就业上报分页与状态')
def employment_registrations(batchId:int=Query(...,ge=1),internshipId:int|None=Query(None,ge=1),status:str=Query('ALL'),page:int=Query(1,ge=1),
    pageSize:int=Query(20,ge=1,le=100),user=Depends(require_permission('internship.employment.view'))):
    return success(employment_svc.list_for_teacher(user,batch_id=batchId,internship_id=internshipId,status=status,page=page,page_size=pageSize))

@router.post('/employment/export', summary='导出当前筛选的脱敏就业上报台账')
def export_employment_registrations(batchId:int=Query(...,ge=1),internshipId:int|None=Query(None,ge=1),
    status:str=Query('ALL'),user=Depends(require_permission('internship.stats.export'))):
    return success(employment_svc.export_registrations(user,batch_id=batchId,internship_id=internshipId,status=status))

@router.get('/employment/{registration_id}', summary='查看就业登记当前版本与完整历史')
def employment_registration(registration_id:int,user=Depends(require_permission('internship.employment.view'))):
    return success(employment_svc.get_for_teacher(user,registration_id))

@router.post('/employment/{registration_id}/disclose', summary='说明用途并留痕查看完整就业登记')
def disclose_employment_registration(registration_id:int,body:dict=Body(...),user=Depends(require_permission('internship.employment.sensitive.view'))):
    return success(employment_svc.disclose_for_teacher(user,registration_id,body))

@router.post('/employment/{registration_id}/review', summary='核验或退回就业登记的明确版本')
def review_employment_registration(registration_id:int,body:dict=Body(...),user=Depends(require_permission('internship.employment.review'))):
    return success(employment_svc.review(user,registration_id,body),message='就业登记审核结果已保存')


class _StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VisitEvidenceBody(_StrictBody):
    batchId: int = Field(gt=0)
    planId: int = Field(gt=0)
    expectedPlanVersion: int = Field(strict=True, ge=0)
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
    title: str | None = Field(default=None, min_length=2, max_length=200)
    location: VisitLocation | None = None
    expectedVersion: int = Field(strict=True, ge=0)


class TeacherCheckinBody(_StrictBody):
    batchId: int = Field(gt=0)
    timezoneName: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    accuracyM: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    address: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)
    photoFileId: str | None = Field(default=None, max_length=64)
    coordinateSystem: Literal["GCJ02", "WGS84"] | None = None
    countryRegion: str | None = Field(default=None, max_length=100)
    locationProvider: str | None = Field(default=None, max_length=50)
    mockLocation: StrictBool = False
    deviceRiskFlags: list[Literal['MOCK_LOCATION','EMULATOR','ROOTED','JAILBROKEN','DEVICE_UNTRUSTED']] = Field(default_factory=list, max_length=10)


class TeacherMakeupBody(_StrictBody):
    batchId: int = Field(gt=0)
    localDate: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reason: str = Field(min_length=5, max_length=500)
    evidenceFileId: str | None = Field(default=None, max_length=64)


class TeacherWorkReportBody(_StrictBody):
    batchId: int = Field(gt=0)
    reportDate: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    workContent: str = Field(min_length=10, max_length=8000)
    issueContent: str | None = Field(default=None, max_length=4000)
    nextPlan: str | None = Field(default=None, max_length=4000)
    studentCount: int | None = Field(default=None, ge=0)
    attachmentFileIds: list[str] = Field(default_factory=list, max_length=9)
    audienceScope: Literal["ALL", "COLLEGE"] = "ALL"
    recipientCollegeIds: list[int] = Field(default_factory=list, max_length=100)
    expectedVersion: int | None = Field(default=None, ge=0)


class TeacherPeriodReportBody(_StrictBody):
    batchId: int = Field(gt=0)
    reportType: Literal["WEEKLY", "MONTHLY", "SUMMARY"]
    periodKey: str = Field(min_length=4, max_length=32)
    content: str = Field(min_length=30, max_length=12000)
    issueContent: str | None = Field(default=None, max_length=4000)
    nextPlan: str | None = Field(default=None, max_length=4000)
    studentCount: int | None = Field(default=None, ge=0, le=2147483647)
    attachmentFileIds: list[str] = Field(default_factory=list, max_length=9)
    expectedVersion: int | None = Field(default=None, ge=0)


class EmergencyNoticeBody(_StrictBody):
    batchId: int = Field(gt=0)
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=5, max_length=5000)
    noticeType: Literal["AGREEMENT", "TRAINING", "SAFETY", "NOTICE", "OTHER"] = "NOTICE"
    schoolCategory: str = Field(default="",max_length=50)
    urgency: Literal["NORMAL", "IMPORTANT", "URGENT"] = "IMPORTANT"
    validFrom: datetime | None = None
    validUntil: datetime | None = None
    attachmentFileIds: list[str] = Field(default_factory=list, max_length=9)
    audienceScope: Literal["ALL", "COLLEGE"] = "ALL"
    recipientCollegeIds: list[int] = Field(default_factory=list, max_length=100)


class NoticeWithdrawBody(_StrictBody):
    reason: str = Field(min_length=2, max_length=500)


@router.get(
    "/visit-targets",
    summary="教师端巡访计划执行目标（含实习记录版本）",
    name="teacher_mobile_v3_visit_targets",
)
def visit_targets(batchId: int = Query(..., ge=1), page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50), planId: int | None = Query(None, ge=1),
    studentPage: int = Query(1, ge=1), studentPageSize: int = Query(20, ge=1, le=100),
    internshipId: int | None = Query(None, ge=1), keyword: str = Query('', max_length=100),
    user=Depends(require_permission("internship.visit.view"))):
    return success(svc.list_visit_targets(user, batch_id=batchId, page=page, page_size=pageSize,
        plan_id=planId, student_page=studentPage, student_page_size=studentPageSize, internship_id=internshipId, keyword=keyword))


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
    month: str | None = Query(None, pattern=r'^\d{4}-\d{2}$'),
    user=Depends(require_permission("internship.guidance.view")),
):
    return success(activity_svc.list_my_checkins(user, batch_id=batchId, limit=limit, month=month))


@router.get('/activity/checkin-rule', summary='教师当前批次签到范围')
def my_teacher_checkin_rule(batchId: int = Query(..., ge=1),
                           user=Depends(require_permission('internship.guidance.view'))):
    return success(activity_svc.my_checkin_rule(user, batch_id=batchId))


@router.post("/activity/checkins", summary="教师本人现场签到")
def teacher_checkin(
    body: TeacherCheckinBody,
    user=Depends(require_permission("internship.guidance.manage")),
):
    return success(
        activity_svc.checkin(user, body.model_dump(exclude_none=True)),
        message="教师签到已记录",
    )


@router.get("/activity/makeups", summary="教师本人补签申请")
def my_teacher_makeups(
    batchId: int = Query(..., ge=1),
    status: Literal["PENDING", "APPROVED", "REJECTED", "WITHDRAWN"] | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    user=Depends(require_permission("internship.guidance.view")),
):
    return success(activity_svc.list_my_teacher_makeups(
        user, batch_id=batchId, status=status, page=page, page_size=pageSize
    ))


@router.post("/activity/makeups", summary="教师本人申请补签")
def apply_teacher_makeup(
    body: TeacherMakeupBody,
    user=Depends(require_permission("internship.guidance.manage")),
):
    return success(
        activity_svc.apply_teacher_makeup(user, body.model_dump(exclude_none=True)),
        message="教师补签申请已提交",
    )


@router.post("/activity/makeups/{makeup_id}/withdraw", summary="教师本人撤回待审补签")
def withdraw_teacher_makeup(
    makeup_id: int,
    user=Depends(require_permission("internship.guidance.manage")),
):
    return success(
        activity_svc.withdraw_teacher_makeup(user, makeup_id),
        message="教师补签申请已撤回",
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


@router.post('/activity/period-reports/export', summary='导出教师本人周期报告')
def export_my_period_reports(batchId: int = Query(..., ge=1),
    reportType: Literal['WEEKLY', 'MONTHLY', 'SUMMARY'] | None = Query(None),
    user=Depends(require_permission('internship.guidance.view'))):
    return success(activity_svc.export_period_reports(user, batch_id=batchId, report_type=reportType))


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


@router.get("/emergency-notices/pending", summary="本人当前批次待强弹确认紧急通知")
def pending_teacher_emergency_notices(
    batchId: int = Query(..., ge=1),
    user=Depends(require_permission("internship.communication.view")),
):
    return success(activity_svc.pending_teacher_notices(user, batch_id=batchId))


@router.post("/emergency-notices/{notice_id}/ack", summary="本人明确确认紧急通知已知悉")
def acknowledge_teacher_emergency_notice(
    notice_id: int,
    batchId: int = Query(..., ge=1),
    user=Depends(require_permission("internship.communication.view")),
):
    return success(
        activity_svc.acknowledge_teacher_notice(
            user, notice_id, batch_id=batchId
        ),
        message="已记录知悉回执",
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
