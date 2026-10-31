"""实习就业预审材料与版本；正式就业事实只由既有就业审批链生成。"""
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class InternshipEmploymentRegistration(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = 't_internship_employment_registration'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'internship_id', name='uk_ix_employment_record'),
        Index('ix_ix_employment_batch_status', 'tenant_id', 'batch_id', 'status', 'is_deleted'),
        Index('ix_ix_employment_student', 'tenant_id', 'student_id', 'is_deleted'),
    )
    internship_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='SUBMITTED')
    current_submission_id: Mapped[int | None] = mapped_column(BigInteger)
    revision_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class InternshipEmploymentSubmission(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """Append-only encrypted declaration; never edit an earlier submission."""
    __tablename__ = 't_internship_employment_submission'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'registration_id', 'revision_no', name='uk_ix_employment_submission'),
        Index('ix_ix_employment_submission_lookup', 'tenant_id', 'registration_id', 'revision_no'),
    )
    registration_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    registration_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    source_company_id: Mapped[int | None] = mapped_column(BigInteger)
    details_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    attachments_json: Mapped[list] = mapped_column(JSON, nullable=False)
    correction_reason_encrypted: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    submitted_by: Mapped[int] = mapped_column(BigInteger, nullable=False)


class InternshipEmploymentReview(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """Append-only review of one exact declaration revision."""
    __tablename__ = 't_internship_employment_review'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'submission_id', name='uk_ix_employment_review'),
        Index('ix_ix_employment_review_lookup', 'tenant_id', 'registration_id', 'submission_id'),
    )
    registration_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    submission_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    comment_encrypted: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reviewer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    employment_submission_id: Mapped[int | None] = mapped_column(BigInteger, index=True,
        comment="预审通过后同事务创建的正式就业去向申请；旧预审版本保持原关联")
