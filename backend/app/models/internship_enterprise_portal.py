"""岗位实习 E 系列 · 企业协同 Authority 模型。

A01 按冻结顺序逐步补齐本文件。企业主档、岗位、正式志愿和最终落岗继续复用
EmpCompany / InternshipPosition / InternshipApplication / assign_position_in_tx()。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin
from app.modules.internship.enterprise_collaboration_contract import (
    RECRUITMENT_CAMPAIGN_STATUSES,
)


class InternshipRecruitmentCampaign(PKMixin, TenantMixin, CommonMixin, Base):
    """学校招聘季 Authority；phase 永不持久化，只由 status + 时间窗派生。"""

    __tablename__ = "t_internship_recruitment_campaign"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "campaign_code", name="uk_intern_recruit_campaign_code"
        ),
        UniqueConstraint(
            "tenant_id",
            "batch_id",
            "round_no",
            name="uk_intern_recruit_campaign_round",
        ),
        Index(
            "ix_intern_recruit_campaign_batch_status",
            "tenant_id",
            "batch_id",
            "status",
            "is_deleted",
        ),
        Index(
            "ix_intern_recruit_campaign_select_window",
            "tenant_id",
            "status",
            "student_select_start_at",
            "student_select_end_at",
        ),
    )

    batch_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="→ t_internship_batch.id"
    )
    campaign_code: Mapped[str] = mapped_column(String(100), nullable=False)
    campaign_name: Mapped[str] = mapped_column(String(200), nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="DRAFT",
        comment="/".join(RECRUITMENT_CAMPAIGN_STATUSES),
    )

    invite_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    invite_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    position_submit_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    position_submit_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    student_select_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    student_select_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    enterprise_decision_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    enterprise_decision_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    school_confirm_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    school_confirm_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    enterprise_access_end_at: Mapped[datetime | None] = mapped_column(DateTime)

    enterprise_confirm_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    remark: Mapped[str | None] = mapped_column(String(500))
