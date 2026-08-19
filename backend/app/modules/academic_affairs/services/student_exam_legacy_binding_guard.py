"""C-W3 compatibility bindings for published student exam/defer entrypoints.

The safe student exam provider owns only the formal-fact boundary. Mature exam
workflow services continue to own defer list/resubmit/review state transitions.
This guard rebinds the real legacy ``academic_affairs_exam_service.defer_apply``
submodule itself so direct historical imports receive the same formal-seat,
local-time and duplicate-submission command semantics without touching the package's
canonical ``academic_affairs_exam_service`` facade export.
"""
from __future__ import annotations

from importlib import import_module

from . import student_exam_read_service as safe_exam

# ``services.__init__`` intentionally exports the canonical exam facade under the
# package attribute ``academic_affairs_exam_service``. A relative ``from . import``
# would therefore resolve that facade attribute and accidentally monkey-patch the
# canonical public owner. Import the concrete legacy submodule by its full module
# path so compatibility hardening stays confined to direct legacy imports.
legacy_exam = import_module(
    "app.modules.academic_affairs.services.academic_affairs_exam_service"
)


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
