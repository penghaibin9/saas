from __future__ import annotations

from datetime import datetime, timedelta

from .delegation_schemas import SlaProjection
from .time_utils import naive_utc


class TodoSlaProjectionService:
    """Read-only SLA projection over existing deadline authorities."""

    def __init__(self, *, due_soon_hours: int = 24) -> None:
        self._due_soon = timedelta(hours=min(max(int(due_soon_hours), 1), 168))

    def project(
        self,
        *,
        todo,
        workflow_task=None,
        node_timeout_hours: int | None = None,
        definition_timeout_hours: int | None = None,
        escalated: bool = False,
        now: datetime | None = None,
    ) -> SlaProjection:
        instant = naive_utc(now) or datetime.utcnow()
        due_at = naive_utc(getattr(workflow_task, "deadline_at", None))
        source = "WORKFLOW_TASK" if due_at is not None else "NONE"
        if due_at is None:
            due_at = naive_utc(getattr(todo, "due_at", None))
            source = "UNIFIED_TODO" if due_at is not None else "NONE"
        if due_at is None:
            timeout = node_timeout_hours if node_timeout_hours is not None else definition_timeout_hours
            created_at = naive_utc(getattr(workflow_task, "created_at", None))
            try:
                timeout_value = int(timeout) if timeout is not None else None
            except (TypeError, ValueError):
                timeout_value = None
            # Node/definition settings are Workflow authority.  Applying them
            # to an arbitrary UnifiedTodo.created_at would invent a deadline.
            if timeout_value is not None and timeout_value > 0 and created_at is not None:
                due_at = created_at + timedelta(hours=timeout_value)
                source = "WORKFLOW_NODE_TIMEOUT" if node_timeout_hours is not None else "WORKFLOW_DEFINITION_TIMEOUT"
        if due_at is None:
            return SlaProjection(
                state="ESCALATED" if escalated else "NO_DUE",
                due_at=None,
                source="NONE",
                remaining_seconds=None,
            )
        remaining = int((due_at - instant).total_seconds())
        if escalated:
            state = "ESCALATED"
        elif remaining < 0:
            state = "OVERDUE"
        elif due_at <= instant + self._due_soon:
            state = "DUE_SOON"
        else:
            state = "ON_TRACK"
        return SlaProjection(
            state=state, due_at=due_at, source=source,
            remaining_seconds=remaining,
        )
