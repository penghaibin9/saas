"""C-W4/W5 live authority guards for grade correction.

The mature correction command remains the single owner of append-only formal-grade
correction, workflow, audit and outbox semantics.  This guard narrows two runtime
authority decisions without duplicating those business writes:

* teacher correction requests use the current formal TeachingTask.teacher_key;
* correction academic review inherits the original grade workflow's concrete
  ACADEMIC_REVIEW assignee when that same account is still ACTIVE, school-level and
  still holds the current ``academicAffairs.gradeChange.review`` School IAM authority.

The second rule preserves the already-proven responsibility chain instead of guessing
among several ACADEMIC_ADMIN accounts.  Missing, stale or ambiguous responsibility
remains fail-closed in the canonical correction resolver.

Installation is performed by the C-owned grade core router rather than the shared
services/__init__.py, avoiding INT-owned registration collisions.
"""
from __future__ import annotations

from . import academic_affairs_grade_core_service as _core
from . import academic_affairs_grade_correction_command as _correction
from . import academic_affairs_grade_execution_service as _execution
from . import academic_affairs_grade_service as _public

_canonical_resolve_change_assignee = _correction.resolve_change_assignee


def change_request(task_id: int, record_id: int, user, body) -> dict:
    """Run the canonical append-only correction request under live teacher authority."""
    with _execution._canonical_delegate(task_id, user, lock_owner=True) as delegated_user:
        return _correction.change_request(task_id, record_id, delegated_user, body)


change_request._grade_live_teacher_authority = True


def resolve_change_assignee(db, node: str, task) -> int:
    """Reuse the original grade academic assignee when it is still currently valid.

    The original grade workflow already created a concrete ``ACADEMIC_REVIEW``
    WorkflowTask through the canonical School IAM resolver before publication.  That
    assignment is a stronger responsibility fact than reconstructing an owner from a
    broad role such as ACADEMIC_ADMIN.  Reuse it only after re-validating the current
    correction-review permission and school-level scope; otherwise delegate to the
    canonical correction resolver, which stays fail-closed.
    """
    if node != _correction._ACADEMIC_NODE:
        return _canonical_resolve_change_assignee(db, node, task)

    from app.models import WorkflowTask

    candidates = _correction._permission_holder_ids(db, _correction._REVIEW_PERM)
    college_bound = _correction._college_bound_user_ids(db)
    school_level = {int(uid) for uid in candidates if int(uid) not in college_bound}
    instance_id = int(getattr(task, "workflow_instance_id", 0) or 0)

    inherited: set[int] = set()
    if instance_id > 0:
        rows = db.query(WorkflowTask.assignee_id).filter(
            WorkflowTask.tenant_id == _core._tid(),
            WorkflowTask.instance_id == instance_id,
            WorkflowTask.node_code == _correction._ACADEMIC_NODE,
            WorkflowTask.is_deleted.is_(False),
            WorkflowTask.assignee_id.is_not(None),
        ).all()
        for row in rows:
            raw = row[0]
            uid = int(raw or 0)
            if uid > 0 and uid in school_level and _correction._active_user(db, uid):
                inherited.add(uid)

    if len(inherited) == 1:
        return next(iter(inherited))
    if len(inherited) > 1:
        raise _correction._conflict(
            "原成绩教务终审存在多个有效责任人，无法安全继承更正终审受理人",
            node=node,
            candidateUserIds=[str(uid) for uid in sorted(inherited)],
        )
    return _canonical_resolve_change_assignee(db, node, task)


resolve_change_assignee._grade_correction_review_authority = True


def install() -> None:
    """Idempotently bind teacher authority and correction-review responsibility.

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

    current_resolver = getattr(_correction, "resolve_change_assignee", None)
    if not getattr(current_resolver, "_grade_correction_review_authority", False):
        _correction.resolve_change_assignee = resolve_change_assignee
