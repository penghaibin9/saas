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
)


@event.listens_for(BusinessFormVersion, "before_update")
def _published_version_is_immutable(_mapper, _connection, target: BusinessFormVersion) -> None:
    state = inspect(target)
    previously_published = state.attrs.status.history.deleted and state.attrs.status.history.deleted[0] == "PUBLISHED"
    still_published = str(target.status or "").upper() == "PUBLISHED"
    # ``DISABLED`` is a lifecycle state, not a return to draft.  Once a version
    # has ever been published its schema identity must remain immutable forever.
    # ``published_at`` survives disable and is therefore the durable marker.
    ever_published = target.published_at is not None
    if previously_published or still_published or ever_published:
        changed = [name for name in _IMMUTABLE_PUBLISHED_FIELDS if state.attrs[name].history.has_changes()]
        if changed:
            raise ValueError("published business form version is immutable: " + ",".join(changed))
