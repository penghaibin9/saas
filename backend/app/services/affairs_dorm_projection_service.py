"""宿舍列表投影：床位并发版本与调宿审批证据。"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import not_found
from app.services.db_service import _iso, _tid, session


def install() -> None:
    from app.models import DormBed, DormBuilding, DormRoom, StudentProfile
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

    def _label(bed, room, building) -> str:
        if not bed:
            return "原床位未记录"
        parts = [
            (building.building_name if building else ""),
            (f"{room.room_no}室" if room and room.room_no else ""),
            (f"{bed.bed_no}床" if bed.bed_no else f"床位#{bed.id}"),
        ]
        return " / ".join(x for x in parts if x) or f"床位#{bed.id}"

    def list_transfers(user, status=None, page=1, page_size=50, student_id=None):
        """补齐审批人必须看到的原床→目标床，不允许只展示内部床位 ID。"""
        items, total = original_list_transfers(
            user, status=status, page=page, page_size=page_size, student_id=student_id,
        )
        if not items:
            return items, total
        bed_ids = {
            int(value)
            for item in items
            for value in (item.get("fromBedId"), item.get("toBedId"))
            if str(value or "").isdigit()
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
        for item in items:
            from_bed = beds.get(int(item["fromBedId"])) if str(item.get("fromBedId") or "").isdigit() else None
            to_bed = beds.get(int(item["toBedId"])) if str(item.get("toBedId") or "").isdigit() else None
            from_room = rooms.get(int(from_bed.room_id)) if from_bed and from_bed.room_id else None
            to_room = rooms.get(int(to_bed.room_id)) if to_bed and to_bed.room_id else None
            from_building = buildings.get(int(from_bed.building_id)) if from_bed and from_bed.building_id else None
            to_building = buildings.get(int(to_bed.building_id)) if to_bed and to_bed.building_id else None
            item.update({
                "fromBuildingName": from_building.building_name if from_building else "",
                "fromRoomNo": from_room.room_no if from_room else "",
                "fromBedNo": from_bed.bed_no if from_bed else "",
                "fromBedLabel": _label(from_bed, from_room, from_building),
                "toBuildingName": to_building.building_name if to_building else "",
                "toRoomNo": to_room.room_no if to_room else "",
                "toBedNo": to_bed.bed_no if to_bed else "",
                "toBedLabel": _label(to_bed, to_room, to_building),
                "allowedActions": ["APPROVE", "REJECT"] if item.get("status") in dorm.TRANSFER_NODES else [],
            })
        return items, total

    dorm.list_beds = list_beds
    dorm.list_transfers = list_transfers
