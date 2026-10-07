from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Computed, DateTime, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class TodoWorkAssignment(PKMixin, TenantMixin, CommonMixin, Base):
    """PLAT-D collaboration overlay; never replaces UnifiedTodo.assignee_id."""

    __tablename__ = "t_todo_work_assignment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "active_todo_key", name="uk_todo_work_assignment_active"),
        Index("ix_todo_work_assignment_history", "tenant_id", "todo_id", "id"),
        Index("ix_todo_work_assignment_owner", "tenant_id", "owner_user_id", "status"),
    )

    todo_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    assignment_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="CLAIM/MANUAL_ASSIGNMENT"
    )
    owner_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_owner_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="ACTIVE", comment="ACTIVE/RELEASED/REVOKED/EXPIRED"
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime)
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime)
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    release_reason: Mapped[str | None] = mapped_column(String(500))
    source_ref_type: Mapped[str | None] = mapped_column(String(80))
    source_ref_id: Mapped[str | None] = mapped_column(String(100))
    active_todo_key: Mapped[int | None] = mapped_column(
        BigInteger,
        Computed(
            "CASE WHEN status = 'ACTIVE' AND released_at IS NULL THEN todo_id ELSE NULL END",
            persisted=True,
        ),
        nullable=True,
    )


class TodoActingDelegation(PKMixin, TenantMixin, CommonMixin, Base):
    """Time-bounded Todo acting authority, deliberately unrelated to IAM roles."""

    __tablename__ = "t_todo_acting_delegation"
    __table_args__ = (
        Index(
            "ix_todo_acting_delegation_lookup",
            "tenant_id", "delegate_user_id", "delegator_user_id", "status",
            "effective_from", "effective_until",
        ),
        Index(
            "ix_todo_acting_delegation_overlap",
            "tenant_id", "delegator_user_id", "status", "effective_from", "effective_until",
        ),
    )

    delegator_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    delegate_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(
        String(40), nullable=False, comment="ALL_TODOS/TODO_TYPE/SOURCE_MODULE/TODO_IDS"
    )
    scope_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scope_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    effective_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="ACTIVE", comment="SCHEDULED/ACTIVE/REVOKED/EXPIRED"
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_by: Mapped[int | None] = mapped_column(BigInteger)
