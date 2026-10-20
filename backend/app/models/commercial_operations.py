"""M8 customer-success bridge and actual service-cost control facts.

These tables do not duplicate the customer-success ticket state machine.  The link
only proves that a settled commercial refund was handed to the existing SupportTicket
authority.  Cost rows are append-only operator-recorded actual facts; no estimate,
forecast or currency conversion is manufactured here.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class CommercialAfterSalesLink(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_commercial_after_sales_link"
    __table_args__ = (
        UniqueConstraint("tenant_id", "refund_case_id", name="uk_commercial_after_sales_refund"),
        UniqueConstraint("tenant_id", "support_ticket_id", name="uk_commercial_after_sales_ticket"),
        Index("ix_commercial_after_sales_order", "tenant_id", "order_id", "id"),
    )

    refund_case_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("t_commercial_refund_case.id"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_order.id"), nullable=False, index=True)
    support_ticket_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("t_support_ticket.id"), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default="REFUND_ENTITLEMENT_REVIEW")
    module_snapshot_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    settlement_ref_snapshot: Mapped[str | None] = mapped_column(String(160))
    linked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    linked_by: Mapped[int | None] = mapped_column(BigInteger)


class CommercialServiceCostRecord(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_commercial_service_cost_record"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_key_hash", name="uk_commercial_service_cost_request"),
        Index("ix_commercial_service_cost_time", "tenant_id", "occurred_at", "id"),
        Index("ix_commercial_service_cost_ticket", "tenant_id", "support_ticket_id", "id"),
        Index("ix_commercial_service_cost_order", "tenant_id", "order_id", "id"),
    )

    request_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    cost_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="SUPPORT/DELIVERY/TRAINING/REFUND_FEE/OTHER")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    support_ticket_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("t_support_ticket.id"), nullable=True, index=True)
    refund_case_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("t_commercial_refund_case.id"), nullable=True, index=True)
    order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("t_order.id"), nullable=True, index=True)
    external_ref: Mapped[str | None] = mapped_column(String(160))
    note: Mapped[str | None] = mapped_column(String(500))
    recorded_by: Mapped[int | None] = mapped_column(BigInteger)
