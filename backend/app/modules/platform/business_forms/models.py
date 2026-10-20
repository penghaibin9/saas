"""The only two PLAT-B persistence tables.

Registration and Alembic migration are intentionally deferred to the serialized
PLAT-B migration slot after PLAT-A integration.  No submission table exists.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint, event, inspect
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class BusinessFormDefinition(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_business_form_definition"
    __table_args__ = (
        UniqueConstraint("tenant_id", "form_code", name="uk_business_form_definition_code"),
        Index("ix_business_form_definition_domain", "tenant_id", "domain_code", "enabled", "is_deleted"),
    )

    form_code: Mapped[str] = mapped_column(String(100), nullable=False)
    form_name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain_code: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active_version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)


class BusinessFormVersion(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_business_form_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "definition_id", "version_no", name="uk_business_form_version_no"),
        UniqueConstraint("tenant_id", "definition_id", "schema_hash", name="uk_business_form_version_hash"),
        Index("ix_business_form_version_status", "tenant_id", "form_code", "status", "effective_at", "is_deleted"),
    )

    definition_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    form_code: Mapped[str] = mapped_column(String(100), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    supported_clients_json: Mapped[list] = mapped_column(JSON, nullable=False)
    policy_refs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    domain_data_adapter: Mapped[str] = mapped_column(String(100), nullable=False)
    domain_command_adapter: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_by: Mapped[int | None] = mapped_column(BigInteger)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime)


_IMMUTABLE_PUBLISHED_FIELDS = (
    "form_code", "version_no", "schema_hash", "schema_version", "supported_clients_json",
    "policy_refs_json", "domain_data_adapter", "domain_command_adapter", "schema_json", "effective_at",
    "published_at", "published_by",
)


@event.listens_for(BusinessFormVersion, "before_update")
def _published_version_is_immutable(_mapper, _connection, target: BusinessFormVersion) -> None:
    state = inspect(target)
    old_statuses = {
        str(value or "").upper()
        for value in state.attrs.status.history.deleted
    }
    current_status = str(target.status or "").upper()
    if old_statuses:
        allowed_transitions = {
            ("DRAFT", "PUBLISHED"),
            ("PUBLISHED", "DISABLED"),
        }
        transitions = {(old, current_status) for old in old_statuses if old != current_status}
        if any(transition not in allowed_transitions for transition in transitions):
            raise ValueError("business form version lifecycle transition is invalid")
    first_publish = current_status == "PUBLISHED" and old_statuses == {"DRAFT"}
    # ``DISABLED`` is a lifecycle state, not a return to draft.  Once a version
    # has ever been published its schema identity and publication proof must
    # remain immutable forever.  Include deleted history so clearing
    # ``published_at`` in the same UPDATE cannot erase that durable marker.
    published_at_history = state.attrs.published_at.history
    had_published_at = target.published_at is not None or any(
        value is not None for value in published_at_history.deleted
    )
    ever_published = (
        current_status in {"PUBLISHED", "DISABLED"}
        or bool(old_statuses & {"PUBLISHED", "DISABLED"})
        or had_published_at
    )
    if ever_published and not first_publish:
        changed = [name for name in _IMMUTABLE_PUBLISHED_FIELDS if state.attrs[name].history.has_changes()]
        if changed:
            raise ValueError("published business form version is immutable: " + ",".join(changed))
