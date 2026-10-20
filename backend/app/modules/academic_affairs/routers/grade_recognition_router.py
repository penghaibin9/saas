"""D8-S4 成绩认定/课程替代 Router；D8-U 管理列表使用 SQL 分页读侧。

既有公开入口、DTO、权限、学生身份守卫、hardened recognition public service、
FileBinding/冻结证据与并发互斥语义保持不变；只读列表不再全租户 materialize。
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, Path, Query

from app.core.exceptions import AppException
from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.core.security import require_staff
from app.modules.academic_affairs.routers import academic_affairs as legacy
from app.modules.academic_affairs.services import academic_affairs_recognition_read_service as recog_read_svc


router = APIRouter(prefix="/academic-affairs", tags=["教务中心-成绩认定"])

recog_svc = legacy.recog_svc
RecognitionSubmitBody = legacy.RecognitionSubmitBody
RecognitionReviewBody = legacy.RecognitionReviewBody
_require_student = legacy._require_student


@router.post("/grade-recognitions", summary="教务代录成绩认定申请")
def recog_submit_staff(
    body: RecognitionSubmitBody,
    command_key: Optional[str] = Header(None, alias="Idempotency-Key", min_length=8, max_length=128),
    user=Depends(require_permission("academicAffairs.gradeRecognition.manage")),
):
    if not body.studentNo:
        raise AppException("VALIDATION_ERROR", "教务代录必须提供学号")
    return success(recog_svc.submit(user, body, student_no=body.studentNo, command_key=command_key), message="已提交认定申请")


@router.get("/grade-recognitions", summary="成绩认定列表")
def recog_list(
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission("academicAffairs.gradeRecognition.view")),
):
    items, total = recog_read_svc.list_all(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/grade-recognitions/{rid}/review", summary="教务审核（通过写 RECOGNIZED 成绩并刷新台账）")
def recog_review(
    body: RecognitionReviewBody,
    rid: int = Path(...),
    command_key: Optional[str] = Header(None, alias="Idempotency-Key", min_length=8, max_length=128),
    user=Depends(require_permission("academicAffairs.gradeRecognition.manage")),
):
    return success(recog_svc.review(user, rid, body.action, body.reason or "", command_key=command_key), message="已处理")


@router.get("/grade-command-receipts/{commandKey}", summary="读取当前教务身份发起的成绩命令回执")
def grade_command_receipt(
    commandKey: str = Path(..., min_length=8, max_length=128),
    operation: Literal["RECHECK_REVIEW", "RECOGNITION_SUBMIT", "RECOGNITION_REVIEW", "GRADE_CHANGE_APPLY", "GRADE_CHANGE_REVIEW"] = Query(...),
    user=Depends(require_staff),
):
    from app.modules.academic_affairs.services import academic_affairs_grade_command_receipt as receipt_service
    return success(receipt_service.read(user, operation, commandKey))


@router.get("/grade-recognitions/{rid}/detail", summary="成绩认定精确申请详情")
def recog_detail(
    rid: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.gradeRecognition.view")),
):
    return success(recog_read_svc.get_detail(user, rid))


@router.get("/grade-recognitions/student/course-options", summary="学生认定目标课程版本候选")
def recog_student_course_options(
    keyword: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(_require_student),
):
    items, total = recog_read_svc.student_target_courses(user, keyword, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/grade-recognitions/student/submit", summary="学生自助提交认定申请")
def recog_submit_student(body: RecognitionSubmitBody, user=Depends(_require_student)):
    return success(recog_svc.submit(user, body), message="已提交认定申请")


@router.get("/grade-recognitions/my", summary="我的认定申请")
def recog_my(user=Depends(_require_student)):
    return success({"items": recog_svc.my(user)})
