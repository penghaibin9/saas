"""Every actionable review needs a concrete assignee, including school-wide roles."""
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.services import affairs_aid_service as aid
from app.services import affairs_discipline_service as discipline
from app.services import affairs_leave_service as leave


class _Db:
    def __init__(self, assignee):
        self.task = None if assignee is None else SimpleNamespace(assignee_id=assignee)

    def scalars(self, statement):
        return SimpleNamespace(first=lambda: self.task)


def _review(kind, db, row, user):
    if kind == "leave":
        return leave._check_review_node(db, row, user)
    if kind == "cancel":
        return leave._check_leave_action_assignee(db, row, user, todo_type="LEAVE_CANCEL")
    if kind == "aid":
        return aid._check_aid_assignee(db, row, user)
    if kind == "aid-adjust":
        return aid._check_aid_assignee(db, row, user, todo_type="AID_ADJUST")
    return discipline._check_disc_node(db, "COLLEGE_REVIEW", user, workflow_instance_id=row.workflow_instance_id)


@pytest.mark.parametrize("kind", ["leave", "cancel", "aid", "aid-adjust", "discipline"])
@pytest.mark.parametrize("assignee,actor", [(None, "db-42"), (0, "db-42"), (43, "db-42"), (42, "unknown")])
def test_school_scope_never_substitutes_for_valid_task_assignment(monkeypatch, kind, assignee, actor):
    from app.core import affairs_security
    monkeypatch.setattr(affairs_security, "build_affairs_context",
                        lambda user, db=None: SimpleNamespace(scope_type="TENANT_ALL"))
    for service in [leave, aid, discipline]:
        monkeypatch.setattr(service, "_tid", lambda: 1)
    row = SimpleNamespace(id=7, workflow_instance_id=8, affairs_status="COUNSELOR_REVIEW", status="COUNSELOR_REVIEW")
    with pytest.raises(AppException):
        _review(kind, _Db(assignee), row, {"userId": actor, "currentRoleCode": "STUDENT_AFFAIRS_ADMIN"})


@pytest.mark.parametrize("kind", ["leave", "aid", "discipline"])
def test_workflow_reviews_reject_missing_workflow(monkeypatch, kind):
    from app.core import affairs_security
    monkeypatch.setattr(affairs_security, "build_affairs_context",
                        lambda user, db=None: SimpleNamespace(scope_type="TENANT_ALL"))
    row = SimpleNamespace(id=7, workflow_instance_id=None, affairs_status="COUNSELOR_REVIEW", status="COUNSELOR_REVIEW")
    with pytest.raises(AppException):
        _review(kind, _Db(42), row, {"userId": "db-42", "currentRoleCode": "STUDENT_AFFAIRS_ADMIN"})


@pytest.mark.parametrize("kind", ["leave", "cancel", "aid", "aid-adjust", "discipline"])
def test_concrete_assignee_can_review_and_aid_adjustment_needs_only_its_own_todo(monkeypatch, kind):
    from app.core import affairs_security
    monkeypatch.setattr(affairs_security, "build_affairs_context",
                        lambda user, db=None: SimpleNamespace(scope_type="TENANT_ALL"))
    for service in [leave, aid, discipline]:
        monkeypatch.setattr(service, "_tid", lambda: 1)
    row = SimpleNamespace(id=7, workflow_instance_id=None if kind == "aid-adjust" else 8,
                          affairs_status="COUNSELOR_REVIEW", status="ADJUST_REVIEW" if kind == "aid-adjust" else "COUNSELOR_REVIEW")
    if kind == "discipline":
        from app.services import affairs_assignee_service
        monkeypatch.setattr(affairs_assignee_service, "resolve_assignee_ids", lambda *args, **kwargs: [42])
    role = "COLLEGE_ADMIN" if kind == "discipline" else "STUDENT_AFFAIRS_ADMIN"
    _review(kind, _Db(42), row, {"userId": "db-42", "currentRoleCode": role})
