"""13A 学工中心域模型（t_affairs_ 前缀 + 公共字段；审计链 append-only）。

P1 仅落地两张：班干部任免（t_affairs_class_cadre）+ 学工域业务留痕（t_affairs_audit_trail）。
其余 24 张按《13A-13B-数据表与迁移策略草案》各阶段 revision 逐步建（P0 已冻结表名与字段）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class AffairsClassCadre(PKMixin, TenantMixin, CommonMixin, Base):
    """班干部任免记录（草案 §3.2）。审计=TRAIL；不走审批。"""
    __tablename__ = "t_affairs_class_cadre"

    class_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    position: Mapped[str] = mapped_column(String(50), nullable=False,
                                          comment="MONITOR/LEAGUE_SECRETARY/STUDY/LIFE/SPORTS/... 班干部职务")
    term_code: Mapped[str | None] = mapped_column(String(50), comment="学年学期编码")
    appointed_at: Mapped[datetime | None] = mapped_column(DateTime)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE", comment="ACTIVE/REMOVED")
    record_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    void_reason: Mapped[str | None] = mapped_column(String(500))


class AffairsAuditTrail(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """学工域业务留痕（append-only，结构对齐 t_cs_audit_trail）。"""
    __tablename__ = "t_affairs_audit_trail"

    biz_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    biz_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    operator: Mapped[str | None] = mapped_column(String(100))
    role_name: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(String(1000))
    before_val: Mapped[str | None] = mapped_column(String(1000))
    after_val: Mapped[str | None] = mapped_column(String(1000))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class AffairsLeaveCancelRecord(PKMixin, TenantMixin, CommonMixin, Base):
    """销假记录（草案 §3.1，子表回链 t_cs_leave.id）。"""
    __tablename__ = "t_affairs_leave_cancel_record"

    leave_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    actual_return_at: Mapped[datetime | None] = mapped_column(DateTime)
    proof_note: Mapped[str | None] = mapped_column(String(500), comment="返校证明说明（附件走 t_file_object）")
    confirm_by: Mapped[str | None] = mapped_column(String(100))
    confirm_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirm_note: Mapped[str | None] = mapped_column(String(500))
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="SUBMITTED",
                                        comment="SUBMITTED/CONFIRMED/RETURNED")


class AffairsLeaveExtension(PKMixin, TenantMixin, CommonMixin, Base):
    """续假申请（草案 §3.1，子表回链 t_cs_leave.id）。"""
    __tablename__ = "t_affairs_leave_extension"

    leave_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    old_end_time: Mapped[datetime | None] = mapped_column(DateTime)
    new_end_time: Mapped[datetime | None] = mapped_column(DateTime)
    extend_days: Mapped[float | None] = mapped_column(Numeric(5, 1))
    reason: Mapped[str | None] = mapped_column(String(500))
    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="SUBMITTED",
                                        comment="SUBMITTED/APPROVED/REJECTED/CANCELLED")
