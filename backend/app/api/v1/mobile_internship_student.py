"""学生小程序与学生 PC 共用的岗位实习本人权威接口。"""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, Query

from app.core.exceptions import not_found
from app.core.permissions import require_module
from app.core.response import success
from app.core.security import get_current_user
from app.modules.internship.services import internship_safety_service as safety
from app.modules.internship.services import internship_student_compliance_service as compliance

router = APIRouter(
    prefix="/mobile/internship",
    tags=["学生移动端-岗位实习权威状态"],
    dependencies=[Depends(require_module("internship"))],
)


@router.get("/compliance/my", summary="本人岗位实习权威合规状态与下一步")
def my_compliance(
    operation: str = Query(default="ONBOARD"),
    batchId: str | None = Query(default=None),
    user=Depends(get_current_user),
):
    return success(compliance.evaluate_my(user, operation=operation, batch_id=batchId))


@router.get("/safety/courses/{course_id}/detail", summary="本人安全教育课程详情与完成版本")
def my_safety_course_detail(course_id: str, user=Depends(get_current_user)):
    courses = safety.list_my_courses(user)
    course = next((x for x in courses if str(x.get("id")) == str(course_id)), None)
    if not course:
        raise not_found("当前批次安全教育课程不存在")
    completions = safety.list_my_completions(user)
    completion = next(
        (x for x in completions if str(x.get("courseId")) == str(course_id)), None)
    snapshot = str(course.get("contentSnapshot") or "")
    return success({
        **course,
        "contentHash": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
        "completion": completion,
    })
