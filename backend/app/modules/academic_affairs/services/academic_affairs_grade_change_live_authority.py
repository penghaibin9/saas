"""C-W4/W5 live teacher authority for grade correction requests.

The mature correction command intentionally remains the single owner of append-only
formal-grade correction, workflow, audit and outbox semantics.  This guard only
replaces its *teacher scope precondition*: for a grade task linked to a formal
TeachingTask, the current TeachingTask.teacher_key is authoritative.  The
AaGradeTask.teacher_key creation snapshot is used only as a compatibility identity
inside the already-proven live-owner transaction.

Installation is performed by the C-owned grade core router rather than the shared
services/__init__.py, avoiding INT-owned registration collisions.
"""
from __future__ import annotations

from . import academic_affairs_grade_core_service as _core
from . import academic_affairs_grade_correction_command as _correction
from . import academic_affairs_grade_execution_service as _execution
from . import academic_affairs_grade_service as _public


def change_request(task_id: int, record_id: int, user, body) -> dict:
    """Run the canonical append-only correction request under live teacher authority."""
    with _execution._canonical_delegate(task_id, user, lock_owner=True) as delegated_user:
        return _correction.change_request(task_id, record_id, delegated_user, body)


change_request._grade_live_teacher_authority = True


def install() -> None:
    """Idempotently bind every public teacher correction entry to one wrapper.

    ``academic_affairs_grade_execution_service`` originally exposed a convenience
    wrapper of its own. Once the public grade service is rebound here, leaving that
    older wrapper in place would nest two independent live-owner row-lock sessions.
    Rebinding the execution convenience name to this same function keeps exactly one
    TeachingTask lock and one canonical correction command invocation.
    """
    for module in (_core, _public):
        current = getattr(module, "change_request", None)
        if not getattr(current, "_grade_live_teacher_authority", False):
            setattr(module, "change_request", change_request)
    _execution.teacher_change_request = change_request
