"""D5-S1 课表主链 Move Only Router。

只迁出 legacy 大 Router 已有的课表批次与课表只读入口；DTO、权限码、service 与响应形状
全部复用原合同。/schedule/export 已由 ExportJob compat Router 正式接管，本 Router 不抢 owner。
自动排课、排课增强、资源字典、调停课在后续 D5-S 子刀处理。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.routers import academic_affairs as legacy

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-课表"])

# Move Only：请求 DTO / canonical service 直接复用 legacy 对象。
ScheduleBatchCreate = legacy.ScheduleBatchCreate
ScheduleItemBody = legacy.ScheduleItemBody
ScheduleImportBody = legacy.ScheduleImportBody
ScheduleMoveBody = legacy.ScheduleMoveBody
VoidBody = legacy.VoidBody
sched_svc = legacy.sched_svc

_SCHED_TIER1_VIEW = legacy._SCHED_TIER1_VIEW
_SCHED_ROOM_VIEW = legacy._SCHED_ROOM_VIEW


@router.post("/schedule-batches", summary="新建课表批次")
def schedule_batch_create(
    body: ScheduleBatchCreate,
    user=Depends(require_permission("academicAffairs.schedule.edit")),
):
    return success(sched_svc.create_batch(body, user), message="已创建")


@router.get("/schedule-batches", summary="课表批次列表")
def schedule_batches(
    termId: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission("academicAffairs.schedule.view")),
):
    items, total = sched_svc.list_batches(user, termId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/schedule-batches/{batchId}/items", summary="手工排课（三重冲突检测→409）")
def schedule_add_item(
    body: ScheduleItemBody,
    batchId: int = Path(...),
    user=Depends(require_permission("academicAffairs.schedule.edit")),
):
    return success(sched_svc.add_item(batchId, user, body), message="已排课")


@router.post("/schedule-batches/{batchId}/import", summary="导入课表（同一冲突检测器，返回冲突清单）")
def schedule_import(
    body: ScheduleImportBody,
    batchId: int = Path(...),
    user=Depends(require_permission("academicAffairs.schedule.import")),
):
    return success(sched_svc.import_items(batchId, user, body.items, atomic=body.atomic), message="导入完成")


@router.put("/schedule-items/{itemId}/move", summary="拖拽调格（同一冲突检测器，冲突409原位不动）")
def schedule_move_item(
    body: ScheduleMoveBody,
    itemId: int = Path(...),
    user=Depends(require_permission("academicAffairs.schedule.edit")),
):
    return success(sched_svc.move_item(itemId, user, body), message="已调整")


@router.post("/schedule-batches/{batchId}/pre-publish", summary="课表预发布")
def schedule_pre_publish(
    batchId: int = Path(...),
    user=Depends(require_permission("academicAffairs.schedule.edit")),
):
    return success(sched_svc.pre_publish(batchId, user), message="已预发布")


@router.post("/schedule-batches/{batchId}/publish", summary="课表发布（通知师生）")
def schedule_publish(
    batchId: int = Path(...),
    user=Depends(require_permission("academicAffairs.schedule.edit")),
):
    return success(sched_svc.publish(batchId, user), message="已发布")


@router.post("/schedule-batches/{batchId}/void-reissue", summary="作废重发（调停课运维通道，留审计）")
def schedule_void(
    body: VoidBody,
    batchId: int = Path(...),
    user=Depends(require_permission("academicAffairs.schedule.archive")),
):
    return success(sched_svc.void_and_reissue(batchId, user, body.reason), message="已作废")


@router.get("/schedule-batches/{batchId}/class-view", summary="班级课表视图")
def schedule_class_view(
    batchId: int = Path(...),
    classId: str = "",
    user=Depends(require_permission("academicAffairs.schedule.view")),
):
    return success(sched_svc.class_view(batchId, user, classId))


@router.get("/schedule-batches/{batchId}/teacher-view", summary="教师课表视图")
def schedule_teacher_view(
    batchId: int = Path(...),
    teacherKey: str = "",
    user=Depends(require_permission("academicAffairs.schedule.view")),
):
    return success(sched_svc.teacher_view(batchId, user, teacherKey))


@router.get("/schedule-batches/{batchId}/student-view", summary="学生课表视图（按行政班服务端推导）")
def schedule_student_view(
    batchId: int = Path(...),
    studentId: str = "",
    user=Depends(require_permission("academicAffairs.schedule.view")),
):
    return success(sched_svc.student_view(batchId, user, studentId))


@router.get("/schedule/class/{classId}", summary="班级课表（自动取当前已发布批次；周次可选过滤；越范围403002）")
def schedule_class_page(
    classId: int = Path(...),
    termId: Optional[str] = None,
    week: Optional[int] = None,
    user=Depends(require_permission(_SCHED_TIER1_VIEW)),
):
    return success(sched_svc.class_schedule(user, classId, termId, week))


@router.get("/schedule/teacher/{teacherKey}", summary="教师课表（教务处/学院教务查任意；教师仅本人，越权403002）")
def schedule_teacher_page(
    teacherKey: str = Path(...),
    termId: Optional[str] = None,
    week: Optional[int] = None,
    user=Depends(require_permission(_SCHED_TIER1_VIEW)),
):
    return success(sched_svc.teacher_schedule(user, teacherKey, termId, week))


@router.get("/schedule/room/{classroomId}", summary="教室课表（教务/学院教务只读；自动取当前已发布批次）")
def schedule_room_page(
    classroomId: int = Path(...),
    termId: Optional[str] = None,
    week: Optional[int] = None,
    user=Depends(require_permission(_SCHED_ROOM_VIEW)),
):
    return success(sched_svc.room_schedule(user, classroomId, termId, week))


@router.get("/schedule/student/{studentId}", summary="学生课表（按行政班+本人LOCKED选课并入；自动取当前已发布批次；越范围403002）")
def schedule_student_page(
    studentId: int = Path(...),
    termId: Optional[str] = None,
    week: Optional[int] = None,
    user=Depends(require_permission(_SCHED_TIER1_VIEW)),
):
    return success(sched_svc.student_schedule(user, studentId, termId, week))


@router.get("/schedule/teaching-class/{teachingClassCode}", summary="教学班课表（派生自教学任务；自动取当前已发布批次；越范围403002）")
def schedule_teaching_class_page(
    teachingClassCode: str = Path(...),
    termId: Optional[str] = None,
    week: Optional[int] = None,
    user=Depends(require_permission(_SCHED_TIER1_VIEW)),
):
    return success(sched_svc.teaching_class_schedule(user, teachingClassCode, termId, week))


@router.get("/schedule/publish-records", summary="课表发布记录（t_aa_schedule_publish，发布/作废历史留痕）")
def schedule_publish_records(
    termId: Optional[str] = None,
    batchId: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission(_SCHED_TIER1_VIEW)),
):
    items, total = sched_svc.list_publish_records(user, termId, batchId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/schedule/adjustments", summary="课表调整记录（读 t_affairs_audit_trail：条目/批次两级变更留痕，只读）")
def schedule_adjustments(
    bizType: Optional[str] = None,
    action: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission(_SCHED_TIER1_VIEW)),
):
    items, total = sched_svc.list_schedule_adjustments(user, bizType, action, page, pageSize)
    return success(paginate(items, total, page, pageSize))
