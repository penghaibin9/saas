"""C-W3 current invigilator authority guard for exam incident commands.

The mature exam service authorizes a teacher to record an incident through
``_is_invigilator_of_course``.  The legacy helper did not exclude soft-deleted
invigilation rows or inactive/deleted rooms, so historical assignment residue could
keep granting write authority after room replacement / assignment cleanup.

Published reassignment still remains owned by the mature exam facade: it updates the
canonical AaExamInvigilator current owner. This guard only narrows the scope helper to
that current fact and never writes assignment/room/course state.
"""
from __future__ import annotations

from sqlalchemy import select

from . import academic_affairs_exam_service as exam


def _is_invigilator_of_course(db, exam_course_id, teacher_keys):
    from app.models import AaExamInvigilator, AaExamRoom

    keys = sorted({str(value).strip() for value in (teacher_keys or set()) if str(value).strip()})
    if not keys:
        return False
    found = db.scalar(
        select(AaExamInvigilator.id)
        .join(
            AaExamRoom,
            (AaExamRoom.id == AaExamInvigilator.exam_room_id)
            & (AaExamRoom.tenant_id == AaExamInvigilator.tenant_id),
        )
        .where(
            AaExamInvigilator.tenant_id == exam._tid(),
            AaExamInvigilator.teacher_key.in_(keys),
            AaExamInvigilator.is_deleted.is_(False),
            AaExamRoom.tenant_id == exam._tid(),
            AaExamRoom.exam_course_id == int(exam_course_id),
            AaExamRoom.status == "ACTIVE",
            AaExamRoom.is_deleted.is_(False),
        )
        .limit(1)
    )
    return found is not None


_is_invigilator_of_course._current_invigilator_scope_guard = True


def install() -> None:
    current = getattr(exam, "_is_invigilator_of_course", None)
    if getattr(current, "_current_invigilator_scope_guard", False):
        return
    if not hasattr(exam, "_current_invigilator_scope_original"):
        exam._current_invigilator_scope_original = current
    exam._is_invigilator_of_course = _is_invigilator_of_course
