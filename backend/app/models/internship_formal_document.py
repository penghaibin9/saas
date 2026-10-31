"""Yiyang C08/G17 formal printable document facts."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipFormalDocument(PKMixin, TenantMixin, CommonMixin, Base):
    """Immutable version pointer for one generated formal PDF."""

    __tablename__ = "t_internship_formal_document"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "internship_id", "document_type", "document_version",
            name="uk_ix_formal_document_version",
        ),
        Index(
            "ix_ix_formal_document_lookup",
            "tenant_id", "internship_id", "document_type", "status",
        ),
    )

    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    document_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    file_id: Mapped[str | None] = mapped_column(String(64))
    file_sha256: Mapped[str | None] = mapped_column(String(64))
    generated_by_user_id: Mapped[str | None] = mapped_column(String(64))
    generated_by_name: Mapped[str | None] = mapped_column(String(100))
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="GENERATED",
        comment="GENERATED/SUPERSEDED",
    )
