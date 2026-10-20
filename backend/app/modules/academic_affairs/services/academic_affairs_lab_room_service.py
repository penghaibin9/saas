"""Explicit lab-to-room binding under the same physical-room mutex as schedules."""
from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import AaLabBooking
from app.services.db_service import _tid, session


def conflict(message):
    return AppException("DATA_CONFLICT", message, http_status=409)


def bind(user, lab_id, body, *, command_key=None):
    from . import academic_affairs_resource_service as resources

    from . import academic_affairs_grade_command_receipt as receipts
    with session() as db:
        receipt, cached = receipts.begin(db, user, "RESOURCE_LAB_BIND", command_key,
                                         {"labId": str(lab_id), **body.model_dump()})
        if cached is not None:
            return cached
        peek = resources._load_lab(db, lab_id)
        old_room_id = peek.classroom_id
        new_room_id = body.classroomId
        # Room(s) first, then lab. No formal head or term authority is acquired here.
        for room_id in sorted({value for value in (old_room_id, new_room_id) if value}):
            resources._load(db, room_id)
        lab = resources._load_lab(db, lab_id, lock=True)
        if lab.version != body.expectedVersion or lab.classroom_id != old_room_id:
            raise conflict("实训室已变化，请重新读取后确认场地关联")
        if old_room_id != new_room_id:
            approved = db.scalar(select(AaLabBooking.id).where(
                AaLabBooking.tenant_id == _tid(), AaLabBooking.lab_id == lab.id,
                AaLabBooking.status == "APPROVED", AaLabBooking.is_deleted.is_(False),
            ).limit(1).with_for_update())
            if approved is not None:
                raise conflict("该实训室已有已批准预约，不能改变历史场地归属，请先完成原预约处置")
            lab.classroom_id = new_room_id
            lab.version = int(lab.version or 0) + 1
            resources._audit(db, lab.id, "SCHEDULE_ROOM_BIND", f"{old_room_id}->{new_room_id}", biz_type="AA_LAB")
        result = resources._lab_row(lab)
        receipts.finish(db, receipt, result)
        db.commit()
        return result


def lock_room(db, lab_id):
    from . import academic_affairs_resource_service as resources

    peek = resources._load_lab(db, lab_id)
    room_id = peek.classroom_id
    if room_id is None:
        raise conflict("实训室未关联正式排课场地，无法证明课表与预约不冲突")
    room = resources._load(db, room_id)
    lab = resources._load_lab(db, lab_id, lock=True)
    if lab.classroom_id != room_id:
        raise conflict("实训室场地关联已变化，请重新确认")
    return lab, room


def require_no_lab_booking(db, classroom_id, booking_date, slot_no, *, exclude_id=None):
    """Caller owns the room. Unknown historical approved sources are not empty slots."""
    query = select(AaLabBooking).where(
        AaLabBooking.tenant_id == _tid(), AaLabBooking.is_deleted.is_(False),
        AaLabBooking.status == "APPROVED", AaLabBooking.booking_date == booking_date,
        AaLabBooking.slot_no == slot_no,
        (AaLabBooking.classroom_id == classroom_id) | AaLabBooking.classroom_id.is_(None),
    )
    if exclude_id is not None:
        query = query.where(AaLabBooking.id != exclude_id)
    booking = db.scalars(query.order_by(AaLabBooking.id).limit(1).with_for_update(read=True)
                         .execution_options(populate_existing=True)).first()
    if booking is not None:
        raise conflict("该时段已有实训室预约占用，或存在场地来源未核实的历史预约")
