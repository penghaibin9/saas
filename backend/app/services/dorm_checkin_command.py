"""Single and bulk check-in share one transaction-level authority."""
from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import DormBed, DormBuilding, DormRoom, DormStay, StudentProfile
from app.services.db_service import _tid, session
from app.services import affairs_dorm_service as dorm
from app.services.affairs_dorm_reliability_service import _strict_gender_ok


def checkin_in_transaction(db, bed_id, user, student_id, *,
                           expected_stay_id=None, expected_stay_version=None):
    student = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.id == int(student_id),
        StudentProfile.is_deleted.is_(False),
    ).with_for_update()).first()
    if not student:
        raise not_found("学生不存在")
    existing = db.scalars(select(DormBed).where(
        DormBed.tenant_id == _tid(),
        DormBed.student_id == int(student.id),
        DormBed.status == "OCCUPIED",
        DormBed.is_deleted.is_(False),
    ).with_for_update()).all()
    target = db.scalars(select(DormBed).where(
        DormBed.tenant_id == _tid(),
        DormBed.id == int(bed_id),
        DormBed.is_deleted.is_(False),
    ).with_for_update()).first()
    if not target:
        raise not_found("床位不存在")
    dorm._require_dorm_scope(db, target.building_id, user)
    if any(int(row.id) != int(target.id) for row in existing):
        raise AppException("DATA_CONFLICT", "该学生已有床位，请通过正式调宿流程变更")
    if existing and int(existing[0].id) == int(target.id):
        raise AppException("DATA_CONFLICT", "该学生已入住此床位")
    if target.status not in ("VACANT", "LOCKED") or target.student_id is not None:
        raise AppException("DATA_CONFLICT", "该床位已被占用或锁定")
    building = db.get(DormBuilding, int(target.building_id))
    if not building or building.is_deleted or building.tenant_id != _tid():
        raise not_found("楼栋不存在")
    if not _strict_gender_ok(building.gender_limit, student.gender):
        raise AppException("DATA_CONFLICT", "学生性别信息缺失或与楼栋限制不符")
    room = db.get(DormRoom, int(target.room_id))
    if not room or room.is_deleted or room.tenant_id != _tid():
        raise not_found("房间不存在")
    if expected_stay_id is not None:
        reservation = db.scalars(select(DormStay).where(
            DormStay.tenant_id == _tid(), DormStay.id == int(expected_stay_id),
            DormStay.student_id == int(student.id), DormStay.bed_id == int(target.id),
            DormStay.is_deleted.is_(False),
        ).with_for_update()).first()
        if (not reservation or reservation.status != "RESERVED"
                or int(reservation.version or 0) != int(expected_stay_version)):
            raise AppException("DATA_CONFLICT", "预留记录已变化，请重新核对后办理")
    from app.services.affairs_dorm_stay_service import activate_checkin
    stay = activate_checkin(db, bed=target, student=student, user=user)
    record_id = dorm._writeback_dorm_record(
        db, student.id, building.building_name, room.room_no, target.bed_no,
    )
    target.cs_dorm_record_id = record_id
    dorm._audit(db, "DORM_BED", target.id, "CHECKIN", f"student={student.id}")
    return {
        "bedId": str(target.id), "bedNo": target.bed_no,
        "studentId": str(student.id), "building": building.building_name,
        "room": room.room_no, "status": "OCCUPIED", "stayId": str(stay.id),
    }


def checkin(bed_id, user, student_id):
    with session() as db:
        result = checkin_in_transaction(db, bed_id, user, student_id)
        db.commit()
        return result
