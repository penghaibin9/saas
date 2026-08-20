"""Teacher Miniapp V3 T6 internship evidence routes.

Mounted under the additive ``/teacher-mobile/internship`` surface. Student V3 shared router files
remain owner-locked until T8.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.core.permissions import require_module
from app.core.response import success
from app.core.security import require_staff
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


@router.get(
    "/visit-targets",
    summary="教师端巡访计划执行目标（含实习记录版本）",
    name="teacher_mobile_v3_visit_targets",
)
def visit_targets(user=Depends(require_staff)):
    return success(svc.list_visit_targets(user))


@router.post(
    "/weekly-reports/{report_id}/remind",
    summary="教师端逾期周报单学生站内催交",
    name="teacher_mobile_v3_weekly_report_remind",
)
def remind_weekly_report(report_id: int, user=Depends(require_staff)):
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
    user=Depends(require_staff),
):
    return success(
        svc.create_visit_evidence(user, internship_id, body.model_dump(exclude_none=True)),
        message="巡访执行证据已保存",
    )
