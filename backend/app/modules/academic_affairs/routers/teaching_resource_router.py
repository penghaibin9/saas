"""D5-S3 教室 / 实训室 / 设备资源 Move Only Router。

只迁出 legacy 大 Router 已有的教学资源字典、预约、占用、冲突、维修与统计入口。
DTO、权限码、resource_svc 与响应形状全部复用原合同；不改资源状态机或预约冲突规则。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.routers import academic_affairs as legacy

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-教学资源"])

# Move Only：请求 DTO / canonical service 直接复用 legacy 对象。
ClassroomCreate = legacy.ClassroomCreate
ClassroomUpdate = legacy.ClassroomUpdate
ClassroomStatusBody = legacy.ClassroomStatusBody
ClassroomBookBody = legacy.ClassroomBookBody
BookingReviewBody = legacy.BookingReviewBody
LabCreate = legacy.LabCreate
LabUpdate = legacy.LabUpdate
LabStatusBody = legacy.LabStatusBody
LabBookBody = legacy.LabBookBody
EquipmentCreate = legacy.EquipmentCreate
EquipmentUpdate = legacy.EquipmentUpdate
EquipmentStatusBody = legacy.EquipmentStatusBody
RepairReportBody = legacy.RepairReportBody
RepairCompleteBody = legacy.RepairCompleteBody
RepairCancelBody = legacy.RepairCancelBody
resource_svc = legacy.resource_svc


# ── 教室字典 ──
@router.get("/classrooms", summary="教室字典列表（按楼栋/类型/状态/关键词过滤）")
def classroom_list(
    keyword: Optional[str] = None,
    buildingCode: Optional[str] = None,
    roomType: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission("academicAffairs.classroom.view")),
):
    items, total = resource_svc.list_classrooms(user, keyword, buildingCode, roomType, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/classrooms/options", summary="可用教室选项（排课选择器供数，含 capacity 供非阻断 warning）")
def classroom_options(
    keyword: Optional[str] = None,
    user=Depends(require_permission("academicAffairs.classroom.view")),
):
    return success({"items": resource_svc.list_options(user, keyword)})


@router.post("/classrooms", summary="新建教室（同楼栋+编号唯一，重复409）")
def classroom_create(
    body: ClassroomCreate,
    user=Depends(require_permission("academicAffairs.classroom.create")),
):
    return success(resource_svc.create_classroom(body, user), message="已创建")


@router.put("/classrooms/{classroomId}", summary="编辑教室")
def classroom_update(
    body: ClassroomUpdate,
    classroomId: int = Path(...),
    user=Depends(require_permission("academicAffairs.classroom.update")),
):
    return success(resource_svc.update_classroom(classroomId, body, user), message="已保存")


@router.post("/classrooms/{classroomId}/status", summary="切换可用状态（AVAILABLE/DISABLED/MAINTENANCE，幂等）")
def classroom_status(
    body: ClassroomStatusBody,
    classroomId: int = Path(...),
    user=Depends(require_permission("academicAffairs.classroom.update")),
):
    return success(resource_svc.set_status(classroomId, body.status, user, body.reason or ""), message="已更新")


@router.delete("/classrooms/{classroomId}", summary="删除教室（逻辑删除）")
def classroom_delete(
    classroomId: int = Path(...),
    user=Depends(require_permission("academicAffairs.classroom.delete")),
):
    return success(resource_svc.delete_classroom(classroomId, user), message="已删除")


# 字面量 bookings 必须先于 GET /classrooms/{classroomId}，保持 legacy 已修复的匹配顺序。
@router.post("/classrooms/bookings", summary="申请教室预约（同教室同时段占用409）")
def classroom_book(
    body: ClassroomBookBody,
    user=Depends(require_permission("academicAffairs.classroom.view")),
):
    return success(resource_svc.book_classroom(user, body), message="已提交预约")


@router.get("/classrooms/bookings", summary="教室预约列表")
def classroom_bookings(
    classroomId: Optional[str] = None,
    date: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission("academicAffairs.classroom.view")),
):
    items, total = resource_svc.list_bookings(user, classroomId, date, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/classrooms/{classroomId}", summary="教室详情")
def classroom_detail(
    classroomId: int = Path(...),
    user=Depends(require_permission("academicAffairs.classroom.view")),
):
    return success(resource_svc.get_classroom(classroomId, user))


@router.post("/classrooms/bookings/{bookingId}/review", summary="审核教室预约")
def classroom_booking_review(
    body: BookingReviewBody,
    bookingId: int = Path(...),
    user=Depends(require_permission("academicAffairs.classroom.update")),
):
    return success(resource_svc.review_booking(user, bookingId, body.action, body.reason), message="已处理")


# ── 实训室 ──
@router.get("/labs", summary="实训室字典列表（按类型/状态/关键词过滤）")
def lab_list(
    keyword: Optional[str] = None,
    labType: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission("academicAffairs.lab.view")),
):
    items, total = resource_svc.list_labs(user, keyword, labType, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/labs/options", summary="可用实训室选项（预约选择器供数）")
def lab_options(
    keyword: Optional[str] = None,
    user=Depends(require_permission("academicAffairs.lab.view")),
):
    return success({"items": resource_svc.list_lab_options(user, keyword)})


@router.post("/labs", summary="新建实训室（编号唯一，重复409）")
def lab_create(
    body: LabCreate,
    user=Depends(require_permission("academicAffairs.lab.create")),
):
    return success(resource_svc.create_lab(body, user), message="已创建")


@router.put("/labs/{labId}", summary="编辑实训室")
def lab_update(
    body: LabUpdate,
    labId: int = Path(...),
    user=Depends(require_permission("academicAffairs.lab.update")),
):
    return success(resource_svc.update_lab(labId, body, user), message="已保存")


@router.post("/labs/{labId}/status", summary="切换可用状态（AVAILABLE/DISABLED/MAINTENANCE，幂等）")
def lab_status(
    body: LabStatusBody,
    labId: int = Path(...),
    user=Depends(require_permission("academicAffairs.lab.update")),
):
    return success(resource_svc.set_lab_status(labId, body.status, user, body.reason or ""), message="已更新")


@router.delete("/labs/{labId}", summary="删除实训室（逻辑删除）")
def lab_delete(
    labId: int = Path(...),
    user=Depends(require_permission("academicAffairs.lab.delete")),
):
    return success(resource_svc.delete_lab(labId, user), message="已删除")


# 字面量 bookings 必须先于 GET /labs/{labId}。
@router.post("/labs/bookings", summary="申请实训室预约（同实训室同时段占用409）")
def lab_book(
    body: LabBookBody,
    user=Depends(require_permission("academicAffairs.lab.view")),
):
    return success(resource_svc.book_lab(user, body), message="已提交预约")


@router.get("/labs/bookings", summary="实训室预约列表")
def lab_bookings(
    labId: Optional[str] = None,
    date: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission("academicAffairs.lab.view")),
):
    items, total = resource_svc.list_lab_bookings(user, labId, date, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/labs/bookings/{bookingId}/review", summary="审核实训室预约")
def lab_booking_review(
    body: BookingReviewBody,
    bookingId: int = Path(...),
    user=Depends(require_permission("academicAffairs.lab.update")),
):
    return success(resource_svc.review_lab_booking(user, bookingId, body.action, body.reason), message="已处理")


@router.get("/labs/{labId}", summary="实训室详情")
def lab_detail(
    labId: int = Path(...),
    user=Depends(require_permission("academicAffairs.lab.view")),
):
    return success(resource_svc.get_lab(labId, user))


# ── 设备资源 ──
@router.get("/equipment", summary="设备资源列表（按位置/状态/关键词过滤）")
def equipment_list(
    keyword: Optional[str] = None,
    ownerKind: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission("academicAffairs.equipment.view")),
):
    items, total = resource_svc.list_equipment(user, keyword, ownerKind, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/equipment", summary="新建设备（资产编号唯一，重复409）")
def equipment_create(
    body: EquipmentCreate,
    user=Depends(require_permission("academicAffairs.equipment.create")),
):
    return success(resource_svc.create_equipment(body, user), message="已创建")


@router.put("/equipment/{equipmentId}", summary="编辑设备")
def equipment_update(
    body: EquipmentUpdate,
    equipmentId: int = Path(...),
    user=Depends(require_permission("academicAffairs.equipment.update")),
):
    return success(resource_svc.update_equipment(equipmentId, body, user), message="已保存")


@router.post("/equipment/{equipmentId}/status", summary="切换设备状态（IN_USE/IDLE/MAINTENANCE/SCRAPPED，幂等）")
def equipment_status(
    body: EquipmentStatusBody,
    equipmentId: int = Path(...),
    user=Depends(require_permission("academicAffairs.equipment.update")),
):
    return success(
        resource_svc.set_equipment_status(equipmentId, body.status, user, body.reason or ""),
        message="已更新",
    )


@router.delete("/equipment/{equipmentId}", summary="删除设备（逻辑删除）")
def equipment_delete(
    equipmentId: int = Path(...),
    user=Depends(require_permission("academicAffairs.equipment.delete")),
):
    return success(resource_svc.delete_equipment(equipmentId, user), message="已删除")


@router.get("/equipment/{equipmentId}", summary="设备详情")
def equipment_detail(
    equipmentId: int = Path(...),
    user=Depends(require_permission("academicAffairs.equipment.view")),
):
    return success(resource_svc.get_equipment(equipmentId, user))


# ── 跨资源只读视图 / 维修 ──
@router.get("/resources/occupancy", summary="资源占用（教室+实训室已批准预约+当日课表，统一只读视图）")
def resource_occupancy(
    date: str,
    resourceKind: Optional[str] = None,
    user=Depends(require_permission("academicAffairs.resourceOccupancy.view")),
):
    return success(resource_svc.get_resource_occupancy(user, date, resourceKind))


@router.get("/resources/conflicts", summary="资源冲突台账（预约 vs 已发布课表跨源冲突，日期范围最多31天）")
def resource_conflicts(
    dateFrom: str,
    dateTo: Optional[str] = None,
    user=Depends(require_permission("academicAffairs.resourceConflict.view")),
):
    return success(resource_svc.list_resource_conflicts(user, dateFrom, dateTo))


@router.post("/resources/repairs", summary="登记故障报修（联动资源状态置为维修中）")
def repair_report(
    body: RepairReportBody,
    user=Depends(require_permission("academicAffairs.resourceRepair.manage")),
):
    return success(resource_svc.report_repair(user, body), message="已登记报修")


@router.get("/resources/repairs", summary="维修工单列表")
def repair_list(
    resourceKind: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission("academicAffairs.resourceRepair.view")),
):
    items, total = resource_svc.list_repairs(user, resourceKind, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/resources/repairs/{repairId}/start", summary="开始维修")
def repair_start(
    repairId: int = Path(...),
    user=Depends(require_permission("academicAffairs.resourceRepair.manage")),
):
    return success(resource_svc.start_repair(user, repairId), message="已开始维修")


@router.post("/resources/repairs/{repairId}/complete", summary="完成维修（联动恢复资源可用，若无其它未完成工单）")
def repair_complete(
    body: RepairCompleteBody,
    repairId: int = Path(...),
    user=Depends(require_permission("academicAffairs.resourceRepair.manage")),
):
    return success(resource_svc.complete_repair(user, repairId, body.repairNote or ""), message="已完成")


@router.post("/resources/repairs/{repairId}/cancel", summary="取消维修工单")
def repair_cancel(
    body: RepairCancelBody,
    repairId: int = Path(...),
    user=Depends(require_permission("academicAffairs.resourceRepair.manage")),
):
    return success(resource_svc.cancel_repair(user, repairId, body.reason or ""), message="已取消")


@router.get("/resources/stats", summary="资源统计（数量/状态分布/预约审批率/维修工单，只读聚合）")
def resource_stats(
    user=Depends(require_permission("academicAffairs.resourceStats.view")),
):
    return success(resource_svc.get_resource_stats(user))
