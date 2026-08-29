"""AA-05 grade write transaction adapter without a second business implementation.

The canonical score-entry and submit state machines live only in
``academic_affairs_grade_service.enter_score`` and ``submit_task``.  Teacher execution still needs a
live TeachingTask/TeachingClassTeacher authority check and owner lock in the *same* SQLAlchemy Session
as the canonical write.  Opening an outer Session and then calling the canonical service caused the
old nested-session timeout; copying the whole write chain here fixed that timeout but created a second
business implementation that had to stay lock-step with the canonical one.

This adapter now uses a request-local ContextVar only for the two teacher write commands.  While the
canonical service is running, its existing ``_core._check_course_scope(task, user)`` call is narrowly
wrapped: the wrapper obtains the Session already owning ``task``, performs the live teacher check/lock
inside that same transaction, then delegates the historical grade-task snapshot scope check.  No
roster, score, workflow, audit, state-transition, or commit logic is duplicated here.
"""
from __future__ import annotations

from contextvars import ContextVar

from sqlalchemy.orm import object_session

from app.core.exceptions import AppException

from . import academic_affairs_grade_core_service as _core
from . import academic_affairs_grade_execution_service as _exec
from . import academic_affairs_grade_service as _grade


_ACTIVE_WRITE_USER: ContextVar[dict | None] = ContextVar(
    "academic_grade_live_write_user",
    default=None,
)
_ORIGINAL_CHECK_COURSE_SCOPE = None
_INSTALLED = False


def _same_session_course_scope(task, user):
    """Inject live teacher authority into the canonical service's own DB transaction."""
    actor = _ACTIVE_WRITE_USER.get()
    if actor is None:
        return _ORIGINAL_CHECK_COURSE_SCOPE(task, user)

    # Historical/admin supplement tasks have no formal teaching-task relation.  Keep the canonical
    # fail-closed snapshot rule exactly as before; the live-owner bridge only applies where a current
    # teaching relation actually exists.
    if not getattr(task, "teaching_task_id", None):
        return _ORIGINAL_CHECK_COURSE_SCOPE(task, actor)

    db = object_session(task)
    if db is None:
        raise AppException(
            "DATA_CONFLICT",
            "成绩任务未绑定当前数据库会话，无法安全校验实时任课教师",
            http_status=409,
        )

    # grade_teacher_relation_guard installs the formal TeachingClassTeacher authority primitive on
    # _exec._require_live_teacher before this adapter's install() runs.  Resolve it dynamically here
    # so import order cannot freeze an older authority implementation.
    _exec._require_live_teacher(db, task, actor, lock_owner=True)

    # The canonical service deliberately retains the historical grade-task teacher snapshot.
    # Once current ownership is proven and pinned, bridge only the scope identity expected by that
    # legacy comparison. Audit/operator identity continues to come from request context.
    delegated_user = _exec._canonical_scope_user(task, actor)
    return _ORIGINAL_CHECK_COURSE_SCOPE(task, delegated_user)


_same_session_course_scope._grade_live_write_same_session_guard = True


def _enter_score_single_session(task_id: int, user, body) -> dict:
    """Run the one canonical enter_score implementation with same-session live authority."""
    token = _ACTIVE_WRITE_USER.set(dict(user or {}))
    try:
        return _grade.enter_score(task_id, user, body)
    finally:
        _ACTIVE_WRITE_USER.reset(token)


_enter_score_single_session.__grade_single_session_guard__ = True


def _submit_task_single_session(task_id: int, user) -> dict:
    """Run the one canonical submit_task implementation with same-session live authority."""
    token = _ACTIVE_WRITE_USER.set(dict(user or {}))
    try:
        return _grade.submit_task(task_id, user)
    finally:
        _ACTIVE_WRITE_USER.reset(token)


_submit_task_single_session.__grade_single_session_guard__ = True


def install() -> None:
    """Install once; keep canonical business functions as the only write-rule owners."""
    global _INSTALLED, _ORIGINAL_CHECK_COURSE_SCOPE
    if _INSTALLED:
        return

    current = _core._check_course_scope
    if not getattr(current, "_grade_live_write_same_session_guard", False):
        _ORIGINAL_CHECK_COURSE_SCOPE = current
        _core._check_course_scope = _same_session_course_scope
    elif _ORIGINAL_CHECK_COURSE_SCOPE is None:
        # Defensive idempotence for unusual reloads.  Normal application import reaches the branch
        # above exactly once.
        raise RuntimeError("grade same-session scope guard reloaded without canonical original")

    _exec.teacher_enter_score = _enter_score_single_session
    _exec.teacher_submit_task = _submit_task_single_session
    _INSTALLED = True
