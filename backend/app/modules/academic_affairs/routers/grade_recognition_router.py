"""D8-S4 成绩认定/课程替代 Router；D8-U 管理列表使用 SQL 分页读侧。

五条公开入口、DTO、权限、学生身份守卫、hardened recognition public service、
FileBinding/冻结证据与并发互斥语义保持不变；只读列表不再全租户 materialize。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path

from app.core.exceptions import AppException
from app.core.permissions import require_permission
from app.core.response import paginate, success
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
    user=Depends(require_permission("academicAffairs.gradeRecognition.manage")),
):
    if not body.studentNo:
        raise AppException("VALIDATION_ERROR", "教务代录必须提供学号")
    return success(recog_svc.submit(user, body, student_no=body.studentNo), message="已提交认定申请")


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
    user=Depends(require_permission("academicAffairs.gradeRecognition.manage")),
):
    return success(recog_svc.review(user, rid, body.action, body.reason or ""), message="已处理")


@router.post("/grade-recognitions/student/submit", summary="学生自助提交认定申请")
def recog_submit_student(body: RecognitionSubmitBody, user=Depends(_require_student)):
    return success(recog_svc.submit(user, body), message="已提交认定申请")


@router.get("/grade-recognitions/my", summary="我的认定申请")
def recog_my(user=Depends(_require_student)):
    return success({"items": recog_svc.my(user)})
