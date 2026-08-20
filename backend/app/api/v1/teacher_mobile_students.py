"""Teacher Miniapp V3 additive teacher-mobile slices.

Mounted under the existing ``/teacher-mobile`` surface by ``todos.make_router`` so teacher-only
V3 slices can ship without editing Student V3 ``mobile.py`` / ``realApi.js``. T3/T4 own the
student read surface; T5/T6 own internship single-object commands/evidence; T7 adds employment
recommendation and verification; T8 consumes the shared action/pager handoff.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.v1.teacher_mobile_employment import router as employment_router
from app.api.v1.teacher_mobile_internship import router as internship_router
from app.api.v1.teacher_mobile_sequential import router as sequential_router
from app.core.response import success
from app.core.security import require_staff
from app.services import teacher_mobile_student_keyset_service as student_svc
from app.services import teacher_mobile_student360_projection_service as student360_svc
from app.services import teacher_mobile_todo_grouped_service as todo_grouped_svc

router = APIRouter()
router.include_router(sequential_router)
router.include_router(internship_router)
router.include_router(employment_router)


@router.get("/todos/grouped-continuous", summary="教师端分组待办连续列表（shared keyset）",
            name="teacher_mobile_todos_grouped_continuous")
def grouped_todos(
    group: str = Query(default="all", max_length=32),
    cursor: Optional[str] = Query(default=None, max_length=2048),
    pageSize: int = Query(default=20, ge=1, le=100),
    user=Depends(require_staff),
):
    return success(todo_grouped_svc.list_grouped_continuous(
        user,
        group=group,
        cursor=cursor,
        page_size=pageSize,
    ))


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
