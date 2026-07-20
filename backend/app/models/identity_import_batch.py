"""Persistent identity-import prevalidation batches shared by every API instance."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class IdentityImportBatch(PKMixin, TenantMixin, CommonMixin, Base):
    """One-time identity import payload and its distributed confirmation lease.

    Initial passwords are never stored here.  The payload contains only the
    validated source rows and installation suggestions needed by later steps.
    """

    __tablename__ = "t_identity_import_batch"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_no", name="uk_identity_import_batch_no"),
    )

    batch_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operator_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="VALIDATED", index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    raw_rows_json: Mapped[list] = mapped_column(JSON, nullable=False)
    errors_json: Mapped[list] = mapped_column(JSON, nullable=False)
    pre_errors_json: Mapped[list] = mapped_column(JSON, nullable=False)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    relationships_json: Mapped[list] = mapped_column(JSON, nullable=False)
    relation_errors_json: Mapped[list] = mapped_column(JSON, nullable=False)
    public_result_json: Mapped[dict | None] = mapped_column(JSON)
    claim_token: Mapped[str | None] = mapped_column(String(64), index=True)
    claim_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
