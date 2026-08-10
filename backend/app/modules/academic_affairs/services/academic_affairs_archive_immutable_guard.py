"""Stage C3 archived-semester immutability guard.

``FROZEN`` is an operational pause and may still use the ordinary term unfreeze flow.
``ARCHIVED`` is a historical fact boundary: the formal archive service must never reopen
an archived batch/term by mutating it back to DRAFT/PUBLISHED. Historical corrections
must append a correction record/version and keep the original archive intact.
"""
from __future__ import annotations

from app.core.exceptions import AppException


def reject_archive_unfreeze(user, batch_id, reason=None):
    """Fail closed for the legacy ARCHIVED -> DRAFT/PUBLISHED reopening command."""
    raise AppException(
        "TERM_ARCHIVED",
        "该学期已正式归档，禁止通过普通解冻回退历史事实；如需更正，请走归档后纠错流程并保留原归档版本。",
        http_status=409,
    )


def install(archive_service) -> None:
    """Bind the formal archive service to immutable archived semantics."""
    archive_service.unfreeze = reject_archive_unfreeze
