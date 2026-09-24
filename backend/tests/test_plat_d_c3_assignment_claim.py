from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from app.models import UnifiedTodo
from app.modules.platform.business_collaboration.assignment_service import (
    TodoAssignmentService,
    TodoCollaborationError,
)
from app.modules.platform.business_collaboration.models import TodoWorkAssignment


TENANT = 8101


class _Visible:
    def can_view(self, _todo, _user, _db):
        return True


def _actor(user_id=701, user_type="TEACHER", **extra):
    return {
        "userId": f"u_{user_id}", "userType": user_type,
        "currentRoleCode": "COUNSELOR", "tenantId": str(TENANT),
        **extra,
    }


def _factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    UnifiedTodo.__table__.create(engine)
    TodoWorkAssignment.__table__.create(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        pool = UnifiedTodo(
            tenant_id=TENANT, source_module="student-affairs", source_biz_type="LEAVE",
            source_biz_id=9001, todo_type="LEAVE_APPROVAL", assignee_id=0,
            student_id=31, title="池待办", status="PENDING", version=4,
        )
        direct = UnifiedTodo(
            tenant_id=TENANT, source_module="student-affairs", source_biz_type="RISK",
            source_biz_id=9002, todo_type="RISK_HANDLE", assignee_id=888,
            student_id=32, title="直接待办", status="PENDING", version=2,
        )
        db.add_all([pool, direct])
        db.commit()
        return factory, int(pool.id), int(direct.id)


def _service(factory, events=None):
    events = events if events is not None else []
    return TodoAssignmentService(
        factory,
        visibility_provider=_Visible(),
        capability_resolver=lambda action, _todo, _user, _db: action in {"CLAIM", "RELEASE"},
        audit_sink=lambda event, _db: events.append(event),
    )


def test_mysql_model_has_generated_nullable_active_unique():
    ddl = str(CreateTable(TodoWorkAssignment.__table__).compile(dialect=mysql.dialect()))
    normalized = " ".join(ddl.upper().split())
    assert "ACTIVE_TODO_KEY BIGINT GENERATED ALWAYS AS" in normalized
    assert "CASE WHEN STATUS = 'ACTIVE' AND RELEASED_AT IS NULL THEN TODO_ID ELSE NULL END" in normalized
    assert "CONSTRAINT UK_TODO_WORK_ASSIGNMENT_ACTIVE UNIQUE (TENANT_ID, ACTIVE_TODO_KEY)" in normalized


def test_claim_release_reclaim_keeps_history_and_never_mutates_source_assignee():
    factory, pool_id, direct_id = _factory()
    events = []
    service = _service(factory, events)

    first = service.claim(
        tenant_id=TENANT, todo_id=pool_id, expected_version=4, user=_actor(701),
    )
    assert first.status == "ACTIVE" and first.owner_user_id == 701
    assert service.effective_owner(tenant_id=TENANT, todo_id=pool_id).ownership_mode == "CLAIMED"
    direct = service.effective_owner(tenant_id=TENANT, todo_id=direct_id)
    assert direct.ownership_mode == "DIRECT" and direct.owner_user_id == 888

    released = service.release(
        tenant_id=TENANT, todo_id=pool_id, expected_version=4,
        reason="交回池中", user=_actor(701),
    )
    assert released.status == "RELEASED" and released.released_at is not None
    assert service.effective_owner(tenant_id=TENANT, todo_id=pool_id).ownership_mode == "POOL"

    second = service.claim(
        tenant_id=TENANT, todo_id=pool_id, expected_version=4, user=_actor(702),
    )
    assert second.id != first.id and second.owner_user_id == 702
    with factory() as db:
        history = db.scalars(select(TodoWorkAssignment).where(
            TodoWorkAssignment.todo_id == pool_id,
        ).order_by(TodoWorkAssignment.id)).all()
        todo = db.get(UnifiedTodo, pool_id)
        assert [row.status for row in history] == ["RELEASED", "ACTIVE"]
        assert todo.assignee_id == 0
        assert todo.version == 4

    assert [event["action"] for event in events] == ["待办认领", "待办释放", "待办认领"]
    assert events[0]["detail"]["originalAssigneeId"] == "0"


def test_claim_fail_closed_for_default_visibility_capability_student_and_version():
    factory, pool_id, _direct_id = _factory()
    default = TodoAssignmentService(factory, audit_sink=lambda _event, _db: None)
    try:
        default.claim(tenant_id=TENANT, todo_id=pool_id, expected_version=4, user=_actor())
        raise AssertionError("default visibility/capability must deny")
    except TodoCollaborationError as exc:
        assert exc.code == "TODO_NOT_FOUND"

    service = _service(factory)
    for expected_version, actor, code in (
        (3, _actor(), "VERSION_CONFLICT"),
        (4, _actor(user_type="STUDENT"), "NO_PERMISSION"),
        (4, _actor(tenantId="999999"), "NO_PERMISSION"),
    ):
        try:
            service.claim(
                tenant_id=TENANT, todo_id=pool_id,
                expected_version=expected_version, user=actor,
            )
            raise AssertionError(code)
        except TodoCollaborationError as exc:
            assert exc.code == code


def test_release_rechecks_visibility_and_capability_even_for_current_owner():
    factory, pool_id, _direct_id = _factory()
    _service(factory).claim(
        tenant_id=TENANT, todo_id=pool_id, expected_version=4, user=_actor(701),
    )
    default_capability = TodoAssignmentService(
        factory, visibility_provider=_Visible(), audit_sink=lambda _event, _db: None,
    )
    try:
        default_capability.release(
            tenant_id=TENANT, todo_id=pool_id, expected_version=4,
            reason="交回池中", user=_actor(701),
        )
        raise AssertionError("owner release must not bypass default-deny capability")
    except TodoCollaborationError as exc:
        assert exc.code == "NO_PERMISSION"

    invisible = TodoAssignmentService(
        factory,
        capability_resolver=lambda action, _todo, _user, _db: action == "RELEASE",
        audit_sink=lambda _event, _db: None,
    )
    try:
        invisible.release(
            tenant_id=TENANT, todo_id=pool_id, expected_version=4,
            reason="交回池中", user=_actor(701),
        )
        raise AssertionError("owner release must recheck current visibility")
    except TodoCollaborationError as exc:
        assert exc.code == "TODO_NOT_FOUND"

    with factory() as db:
        db.get(UnifiedTodo, pool_id).status = "COMPLETED"
        db.commit()
    try:
        _service(factory).release(
            tenant_id=TENANT, todo_id=pool_id, expected_version=4,
            reason="交回池中", user=_actor(701),
        )
        raise AssertionError("completed Todo assignment must not be released back to a pool")
    except TodoCollaborationError as exc:
        assert exc.code == "TODO_NOT_RELEASABLE"


def test_active_unique_race_is_returned_as_typed_409(monkeypatch):
    factory, pool_id, _direct_id = _factory()
    service = _service(factory)
    service.claim(tenant_id=TENANT, todo_id=pool_id, expected_version=4, user=_actor(701))

    # Simulate the exact race window: the pre-check saw no row, while the
    # generated unique key observes the winner during flush.
    monkeypatch.setattr(service, "_active_assignment", lambda *_args, **_kwargs: None)
    try:
        service.claim(tenant_id=TENANT, todo_id=pool_id, expected_version=4, user=_actor(702))
        raise AssertionError("second claimant must conflict")
    except TodoCollaborationError as exc:
        assert exc.code == "TODO_ALREADY_CLAIMED"
        assert exc.http_status == 409
