from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import UnifiedTodo, User
from app.modules.platform.business_collaboration.assignment_service import TodoCollaborationError
from app.modules.platform.business_collaboration.delegation_service import TodoActingDelegationService
from app.modules.platform.business_collaboration.models import TodoActingDelegation, TodoWorkAssignment
from app.modules.platform.business_collaboration.sla_service import TodoSlaProjectionService


TENANT = 9101


def _actor(user_id: int, user_type="TEACHER"):
    return {
        "userId": f"u_{user_id}", "userType": user_type,
        "currentRoleCode": "COUNSELOR", "tenantId": str(TENANT),
    }


def _factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        User.__table__, UnifiedTodo.__table__, TodoWorkAssignment.__table__,
        TodoActingDelegation.__table__,
    ):
        table.create(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add_all([
            User(id=701, tenant_id=TENANT, login_name="owner", real_name="委托老师",
                 password_hash="x", user_type="TEACHER", status="ACTIVE"),
            User(id=702, tenant_id=TENANT, login_name="delegate", real_name="代理老师",
                 password_hash="x", user_type="TEACHER", status="ACTIVE"),
            User(id=703, tenant_id=TENANT, login_name="student", real_name="学生",
                 password_hash="x", user_type="STUDENT", status="ACTIVE"),
            User(id=704, tenant_id=TENANT, login_name="delegate2", real_name="第二代理老师",
                 password_hash="x", user_type="TEACHER", status="ACTIVE"),
            UnifiedTodo(
                tenant_id=TENANT, source_module="graduation", source_biz_type="FINAL",
                source_biz_id=1001, todo_type="GD_FINAL_REVIEW", assignee_id=701,
                student_id=31, title="终稿评阅", status="PENDING", version=3,
                due_at=datetime.utcnow() + timedelta(hours=8),
            ),
        ])
        db.commit()
        todo_id = db.query(UnifiedTodo.id).scalar()
    return factory, int(todo_id)


def _service(factory, events, **overrides):
    values = {
        "configuration_capability": lambda action, _todo, _actor, _db: action in {"DELEGATE", "REVOKE_OTHER"},
        "delegator_capability": lambda _action, _todo, _owner, _db: True,
        "delegate_capability": lambda _action, _todo, _actor, _db: True,
        "delegate_scope": lambda _todo, _actor, _db: True,
        "domain_capability": lambda _action, _todo, _actor, _db: True,
        "audit_sink": lambda event, _db: events.append(event),
    }
    values.update(overrides)
    return TodoActingDelegationService(factory, **values)


def _create(service, *, delegate=702, start=None, end=None, scope_type="ALL_TODOS", scope=None):
    now = datetime.utcnow()
    return service.create(
        tenant_id=TENANT, delegate_user_id=delegate,
        scope_type=scope_type, scope=scope or {},
        effective_from=start or now - timedelta(minutes=5),
        effective_until=end or now + timedelta(days=1),
        reason="出差期间代理", actor=_actor(701),
    )


def test_acting_delegation_is_not_iam_and_overlap_is_rejected():
    columns = set(TodoActingDelegation.__table__.columns.keys())
    assert TodoActingDelegation.__tablename__ == "t_todo_acting_delegation"
    assert {"delegator_user_id", "delegate_user_id", "scope_type", "scope_json", "scope_hash"} <= columns
    assert not ({"role_id", "permission_id", "permission_codes", "data_scope"} & columns)
    overlap_index = next(
        index for index in TodoActingDelegation.__table__.indexes
        if index.name == "ix_todo_acting_delegation_overlap"
    )
    assert [column.name for column in overlap_index.columns] == [
        "tenant_id", "delegator_user_id", "status", "effective_from", "effective_until",
    ]
    source = inspect.getsource(TodoActingDelegationService)
    assert "RoleAssignment" not in source and "UserRole" not in source and "RolePermission" not in source

    factory, _todo_id = _factory()
    service = _service(factory, [])
    first = _create(service)
    assert first.status == "ACTIVE" and len(first.scope_hash) == 64
    try:
        _create(service)
        raise AssertionError("overlapping window must be rejected")
    except TodoCollaborationError as exc:
        assert exc.code == "DELEGATION_OVERLAP" and exc.http_status == 409

    try:
        _create(service, delegate=704)
        raise AssertionError("a second delegate must not create overlapping acting authority")
    except TodoCollaborationError as exc:
        assert exc.code == "DELEGATION_OVERLAP" and exc.http_status == 409

    try:
        _create(
            service, scope_type="TODO_TYPE",
            scope={"todoTypes": ["GD_FINAL_REVIEW"]},
        )
        raise AssertionError("different scope encodings must not bypass overlap protection")
    except TodoCollaborationError as exc:
        assert exc.code == "DELEGATION_OVERLAP" and exc.http_status == 409

    later_start = first.effective_until + timedelta(hours=1)
    later = _create(service, start=later_start, end=later_start + timedelta(hours=2))
    assert later.id != first.id and later.status == "SCHEDULED"

    aware_start_utc = later.effective_until + timedelta(hours=1)
    aware_start = aware_start_utc.replace(tzinfo=timezone.utc).astimezone(
        timezone(timedelta(hours=8))
    )
    aware_end = aware_start + timedelta(hours=2)
    aware = _create(service, start=aware_start, end=aware_end)
    assert aware.effective_from.tzinfo is None
    assert aware.effective_from == aware_start_utc


def test_student_delegatee_is_forbidden_and_runtime_rechecks_disabled_user():
    factory, todo_id = _factory()
    events = []
    service = _service(factory, events)
    try:
        _create(service, delegate=703)
        raise AssertionError("student cannot become staff Todo delegatee")
    except TodoCollaborationError as exc:
        assert exc.code == "VALIDATION_ERROR"

    delegation = _create(service)
    try:
        service.authorize_action(
            tenant_id=TENANT, todo_id=todo_id, action="OPEN",
            actor={**_actor(702), "tenantId": "999999"},
        )
        raise AssertionError("actor tenant mismatch must be denied before delegation lookup")
    except TodoCollaborationError as exc:
        assert exc.code == "NO_PERMISSION"

    authorized = service.authorize_action(
        tenant_id=TENANT, todo_id=todo_id, action="OPEN", actor=_actor(702),
    )
    assert authorized.actor_user_id == 702
    assert authorized.on_behalf_of_user_id == 701
    assert authorized.delegation_id == delegation.id
    assert events[-1]["detail"]["actorUserId"] == "702"
    assert events[-1]["detail"]["onBehalfOfUserId"] == "701"

    with factory() as db:
        delegate = db.get(User, 702)
        delegate.status = "DISABLED"
        db.commit()
    try:
        service.authorize_action(
            tenant_id=TENANT, todo_id=todo_id, action="OPEN", actor=_actor(702),
        )
        raise AssertionError("disabled delegate must be denied in real time")
    except TodoCollaborationError as exc:
        assert exc.code == "NO_PERMISSION"


def test_runtime_permission_scope_and_domain_intersection_is_fail_closed():
    factory, todo_id = _factory()
    base = _service(factory, [])
    _create(base, scope_type="TODO_TYPE", scope={"todoTypes": ["GD_FINAL_REVIEW"]})

    resolver_names = (
        "delegator_capability", "delegate_capability", "delegate_scope", "domain_capability",
    )
    for denied_name in resolver_names:
        overrides = {}
        if denied_name == "delegator_capability":
            overrides[denied_name] = lambda _action, _todo, _owner, _db: False
        elif denied_name == "delegate_scope":
            overrides[denied_name] = lambda _todo, _actor, _db: False
        else:
            overrides[denied_name] = lambda _action, _todo, _actor, _db: False
        service = _service(factory, [], **overrides)
        try:
            service.authorize_action(
                tenant_id=TENANT, todo_id=todo_id, action="OPEN", actor=_actor(702),
            )
            raise AssertionError(denied_name)
        except TodoCollaborationError as exc:
            assert exc.code == "NO_PERMISSION", denied_name


def test_runtime_fails_closed_if_legacy_rows_contain_ambiguous_overlap():
    factory, todo_id = _factory()
    service = _service(factory, [])
    original = _create(service)
    with factory() as db:
        db.add(TodoActingDelegation(
            tenant_id=TENANT,
            delegator_user_id=701,
            delegate_user_id=702,
            scope_type="TODO_TYPE",
            scope_json={"todoTypes": ["GD_FINAL_REVIEW"]},
            scope_hash="f" * 64,
            effective_from=original.effective_from,
            effective_until=original.effective_until,
            status="ACTIVE",
            reason="历史重叠脏数据",
            created_by=701,
            updated_by=701,
        ))
        db.commit()
    try:
        service.authorize_action(
            tenant_id=TENANT, todo_id=todo_id, action="OPEN", actor=_actor(702),
        )
        raise AssertionError("ambiguous legacy authority must fail closed")
    except TodoCollaborationError as exc:
        assert exc.code == "DELEGATION_AMBIGUOUS" and exc.http_status == 409


def test_runtime_fails_closed_for_corrupt_or_unknown_scope_payload():
    factory, todo_id = _factory()
    service = _service(factory, [])
    now = datetime.utcnow()
    with factory() as db:
        db.add(TodoActingDelegation(
            tenant_id=TENANT,
            delegator_user_id=701,
            delegate_user_id=702,
            scope_type="TODO_TYPE",
            scope_json=["GD_FINAL_REVIEW"],
            scope_hash="e" * 64,
            effective_from=now - timedelta(minutes=5),
            effective_until=now + timedelta(hours=1),
            status="ACTIVE",
            reason="历史损坏范围",
            created_by=701,
            updated_by=701,
        ))
        db.commit()
    try:
        service.authorize_action(
            tenant_id=TENANT, todo_id=todo_id, action="OPEN", actor=_actor(702),
        )
        raise AssertionError("malformed scope must fail closed")
    except TodoCollaborationError as exc:
        assert exc.code == "NO_DELEGATION"


def test_revoke_takes_effect_immediately_without_changing_iam_or_todo_owner():
    factory, todo_id = _factory()
    events = []
    service = _service(factory, events)
    delegation = _create(service)
    revoked = service.revoke(
        tenant_id=TENANT, delegation_id=delegation.id,
        reason="提前返校", actor=_actor(701),
    )
    assert revoked.status == "REVOKED" and revoked.revoked_by == 701
    assert revoked.reason == "出差期间代理"
    assert events[-1]["detail"]["reason"] == "提前返校"
    try:
        service.authorize_action(
            tenant_id=TENANT, todo_id=todo_id, action="OPEN", actor=_actor(702),
        )
        raise AssertionError("revoked delegation must be denied")
    except TodoCollaborationError as exc:
        assert exc.code == "NO_DELEGATION"
    with factory() as db:
        todo = db.get(UnifiedTodo, todo_id)
        assert todo.assignee_id == 701


def test_sla_projection_uses_existing_deadline_authorities_only():
    now = datetime(2026, 8, 30, 4, 0, 0)
    service = TodoSlaProjectionService(due_soon_hours=24)

    no_due = service.project(todo=SimpleNamespace(due_at=None, created_at=None), now=now)
    assert no_due.state == "NO_DUE" and no_due.source == "NONE"

    escalated_without_due = service.project(
        todo=SimpleNamespace(due_at=None, created_at=None), now=now, escalated=True,
    )
    assert escalated_without_due.state == "ESCALATED"
    assert escalated_without_due.due_at is None and escalated_without_due.remaining_seconds is None

    on_track = service.project(
        todo=SimpleNamespace(due_at=now + timedelta(days=3), created_at=now), now=now,
    )
    assert on_track.state == "ON_TRACK" and on_track.source == "UNIFIED_TODO"

    soon = service.project(
        todo=SimpleNamespace(due_at=now + timedelta(hours=3), created_at=now), now=now,
    )
    assert soon.state == "DUE_SOON"

    aware_now = now.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
    aware_due = aware_now + timedelta(hours=3)
    aware_projection = service.project(
        todo=SimpleNamespace(due_at=aware_due, created_at=aware_now), now=aware_now,
    )
    assert aware_projection.state == "DUE_SOON"
    assert aware_projection.due_at == now + timedelta(hours=3)
    assert aware_projection.due_at.tzinfo is None

    task_due = now - timedelta(minutes=1)
    overdue = service.project(
        todo=SimpleNamespace(due_at=now + timedelta(days=5), created_at=now),
        workflow_task=SimpleNamespace(deadline_at=task_due, created_at=now), now=now,
    )
    assert overdue.state == "OVERDUE" and overdue.due_at == task_due
    assert overdue.source == "WORKFLOW_TASK"

    escalated = service.project(
        todo=SimpleNamespace(due_at=task_due, created_at=now), now=now, escalated=True,
    )
    assert escalated.state == "ESCALATED"

    derived = service.project(
        todo=SimpleNamespace(due_at=None, created_at=now),
        workflow_task=SimpleNamespace(deadline_at=None, created_at=now),
        node_timeout_hours=6, definition_timeout_hours=12, now=now,
    )
    assert derived.due_at == now + timedelta(hours=6)
    assert derived.source == "WORKFLOW_NODE_TIMEOUT" and derived.state == "DUE_SOON"

    # Workflow timeout settings must not create a deadline from a non-workflow
    # Todo timestamp, and disabled/invalid settings fail closed to NO_DUE.
    for timeout, task in (
        (6, None),
        (0, SimpleNamespace(deadline_at=None, created_at=now)),
        (-1, SimpleNamespace(deadline_at=None, created_at=now)),
    ):
        projection = service.project(
            todo=SimpleNamespace(due_at=None, created_at=now),
            workflow_task=task, node_timeout_hours=timeout, now=now,
        )
        assert projection.state == "NO_DUE" and projection.source == "NONE"
