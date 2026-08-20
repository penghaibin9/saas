"""Teacher Miniapp V3 T3/T4 additive student read API.

Mounted under the existing ``/teacher-mobile`` surface by ``todos.make_router`` so these
teacher-only slices can ship without editing #182-owned ``mobile.py`` / ``realApi.js``.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import success
from app.core.security import require_staff
from app.services import teacher_mobile_student_keyset_service as student_svc
from app.services import teacher_mobile_student360_projection_service as student360_svc

router = APIRouter()


@router.get("/students", summary="教师端我的学生连续列表（keyset）",
            name="teacher_mobile_students_continuous")
def list_students(
    classId: Optional[int] = Query(default=None, ge=1),
    keyword: Optional[str] = Query(default=None, max_length=100),
    cursor: Optional[str] = Query(default=None, max_length=2048),
    pageSize: int = Query(default=20, ge=1, le=100),
    user=Depends(require_staff),
):
    return success(student_svc.list_continuous(
        user,
        class_id=classId,
        keyword=keyword,
        cursor=cursor,
        page_size=pageSize,
    ))


@router.get("/students/{student_id}/projection", summary="教师端 Student360 单学生投影",
            name="teacher_mobile_student360_projection")
def student360_projection(student_id: str, user=Depends(require_staff)):
    return success(student360_svc.get_projection(user, student_id))
