"""学生宿舍调宿的目标床选择接口。

首次自选受学校 selfSelectEnabled 开关控制；已有床学生的正式调宿申请是另一条业务链，
不应因关闭首次自选而失去申请入口，也不得直接释放原床。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.core.response import success
from app.core.security import get_current_user
from app.services.db_service import _tid, session

router = APIRouter(tags=["学工中心·学生调宿"])


def _student(db, user):
    from app.services.mobile_student_service import _require_student, resolve_student
    _require_student(user)
    row = resolve_student(db, user)
    if not row:
        raise no_permission("尚未建立你的学生档案")
    return row


def _require_existing_bed(db, student_id):
    from app.models import DormBed
    rows = db.scalars(select(DormBed).where(
        DormBed.tenant_id == _tid(),
        DormBed.student_id == int(student_id),
        DormBed.status == "OCCUPIED",
        DormBed.is_deleted.is_(False),
    )).all()
    if not rows:
        raise AppException("DATA_CONFLICT", "你当前没有床位，请使用首次入住流程")
    if len(rows) != 1:
        raise AppException("DATA_CONFLICT", "你的有效床位数据异常，请联系宿管核对")
    return rows[0]


def _eligible_building(db, building_id: int, student):
    from app.models import DormBuilding
    from app.services.affairs_dorm_reliability_service import _strict_gender_ok
    building = db.get(DormBuilding, int(building_id))
    if (
        not building or building.is_deleted or building.tenant_id != _tid()
        or building.status != "ENABLED"
    ):
        raise not_found("目标楼栋不存在或未启用")
    if not _strict_gender_ok(building.gender_limit, student.gender):
        raise AppException("NO_DATA_SCOPE", "该楼栋不适用于你的性别信息")
    return building


@router.get("/mobile/affairs/dorm/transfer-options", summary="本人调宿可选楼栋")
def transfer_options(user=Depends(get_current_user)):
    from app.services import affairs_dorm_service as dorm
    with session() as db:
        student = _student(db, user)
        current = _require_existing_bed(db, student.id)
        gender = student.gender
        current_id = int(current.id)
    buildings, total = dorm.list_buildings(user, gender=gender, page=1, page_size=200)
    return success({
        "items": buildings,
        "total": total,
        "currentBedId": str(current_id),
        "notice": "选择目标床位后提交调宿申请，原床将在辅导员和宿管审批完成后才释放。",
    })


@router.get("/mobile/affairs/dorm/transfer-buildings/{building_id}/rooms", summary="本人调宿可选房间")
def transfer_rooms(
    building_id: int = Path(...),
    floor: int | None = Query(None),
    user=Depends(get_current_user),
):
    from app.services import affairs_dorm_service as dorm
    with session() as db:
        student = _student(db, user)
        _require_existing_bed(db, student.id)
        _eligible_building(db, building_id, student)
    items, total = dorm.list_rooms(building_id, user, floor=floor, page=1, page_size=200)
    return success({"items": items, "total": total})


@router.get("/mobile/affairs/dorm/transfer-rooms/{room_id}/beds", summary="本人调宿可选床位")
def transfer_beds(room_id: int = Path(...), user=Depends(get_current_user)):
    from app.models import DormRoom
    from app.services import affairs_dorm_service as dorm
    with session() as db:
        student = _student(db, user)
        current = _require_existing_bed(db, student.id)
        room = db.get(DormRoom, int(room_id))
        if not room or room.is_deleted or room.tenant_id != _tid() or room.status != "ENABLED":
            raise not_found("目标房间不存在或未启用")
        _eligible_building(db, int(room.building_id), student)
        current_id = int(current.id)
    items = dorm.list_beds(room_id, user)
    safe = []
    for item in items:
        safe.append({
            "bedId": item.get("bedId"),
            "roomId": item.get("roomId"),
            "bedNo": item.get("bedNo"),
            "status": item.get("status"),
            "isCurrent": str(item.get("bedId")) == str(current_id),
        })
    return success({"items": safe})
