"""岗位实习中心 · 岗位匹配（意向 + 匹配结果）。

独立业务表，不改岗位库/实习学生表结构：
- t_internship_intention：学生实习意向
- t_internship_match：推荐/人工匹配台账；CONFIRMED 时调用已有 assign_position 落岗
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipIntention(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_intention 学生实习意向。"""
    __tablename__ = "t_internship_intention"

    record_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True,
                                           comment="→ t_internship_record.id")
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True,
                                            comment="→ t_student_profile.id")
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    preferred_city: Mapped[str | None] = mapped_column(String(100))
    preferred_industry: Mapped[str | None] = mapped_column(String(100))
    preferred_company_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    preferred_position_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    intention_note: Mapped[str | None] = mapped_column(String(500))
    # DRAFT / SUBMITTED / WITHDRAWN
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)


class InternshipApplication(PKMixin, TenantMixin, CommonMixin, Base):
    """Formal internship application ledger, independent from matching intentions."""
    __tablename__ = "t_internship_application"
    __table_args__ = (UniqueConstraint("tenant_id", "record_id", "volunteer_no",
                                       name="uk_intern_application_record_volunteer"),)

    record_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    # POSITION / SELF_ARRANGED. SELF_ARRANGED always uses volunteer_no=0.
    application_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    volunteer_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    position_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    company_name: Mapped[str | None] = mapped_column(String(200))
    position_name: Mapped[str | None] = mapped_column(String(100))
    work_address: Mapped[str | None] = mapped_column(String(300))
    contact_name: Mapped[str | None] = mapped_column(String(100))
    contact_phone: Mapped[str | None] = mapped_column(String(64))
    evidence_file_id: Mapped[str | None] = mapped_column(String(64))
    application_note: Mapped[str | None] = mapped_column(String(500))
    # DRAFT / PENDING_REVIEW / APPROVED / REJECTED / WITHDRAWN / CANCELLED
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_comment: Mapped[str | None] = mapped_column(String(500))


class InternshipMatch(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_match 匹配结果 / 推荐台账。"""
    __tablename__ = "t_internship_match"

    record_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    position_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # AUTO_MAJOR / AUTO_ENTERPRISE / MANUAL / BATCH
    match_type: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL", index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    major_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enterprise_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conflict_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conflict_reason: Mapped[str | None] = mapped_column(String(500))
    # RECOMMENDED / PENDING_CONFIRM / CONFIRMED / REJECTED / CONFLICT / CANCELLED
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RECOMMENDED", index=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(100))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(500))
