"""岗位实习中心 · 岗位匹配（意向 + 匹配结果）。

独立业务表，不改岗位库/实习学生表结构：
- t_internship_intention：学生实习意向
- t_internship_match：推荐/人工匹配台账；CONFIRMED 时调用已有 assign_position 落岗
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, Computed, DateTime, Integer, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class InternshipIntention(PKMixin, TenantMixin, CommonMixin, Base):
    """t_internship_intention 学生实习意向。

    并发不变量：同一实习记录同时只能有一条进行中（DRAFT/SUBMITTED）意向。
    `create_intention()` 原本是「无锁 SELECT 查进行中 → 没有就 INSERT」，两个并发请求
    会同时查到「没有」、各插一条（实测 5 轮里 4 轮复现）。撤回（WITHDRAWN）之后应当允许
    重新填，所以不变量只约束「同时活动」的行——沿用请假/补卡同一套写法（生成列在非活动时
    为 NULL + 唯一索引）。见迁移 20260814_ix_first_create。
    """
    __tablename__ = "t_internship_intention"
    __table_args__ = (UniqueConstraint("tenant_id", "active_record_id",
                                       name="uk_ix_intention_active"),)

    record_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True,
                                           comment="→ t_internship_record.id")
    active_record_id: Mapped[int | None] = mapped_column(
        BigInteger,
        Computed("CASE WHEN is_deleted = 0 AND status IN ('DRAFT', 'SUBMITTED') "
                 "THEN record_id ELSE NULL END", persisted=True),
        comment="仅进行中（DRAFT/SUBMITTED）时等于 record_id，用于唯一索引；其余为 NULL")
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
