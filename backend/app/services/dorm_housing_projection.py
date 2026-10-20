"""Shared current housing facts. Allocation confirmation is not physical check-in."""
from sqlalchemy import and_, case, func, select

from app.models import DormBed, DormBuilding, DormRoom, DormStay, OrientationStudent
from app.services.db_service import _tid


def housing_query():
    live = DormStay.status.in_(["RESERVED", "ACTIVE"])
    ranked = select(
        DormStay,
        func.row_number().over(partition_by=DormStay.student_id,
            order_by=(case((live, 0), else_=1), DormStay.id.desc())).label("position"),
        func.sum(case((live, 1), else_=0)).over(partition_by=DormStay.student_id).label("live_count"),
    ).where(DormStay.tenant_id == _tid(), DormStay.is_deleted.is_(False)).subquery()
    consistent = and_(
        DormBed.id.is_not(None), DormRoom.id.is_not(None), DormBuilding.id.is_not(None),
        DormBed.room_id == ranked.c.room_id, DormBed.building_id == ranked.c.building_id,
        DormRoom.building_id == ranked.c.building_id,
        case((ranked.c.status == "ACTIVE", and_(DormBed.status == "OCCUPIED",
             DormBed.student_id == ranked.c.student_id)),
             else_=and_(DormBed.status == "LOCKED", DormBed.student_id.is_(None))),
        ranked.c.live_count == 1,
    )
    status = case((ranked.c.status.in_(["ACTIVE", "RESERVED"]),
                  case((consistent, ranked.c.status), else_="EXCEPTION")),
                  else_=ranked.c.status)
    return select(
        ranked.c.student_id, status.label("housing_status"), ranked.c.checkin_at,
        ranked.c.building_id, ranked.c.room_id, ranked.c.bed_id,
        DormBuilding.building_name, DormRoom.room_no, DormBed.bed_no,
    ).select_from(ranked).outerjoin(DormBed, and_(DormBed.id == ranked.c.bed_id,
        DormBed.tenant_id == _tid(), DormBed.is_deleted.is_(False))) \
     .outerjoin(DormRoom, and_(DormRoom.id == ranked.c.room_id,
        DormRoom.tenant_id == _tid(), DormRoom.is_deleted.is_(False))) \
     .outerjoin(DormBuilding, and_(DormBuilding.id == ranked.c.building_id,
        DormBuilding.tenant_id == _tid(), DormBuilding.is_deleted.is_(False))) \
     .where(ranked.c.position == 1)


def housing_fields(fact=None, *, linked=True):
    status = fact["housing_status"] if fact else ("UNASSIGNED" if linked else "UNLINKED")
    assigned = status in ("RESERVED", "ACTIVE")
    labels = {"RESERVED": "已预留 · 待入住", "ACTIVE": "已入住", "ENDED": "已退宿",
              "CANCELLED": "预留已取消", "EXCEPTION": "住宿待核查",
              "UNLINKED": "待关联学生档案", "UNASSIGNED": "未分配"}
    return {
        "housingStatus": status, "housingStatusLabel": labels.get(status, "住宿待核查"),
        "dormStatus": {"RESERVED": "ASSIGNED", "ACTIVE": "CHECKED_IN",
                       "EXCEPTION": "EXCEPTION"}.get(status, "UNASSIGNED"),
        "dormStatusLabel": labels.get(status, "住宿待核查"),
        "building": (fact["building_name"] or "") if assigned else "",
        "room": f'{fact["room_no"]}室 {fact["bed_no"]}床' if assigned else "",
        "buildingId": str(fact["building_id"]) if assigned else "",
        "roomId": str(fact["room_id"]) if assigned else "",
        "bedId": str(fact["bed_id"]) if assigned else "",
        "checkinTime": fact["checkin_at"].isoformat() if status == "ACTIVE" and fact["checkin_at"] else "",
    }


def housing_map(db, student_ids):
    ids = list({int(sid) for sid in student_ids if sid})
    if not ids:
        return {}
    q = housing_query().subquery()
    return {int(r["student_id"]): housing_fields(r) for r in
            db.execute(select(q).where(q.c.student_id.in_(ids))).mappings()}


def sync_orientation(db, student_id):
    """Keep legacy summary fields in the same transaction; never manufacture a stay."""
    db.flush()
    facts = housing_map(db, [student_id]).get(int(student_id), housing_fields())
    for row in db.scalars(select(OrientationStudent).where(
        OrientationStudent.tenant_id == _tid(), OrientationStudent.student_id == student_id,
        OrientationStudent.is_deleted.is_(False), OrientationStudent.record_status == "ACTIVE",
    )):
        row.dorm_status = facts["dormStatus"]
        row.building, row.room = facts["building"], facts["room"]
        # OrientationStudent.checkin_time belongs to reporting. Physical dorm time is projected.
        row.version = int(row.version or 0) + 1
