"""C-W3 compatibility bindings for published student exam/defer entrypoints.

The safe student exam provider owns only the formal-fact boundary. Mature exam
workflow services continue to own defer list/resubmit/review state transitions.
This guard rebinds the old ``academic_affairs_exam_service.defer_apply`` function
itself so every already-published PC/legacy caller receives the same formal-seat,
local-time and duplicate-submission command semantics without editing large/shared
routers.
"""
from __future__ import annotations

from . import academic_affairs_exam_service as legacy_exam
from . import student_exam_read_service as safe_exam


def _defer_apply(user, body) -> dict:
    if isinstance(body, dict):
        data = body
    elif hasattr(body, "model_dump"):
        data = body.model_dump()
    else:
        data = {
            "examCourseId": getattr(body, "examCourseId", None),
            "reasonType": getattr(body, "reasonType", None),
            "reason": getattr(body, "reason", None),
        }
    return safe_exam.defer_apply(user, data)


_defer_apply._formal_exam_seat_defer_guard = True


def install() -> None:
    current = getattr(legacy_exam, "defer_apply", None)
    if getattr(current, "_formal_exam_seat_defer_guard", False):
        return
    if not hasattr(legacy_exam, "_c_w3_original_defer_apply"):
        legacy_exam._c_w3_original_defer_apply = current
    legacy_exam.defer_apply = _defer_apply
