"""学工材料补交与安全批次操作模型。

材料：缺项定义与每次补交版本分离，禁止覆盖历史文件；阶段 5 同步接入公共
FileAsset/FileVersion/FileBinding，旧字段继续保留兼容。
批次：主表与逐条结果分离，支持部分成功、失败重试、幂等和审计。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AffairsMaterialRequirement(PKMixin, TenantMixin, CommonMixin, Base):
    """某笔学生申请被明确要求补交的一项材料。"""

    __tablename__ = "t_affairs_material_requirement"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False)
    biz_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    item_code: Mapped[str] = mapped_column(String(100), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    requirement_reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="MISSING",
        comment="MISSING/PENDING_REVIEW/ACCEPTED/RETURNED/WAIVED",
    )
    return_round: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_owner_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    current_submission_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime)

    # 公共文件冻结中心阶段 5：同一缺项只有一个逻辑资产，重交形成不可变版本。
    asset_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    sensitivity_level: Mapped[str] = mapped_column(
        String(30), nullable=False, default="SENSITIVE",
        comment="NORMAL/PERSONAL/SENSITIVE/HIGHLY_SENSITIVE",
    )
    material_scope: Mapped[str] = mapped_column(
        String(30), nullable=False, default="STUDENT_SELF",
        comment="STUDENT_SELF/PSY_STUDENT/AID_RESTRICTED/BUSINESS_SCOPE",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "biz_type", "biz_id", "item_code",
            name="uk_affairs_material_requirement_biz_item",
        ),
        Index(
            "ix_affairs_material_requirement_biz",
            "tenant_id", "biz_type", "biz_id", "status",
        ),
        Index(
            "ix_affairs_material_requirement_sensitivity",
            "tenant_id", "sensitivity_level", "status",
        ),
    )


class AffairsMaterialSubmission(PKMixin, TenantMixin, CommonMixin, Base):
    """材料补交的不可覆盖版本；每次补交新增一行。"""

    __tablename__ = "t_affairs_material_submission"

    requirement_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    affairs_attachment_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    file_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="SUBMITTED",
        comment="SUBMITTED/ACCEPTED/RETURNED/SUPERSEDED",
    )
    submitted_by: Mapped[str | None] = mapped_column(String(64))
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_by: Mapped[str | None] = mapped_column(String(64))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_note: Mapped[str | None] = mapped_column(String(500))
    supersedes_id: Mapped[int | None] = mapped_column(BigInteger, index=True)

    # 兼容字段 file_id/affairs_attachment_id 继续双写；以下为公共版本权威引用。
    asset_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    file_version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    binding_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    sensitivity_level: Mapped[str] = mapped_column(
        String(30), nullable=False, default="SENSITIVE",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "requirement_id", "version_no",
            name="uk_affairs_material_submission_version",
        ),
        Index(
            "ix_affairs_material_submission_requirement",
            "tenant_id", "requirement_id", "status", "version_no",
        ),
        Index(
            "ix_affairs_material_submission_public_version",
            "tenant_id", "requirement_id", "file_version_id", "status",
        ),
    )


class AffairsBatchJob(PKMixin, TenantMixin, CommonMixin, Base):
    """一次安全批量办理的主记录。"""

    __tablename__ = "t_affairs_batch_job"

    batch_no: Mapped[str] = mapped_column(String(64), nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING",
        comment="PENDING/RUNNING/PARTIAL_SUCCESS/SUCCESS/FAILED/CANCELLED",
    )
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    retry_of_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    request_json: Mapped[dict | None] = mapped_column(JSON)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(String(1000))

    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_no", name="uk_affairs_batch_job_no"),
        UniqueConstraint(
            "tenant_id", "job_type", "idempotency_key",
            name="uk_affairs_batch_job_idempotency",
        ),
        Index("ix_affairs_batch_job_status", "tenant_id", "job_type", "status"),
    )


class AffairsBatchJobItem(PKMixin, TenantMixin, CommonMixin, Base):
    """批次中的一条业务记录及其独立执行结果。"""

    __tablename__ = "t_affairs_batch_job_item"

    batch_job_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(128), nullable=False)
    todo_type: Mapped[str | None] = mapped_column(String(50))
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False)
    biz_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    expected_version: Mapped[int | None] = mapped_column(Integer)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING",
        comment="PENDING/RUNNING/SUCCESS/FAILED/SKIPPED",
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    result_json: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "batch_job_id", "item_key",
            name="uk_affairs_batch_job_item_key",
        ),
        Index(
            "ix_affairs_batch_job_item_status",
            "tenant_id", "batch_job_id", "status",
        ),
    )
