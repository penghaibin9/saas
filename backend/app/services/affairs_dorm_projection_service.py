"""宿舍床位列表补充并发版本投影。"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import not_found
from app.services.db_service import _iso, _tid, session


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

    dorm.list_beds = list_beds
