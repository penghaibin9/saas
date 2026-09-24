"""Cross-check existing formal schedules and approved classroom bookings.

Formal writers serialize on the existing term authority before business locks.
Booking approval holds only its classroom/booking locks and uses a fresh reader;
it must never acquire that authority or a ScopeHead lock while holding a room.
The calendar and schedule services remain the owners of occurrence semantics.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.core.academic_term_authority_lock import lock_term_authority
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session


def lock_formal_authority(db):
    if not lock_term_authority(db, _tid()):
        raise AppException("DATA_CONFLICT", "缺少正式课表协调行，不能修改课表或校历", http_status=409)


def lock_term(db, term_id):
    from app.models import AaTerm
    term = db.scalar(select(AaTerm).where(
        AaTerm.tenant_id == _tid(), AaTerm.id == int(term_id), AaTerm.is_deleted.is_(False),
    ).with_for_update().execution_options(populate_existing=True))
    if term is None:
        raise not_found("学期不存在")
    return term


def formal_timeline_head_id(db, term_id, *, lock=False):
    from app.models import AaScheduleScopeHead
    query = select(AaScheduleScopeHead.id).where(
        AaScheduleScopeHead.tenant_id == _tid(), AaScheduleScopeHead.term_id == int(term_id),
        AaScheduleScopeHead.active_batch_id.is_not(None), AaScheduleScopeHead.is_deleted.is_(False),
    ).order_by(AaScheduleScopeHead.id).limit(1)
    return db.scalar(query.with_for_update(read=True) if lock else query)


def require_no_formal_timeline(db, term_id):
    """Caller holds authority then term. An invalid active head is also a blocker."""
    head_id = formal_timeline_head_id(db, term_id, lock=True)
    if head_id is not None:
        raise AppException("DATA_CONFLICT", "该学期已有正式课表，不能直接改写时间轴或校历事件",
                           details={"termId": str(term_id), "scopeHeadId": str(head_id)}, http_status=409)


def require_booking_slot_free(classroom_id, booking_date, slot_no):
    """Read after caller acquired Classroom X; never reuse its earlier RR snapshot."""
    from .academic_affairs_resource_service import _schedule_occurrences_on_date
    with session() as reader:
        for item, facts in _schedule_occurrences_on_date(reader, booking_date):
            if int(item.slot_no) != int(slot_no):
                continue
            if item.classroom_id is None and str(item.classroom_text or "").strip():
                raise AppException("DATA_CONFLICT", "该时段正式课表存在未关联教室，无法确认借用不冲突",
                                   details=facts, http_status=409)
            if item.classroom_id is not None and int(item.classroom_id) == int(classroom_id):
                raise AppException("DATA_CONFLICT", "该教室时段已有正式课程，不能批准借用",
                                   details={**facts, "classroomId": str(classroom_id)}, http_status=409)


def require_no_booking_conflict(db, term, items):
    """Caller holds formal authority and term; lock rooms, then current-read bookings.

Only stable classroom IDs join the two sources. Bookings are checked on their
actual calendar date, including SWAP targets, using the existing occurrence owner.
"""
    from app.models import AaClassroomBooking, AaLabBooking
    from . import academic_affairs_attendance_occurrence_consumer as occurrence
    from .academic_affairs_resource_service import _load as load_classroom

    by_room_slot = {}
    for item in items:
        if item.classroom_id is None:
            if str(item.classroom_text or "").strip():
                raise AppException("DATA_CONFLICT", "课位尚未关联正式教室 ID，不能发布或生效",
                                   details={"scheduleItemId": str(item.id) if item.id else None}, http_status=409)
            continue
        by_room_slot.setdefault((int(item.classroom_id), int(item.slot_no)), []).append(item)
    rooms = sorted({room_id for room_id, _slot in by_room_slot})
    for room_id in rooms:
        room = load_classroom(db, room_id)
        if room.status != "AVAILABLE" or not room.allow_schedule:
            raise AppException("DATA_CONFLICT", "教室当前不可用或未允许排课", http_status=409,
                               details={"classroomId": str(room_id)})
    if not rooms:
        return
    start, end = occurrence._date_value(term.start_date), occurrence._date_value(term.end_date)
    if not start or not end:
        raise AppException("DATA_CONFLICT", "学期起止日期不完整，无法核对预约", http_status=409)
    dates = {}
    for model, kind in ((AaClassroomBooking, "CLASSROOM"), (AaLabBooking, "LAB")):
        room_condition = model.classroom_id.in_(rooms)
        if kind == "LAB":
            room_condition = room_condition | model.classroom_id.is_(None)
        query = select(model).where(
            model.tenant_id == _tid(), room_condition, model.status == "APPROVED", model.is_deleted.is_(False),
            model.booking_date >= start.isoformat(), model.booking_date <= end.isoformat(),
        ).order_by(model.id).with_for_update(read=True).execution_options(populate_existing=True)
        last_id = 0
        while True:
            bookings = db.scalars(query.where(model.id > last_id).limit(200)).all()
            if not bookings:
                break
            for booking in bookings:
                candidates = by_room_slot.get((int(booking.classroom_id), int(booking.slot_no)), []) if booking.classroom_id else [
                    item for (_room, slot), values in by_room_slot.items() if slot == int(booking.slot_no) for item in values
                ]
                if not candidates:
                    continue
                requested = date.fromisoformat(str(booking.booking_date))
                if requested not in dates:
                    try:
                        logical, _source, _event = occurrence._calendar_logical_date(db, term, requested, lock=True)
                        dates[requested] = occurrence._week_and_weekday(term, logical)
                    except AppException as error:
                        if error.message in {"该日期为校历调休停课日，不能创建普通课堂考勤", "该日期为节假日，不能创建普通课堂考勤"}:
                            dates[requested] = None
                        else:
                            raise
                coordinate = dates[requested]
                if coordinate is None:
                    continue
                week_no, weekday = coordinate
                for item in candidates:
                    if (int(item.weekday) == weekday and int(item.start_week) <= week_no <= int(item.end_week)
                            and occurrence._parity_allows(item.week_parity, week_no)):
                        raise AppException("DATA_CONFLICT", "拟生效课位与已批准资源预约冲突或来源未核实",
                                           details={"bookingId": str(booking.id), "classroomId": str(booking.classroom_id) if booking.classroom_id else None,
                                                    "resourceKind": kind,
                                                    "date": str(booking.booking_date), "slotNo": booking.slot_no,
                                                    "scheduleItemId": str(item.id) if item.id else None,
                                                    "termId": str(term.id)}, http_status=409)
            last_id = int(bookings[-1].id)
