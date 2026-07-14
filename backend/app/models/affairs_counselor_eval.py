"""13A-D 辅导员考评（D 包·指标/采集/评分/申诉/发布）模型。

指标库 t_affairs_counselor_eval_indicator（可配权重/满分）+ 考评记录 t_affairs_counselor_eval
（按周期对辅导员评分,scores_json 明细,总分,发布,申诉复核）。来源可追溯（留痕 AuditTrail）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class CounselorEvalIndicator(PKMixin, TenantMixin, CommonMixin, Base):
    """考评指标（学校可配）。category 师德/工作量/学生工作/科研/满意度…；status ENABLED/DISABLED。"""
    __tablename__ = "t_affairs_counselor_eval_indicator"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    weight: Mapped[float | None] = mapped_column(Numeric(6, 2), comment="权重(%)")
    max_score: Mapped[float | None] = mapped_column(Numeric(6, 2), default=100, comment="满分")
    sort_order: Mapped[int | None] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ENABLED", index=True)

    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uk_counselor_indicator_name"),)


class CounselorEval(PKMixin, TenantMixin, CommonMixin, Base):
    """辅导员考评记录（一周期一辅导员一条）。status DRAFT/PUBLISHED；
    申诉：appeal_status NONE/SUBMITTED/REVIEWED；appeal_result UPHELD维持/ADJUSTED调整。"""
    __tablename__ = "t_affairs_counselor_eval"

    period_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="考评周期,如 2025-2026-1")
    counselor_key: Mapped[str] = mapped_column(String(100), nullable=False, comment="辅导员标识")
    counselor_name: Mapped[str | None] = mapped_column(String(100))
    scores_json: Mapped[dict | None] = mapped_column(JSON, comment="{indicatorId: score} 明细")
    total_score: Mapped[float | None] = mapped_column(Numeric(8, 2))
    remark: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    appeal_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NONE", index=True)
    appeal_reason: Mapped[str | None] = mapped_column(String(1000))
    appeal_result: Mapped[str | None] = mapped_column(String(30), comment="UPHELD/ADJUSTED")
    appeal_opinion: Mapped[str | None] = mapped_column(String(1000))

    __table_args__ = (UniqueConstraint("tenant_id", "period_code", "counselor_key",
                                       name="uk_counselor_eval_period_key"),)
