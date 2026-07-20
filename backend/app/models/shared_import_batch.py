"""Generic persistent Dry-Run batch used by student and legacy-data imports."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class SharedImportBatch(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_shared_import_batch"
    __table_args__ = (
        UniqueConstraint("tenant_id", "namespace", "batch_no", name="uk_shared_import_batch_no"),
        UniqueConstraint("tenant_id", "namespace", "request_id", name="uk_shared_import_request_id"),
    )

    namespace: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operator_key: Mapped[str | None] = mapped_column(String(160), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    errors_json: Mapped[list] = mapped_column(JSON, nullable=False)
    public_result_json: Mapped[dict | None] = mapped_column(JSON)
    request_id: Mapped[str | None] = mapped_column(String(160))
    claim_token: Mapped[str | None] = mapped_column(String(64), index=True)
    claim_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
