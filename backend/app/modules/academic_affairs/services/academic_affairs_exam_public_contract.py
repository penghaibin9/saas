"""Stable public contract for deferred-exam consumers.

The academic-affairs services package intentionally exposes
``academic_affairs_exam_service`` as the final facade. Consumers that need a
small part of the legacy deferred-exam state machine must therefore never rely
on package attribute resolution or import underscore-prefixed names directly.

This adapter resolves the canonical legacy module by its exact module path once,
then exposes only the stable state/DTO/audit surface used outside that module.
All state values still come from the canonical exam state machine; this module
does not define a second workflow.
"""
from __future__ import annotations

import importlib

_legacy = importlib.import_module(
    "app.modules.academic_affairs.services.academic_affairs_exam_service"
)

DEFER_STATUS_COUNSELOR_REVIEW = _legacy._D_COUNSELOR
DEFER_STATUS_APPROVED = _legacy._D_APPROVED
DEFER_STATUS_REJECTED = _legacy._D_REJECTED
DEFER_TERMINAL_STATUSES = frozenset({DEFER_STATUS_APPROVED, DEFER_STATUS_REJECTED})


def deferred_exam_dto(row) -> dict:
    """Return the canonical public DTO shape for a deferred-exam row."""
    return _legacy._defer_dto(row)


def record_exam_audit(db, biz_type, biz_id, action, detail="", before="", after=""):
    """Write using the canonical exam-domain audit formatter."""
    return _legacy._audit(db, biz_type, biz_id, action, detail, before, after)
