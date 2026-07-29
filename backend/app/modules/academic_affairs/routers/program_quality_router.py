"""V2-01 培养方案质量与开课差异接口。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_program_governance_service as quality_svc

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-培养方案质量"])
_VIEW = require_permission("academicAffairs.program.view")


@router.get("/programs/{program_id}/validation", summary="培养方案结构化校验")
def program_validation(program_id: int = Path(..., gt=0), user=Depends(_VIEW)):
    return success(quality_svc.validate_program(user, program_id))


@router.get("/program-governance/summary", summary="培养方案治理摘要")
def program_governance_summary(user=Depends(_VIEW)):
    return success(quality_svc.program_governance_summary(user))


@router.get("/opening-plan/differences", summary="方案应开与教学任务实开差异")
def opening_plan_differences(
    termId: int,
    majorId: Optional[int] = None,
    gradeYear: Optional[str] = None,
    status: Optional[str] = None,
    user=Depends(_VIEW),
):
    return success(quality_svc.opening_differences(user, termId, majorId, gradeYear, status))
