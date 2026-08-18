"""V2-02 独立教学班、名单版本与正式教师关系接口。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.services import academic_affairs_attendance_swap_teacher_week_guard as attendance_swap_week_guard
from app.modules.academic_affairs.services import academic_affairs_grade_todo_teacher_relation_guard as grade_todo_relation_guard
from app.modules.academic_affairs.services import academic_affairs_teaching_class_query_service as query_service
from app.modules.academic_affairs.services import academic_affairs_teaching_class_admin_service as admin_service
from app.modules.academic_affairs.services import academic_affairs_teaching_class_change_service as change_service
from app.modules.academic_affairs.services import academic_affairs_teaching_class_teacher_service as teacher_service

# Teacher-relation management may be imported independently from mobile grade routes.
# Install explicit-topology protection and SWAP logical-week reauthorization here too,
# so runtime correctness never depends on router import order.
grade_todo_relation_guard.install()
attendance_swap_week_guard.install()

router = APIRouter(prefix="/academic-affairs/teaching-classes", tags=["教务中心-教学班"])

_VIEW = require_permission("academicAffairs.teachingTask.view")
_MANAGE = require_permission("academicAffairs.teachingTask.manage")


class TeachingClassBackfillBody(BaseModel):
    termId: int = Field(..., gt=0)
    dryRun: bool = True
    reason: Optional[str] = Field(default=None, max_length=500)


class TeachingClassRosterPreviewBody(BaseModel):
    studentIds: list[int] = Field(default_factory=list)


class TeachingClassRosterChangeBody(TeachingClassRosterPreviewBody):
    reason: str = Field(..., min_length=5, max_length=500)


class TeachingClassTeacherCreateBody(BaseModel):
    teacherKey: str = Field(..., min_length=1, max_length=100)
    roleType: str = Field(default="CO_TEACHER", pattern="^(PRIMARY|CO_TEACHER)$")
    startWeek: Optional[int] = Field(default=None, ge=1, le=60)
    endWeek: Optional[int] = Field(default=None, ge=1, le=60)
    reason: str = Field(..., min_length=5, max_length=500)


class TeachingClassTeacherUpdateBody(BaseModel):
    teacherKey: Optional[str] = Field(default=None, min_length=1, max_length=100)
    startWeek: Optional[int] = Field(default=None, ge=1, le=60)
    endWeek: Optional[int] = Field(default=None, ge=1, le=60)
    reason: str = Field(..., min_length=5, max_length=500)


class TeachingClassTeacherDeactivateBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


@router.get("", summary="教学班列表")
def teaching_class_list(
    termId: Optional[int] = None,
    status: Optional[str] = None,
    classType: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    pageSize: int = 30,
    user=Depends(_VIEW),
):
    items, total = query_service.list_teaching_classes(
        user, termId, status, classType, keyword, page, min(max(pageSize, 1), 200),
    )
    data = paginate(items, total, page, pageSize)
    data["list"] = items
    return success(data)


@router.post("/actions/backfill", summary="教学班存量投影与对账")
def teaching_class_backfill(body: TeachingClassBackfillBody, user=Depends(_MANAGE)):
    result = admin_service.backfill_teaching_classes(
        user, body.termId, body.dryRun, body.reason or "",
    )
    return success(result, message="对账完成" if body.dryRun else "教学班与名单版本回填完成")


@router.post("/{teaching_class_id}/roster/impact", summary="名单变更影响预览")
def teaching_class_roster_impact(
    body: TeachingClassRosterPreviewBody,
    teaching_class_id: int = Path(..., gt=0),
    user=Depends(_MANAGE),
):
    return success(change_service.preview_roster_change(user, teaching_class_id, body.studentIds))


@router.post("/{teaching_class_id}/roster/versions", summary="创建非选课教学班名单版本")
def teaching_class_roster_version_create(
    body: TeachingClassRosterChangeBody,
    teaching_class_id: int = Path(..., gt=0),
    user=Depends(_MANAGE),
):
    result = change_service.create_manual_roster_version(
        user, teaching_class_id, body.studentIds, body.reason,
    )
    return success(result, message="新名单版本已生效")


@router.get("/{teaching_class_id}/teachers", summary="正式任课教师关系（PRIMARY/共同授课/有效周次）")
def teaching_class_teacher_list(
    teaching_class_id: int = Path(..., gt=0),
    user=Depends(_VIEW),
):
    return success({"items": teacher_service.list_relations(user, teaching_class_id)})


@router.post("/{teaching_class_id}/teachers", summary="新增正式任课教师关系")
def teaching_class_teacher_create(
    body: TeachingClassTeacherCreateBody,
    teaching_class_id: int = Path(..., gt=0),
    user=Depends(_MANAGE),
):
    result = teacher_service.create_relation(
        user,
        teaching_class_id,
        teacher_key=body.teacherKey,
        role_type=body.roleType,
        start_week=body.startWeek,
        end_week=body.endWeek,
        reason=body.reason,
    )
    return success(result, message="正式教师关系已生效")


@router.put("/{teaching_class_id}/teachers/{relation_id}", summary="调整教师身份或有效周次")
def teaching_class_teacher_update(
    body: TeachingClassTeacherUpdateBody,
    teaching_class_id: int = Path(..., gt=0),
    relation_id: int = Path(..., gt=0),
    user=Depends(_MANAGE),
):
    result = teacher_service.update_relation(
        user,
        teaching_class_id,
        relation_id,
        teacher_key=body.teacherKey,
        start_week=body.startWeek,
        end_week=body.endWeek,
        reason=body.reason,
    )
    return success(result, message="正式教师关系已更新")


@router.post("/{teaching_class_id}/teachers/{relation_id}/deactivate", summary="停用共同授课教师关系")
def teaching_class_teacher_deactivate(
    body: TeachingClassTeacherDeactivateBody,
    teaching_class_id: int = Path(..., gt=0),
    relation_id: int = Path(..., gt=0),
    user=Depends(_MANAGE),
):
    result = teacher_service.deactivate_relation(
        user,
        teaching_class_id,
        relation_id,
        reason=body.reason,
    )
    return success(result, message="正式教师关系已停用")


@router.get("/{teaching_class_id}", summary="教学班详情与名单版本")
def teaching_class_detail(teaching_class_id: int = Path(..., gt=0), user=Depends(_VIEW)):
    return success(query_service.get_teaching_class(user, teaching_class_id))
