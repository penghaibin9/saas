"""宿舍列表投影：床位并发版本、可读床位证据与节点动作。"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import not_found
from app.services.db_service import _iso, _tid, session


def _user_id(user) -> int:
    raw = str((user or {}).get("userId") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    return int(raw) if raw.isdigit() else 0


def _label(bed, room, building) -> str:
    if not bed:
        return "原床位未记录"
    parts = [
        (building.building_name if building else ""),
        (f"{room.room_no}室" if room and room.room_no else ""),
        (f"{bed.bed_no}床" if bed.bed_no else f"床位#{bed.id}"),
    ]
    return " / ".join(x for x in parts if x) or f"床位#{bed.id}"


def project_transfer_items(items, user):
    """给任意已完成数据范围过滤的调宿行补齐床位证据与当前账号真实可执行动作。"""
    if not items:
        return items

    from app.core.affairs_security import build_affairs_context
    from app.models import DormBed, DormBuilding, DormRoom, UnifiedTodo
    from app.services import affairs_dorm_service as dorm

    bed_ids = {
        int(value)
        for item in items
        for value in (item.get("fromBedId"), item.get("toBedId"))
        if str(value or "").isdigit()
    }
    transfer_ids = {
        int(item.get("transferId"))
        for item in items
        if str(item.get("transferId") or "").isdigit()
    }
    with session() as db:
        beds = {
            int(row.id): row
            for row in db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(), DormBed.id.in_(bed_ids or {-1}),
                DormBed.is_deleted.is_(False),
            )).all()
        }
        room_ids = {int(row.room_id) for row in beds.values() if row.room_id}
        rooms = {
            int(row.id): row
            for row in db.scalars(select(DormRoom).where(
                DormRoom.tenant_id == _tid(), DormRoom.id.in_(room_ids or {-1}),
                DormRoom.is_deleted.is_(False),
            )).all()
        }
        building_ids = {int(row.building_id) for row in beds.values() if row.building_id}
        buildings = {
            int(row.id): row
            for row in db.scalars(select(DormBuilding).where(
                DormBuilding.tenant_id == _tid(), DormBuilding.id.in_(building_ids or {-1}),
                DormBuilding.is_deleted.is_(False),
            )).all()
        }
        context = build_affairs_context(user, db)
        uid = _user_id(user)
        pending_assignees = {
            int(row.source_biz_id): int(row.assignee_id or 0)
            for row in db.scalars(select(UnifiedTodo).where(
                UnifiedTodo.tenant_id == _tid(),
                UnifiedTodo.source_module == "student-affairs",
                UnifiedTodo.source_biz_type == "DORM_TRANSFER",
                UnifiedTodo.source_biz_id.in_(transfer_ids or {-1}),
                UnifiedTodo.todo_type == dorm.TODO_TRANSFER,
                UnifiedTodo.status == "PENDING",
                UnifiedTodo.is_deleted.is_(False),
            )).all()
        }

    for item in items:
        from_bed = beds.get(int(item["fromBedId"])) if str(item.get("fromBedId") or "").isdigit() else None
        to_bed = beds.get(int(item["toBedId"])) if str(item.get("toBedId") or "").isdigit() else None
        from_room = rooms.get(int(from_bed.room_id)) if from_bed and from_bed.room_id else None
        to_room = rooms.get(int(to_bed.room_id)) if to_bed and to_bed.room_id else None
        from_building = buildings.get(int(from_bed.building_id)) if from_bed and from_bed.building_id else None
        to_building = buildings.get(int(to_bed.building_id)) if to_bed and to_bed.building_id else None
        transfer_id = int(item["transferId"]) if str(item.get("transferId") or "").isdigit() else 0
        node = str(item.get("currentNode") or item.get("status") or "")
        assigned_to_current = uid > 0 and pending_assignees.get(transfer_id) == uid
        can_review = False
        if node in dorm.TRANSFER_NODES:
            if context.scope_type == "TENANT_ALL":
                can_review = True
            elif node == "COUNSELOR_REVIEW" and context.scope_type in ("CLASS", "COLLEGE"):
                can_review = assigned_to_current
            elif node == "DORM_MANAGER_REVIEW" and context.scope_type == "DORM_BUILDING":
                can_review = assigned_to_current

        item.update({
            "fromBuildingName": from_building.building_name if from_building else "",
            "fromRoomNo": from_room.room_no if from_room else "",
            "fromBedNo": from_bed.bed_no if from_bed else "",
            "fromBedLabel": _label(from_bed, from_room, from_building),
            "toBuildingName": to_building.building_name if to_building else "",
            "toRoomNo": to_room.room_no if to_room else "",
            "toBedNo": to_bed.bed_no if to_bed else "",
            "toBedLabel": _label(to_bed, to_room, to_building),
            "allowedActions": ["APPROVE", "REJECT"] if can_review else [],
        })
    return items


def install() -> None:
    from app.models import DormBed, DormRoom, StudentProfile
    from app.services import affairs_dorm_service as dorm

    def list_beds(room_id, user):
        with session() as db:
            room = db.get(DormRoom, int(room_id))
            if not room or room.is_deleted or room.tenant_id != _tid():
                raise not_found("房间不存在")
            dorm._require_dorm_scope(db, room.building_id, user)
            rows = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(), DormBed.room_id == int(room_id),
                DormBed.is_deleted.is_(False),
            ).order_by(DormBed.bed_no)).all()
            student_ids = {int(x.student_id) for x in rows if x.student_id}
            students = {
                int(x.id): x.real_name
                for x in db.scalars(select(StudentProfile).where(
                    StudentProfile.tenant_id == _tid(),
                    StudentProfile.id.in_(student_ids or {-1}),
                    StudentProfile.is_deleted.is_(False),
                )).all()
            }
            return [{
                "bedId": str(row.id), "roomId": str(row.room_id), "bedNo": row.bed_no,
                "status": row.status, "studentId": str(row.student_id or ""),
                "occupantName": students.get(int(row.student_id), "") if row.student_id else None,
                "occupiedAt": _iso(row.occupied_at), "version": int(row.version or 0),
            } for row in rows]

    original_list_transfers = dorm.list_transfers

    def list_transfers(user, status=None, page=1, page_size=50, student_id=None):
        """补齐审批人必须看到的原床→目标床，并按真实当前节点/受理人投影动作。"""
        items, total = original_list_transfers(
            user, status=status, page=page, page_size=page_size, student_id=student_id,
        )
        return project_transfer_items(items, user), total

    dorm.list_beds = list_beds
    dorm.list_transfers = list_transfers
