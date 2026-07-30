"""毕业设计材料中心业务语义模型。

文件字节、安全状态、不可变版本和业务绑定继续统一复用公共
FileObject / FileAsset / FileVersion / FileBinding；本文件只保存毕业设计材料规则、
学生材料项、旧数据迁移检查点和模板资产适用策略，禁止复制公共文件模型。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class GraduationMaterialRule(PKMixin, TenantMixin, CommonMixin, Base):
    """批次级材料规则版本；启用新版本不修改历史批次证据。"""

    __tablename__ = "t_gd_material_rule"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "batch_id", "rule_code", "rule_version",
            name="uk_gd_material_rule_version",
        ),
        Index(
            "ix_gd_material_rule_active",
            "tenant_id", "batch_id", "status", "enabled", "is_deleted",
        ),
    )

    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    rule_code: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="DRAFT",
        comment="DRAFT/ENABLED/DISABLED/ARCHIVED",
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_owner_role: Mapped[str] = mapped_column(String(40), nullable=False, default="STUDENT")
    version_policy: Mapped[str] = mapped_column(String(40), nullable=False, default="IMMUTABLE_APPEND")
    archive_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sensitivity_level: Mapped[str] = mapped_column(String(30), nullable=False, default="SENSITIVE")
    applicable_scope_json: Mapped[dict | None] = mapped_column(JSON)
    applicable_major_id: Mapped[str | None] = mapped_column(String(64), index=True)
    applicable_topic_type: Mapped[str | None] = mapped_column(String(64), index=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime)
    required_items_json: Mapped[list | None] = mapped_column(JSON)
    allowed_ext_json: Mapped[list | None] = mapped_column(JSON)
    max_files: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=50 * 1024 * 1024)
    remark: Mapped[str | None] = mapped_column(String(500))


class GraduationMaterialItem(PKMixin, TenantMixin, CommonMixin, Base):
    """规则中的一个材料定义，不是学生提交实例。"""

    __tablename__ = "t_gd_material_item"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "rule_id", "material_code",
            name="uk_gd_material_item_code",
        ),
        Index(
            "ix_gd_material_item_stage",
            "tenant_id", "rule_id", "biz_stage", "enabled", "sort_no", "is_deleted",
        ),
    )

    rule_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    biz_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    material_code: Mapped[str] = mapped_column(String(100), nullable=False)
    material_name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_role: Mapped[str] = mapped_column(String(40), nullable=False, default="STUDENT")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allowed_ext_json: Mapped[list | None] = mapped_column(JSON)
    max_files: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=50 * 1024 * 1024)
    version_policy: Mapped[str] = mapped_column(String(40), nullable=False, default="IMMUTABLE_APPEND")
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    archive_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sensitivity_level: Mapped[str] = mapped_column(String(30), nullable=False, default="SENSITIVE")
    applicable_major_id: Mapped[str | None] = mapped_column(String(64), index=True)
    applicable_topic_type: Mapped[str | None] = mapped_column(String(64), index=True)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(String(500))


class GraduationStudentMaterial(PKMixin, TenantMixin, CommonMixin, Base):
    """同一学生、批次、材料代码唯一的逻辑材料项。"""

    __tablename__ = "t_gd_student_material"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "batch_id", "gd_student_id", "material_code",
            name="uk_gd_student_material_code",
        ),
        Index(
            "ix_gd_student_material_library",
            "tenant_id", "batch_id", "gd_student_id", "biz_stage", "is_deleted",
        ),
        Index(
            "ix_gd_student_material_status",
            "tenant_id", "batch_id", "business_status", "review_status", "archive_status",
        ),
        Index(
            "ix_gd_student_material_current",
            "tenant_id", "asset_id", "current_version_id",
        ),
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    gd_student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    topic_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    rule_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    material_code: Mapped[str] = mapped_column(String(100), nullable=False)
    material_name: Mapped[str] = mapped_column(String(200), nullable=False)
    biz_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_role: Mapped[str] = mapped_column(String(40), nullable=False, default="STUDENT")
    asset_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    current_version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    last_reviewed_version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    business_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="MISSING",
        comment="MISSING/UPLOADING/SCANNING/SUBMITTED/RETURNED/APPROVED/ARCHIVED/EXEMPTED",
    )
    review_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="NOT_SUBMITTED",
        comment="NOT_SUBMITTED/PENDING/RETURNED/APPROVED/NOT_REQUIRED",
    )
    required_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="REQUIRED",
        comment="REQUIRED/OPTIONAL/NOT_APPLICABLE/EXEMPTED",
    )
    archive_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="NOT_ARCHIVED",
        comment="NOT_ARCHIVED/ELIGIBLE/FROZEN/ARCHIVED/SUPERSEDED",
    )
    sensitivity_level: Mapped[str] = mapped_column(String(30), nullable=False, default="SENSITIVE")
    reject_reason: Mapped[str | None] = mapped_column(String(1000))
    reviewer_user_id: Mapped[int | None] = mapped_column(BigInteger)
    reviewer_name: Mapped[str | None] = mapped_column(String(100))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_revision: Mapped[int | None] = mapped_column(Integer)
    source_record_type: Mapped[str | None] = mapped_column(String(50), index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(80), index=True)
    migration_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NATIVE")


class GraduationMaterialBackfillCheckpoint(PKMixin, TenantMixin, CommonMixin, Base):
    """旧 attachments_json 分页回填、断点续跑和差异报告。"""

    __tablename__ = "t_gd_material_backfill_checkpoint"
    __table_args__ = (
        UniqueConstraint("tenant_id", "migration_key", name="uk_gd_material_backfill_key"),
        Index("ix_gd_material_backfill_status", "tenant_id", "status", "updated_at"),
    )

    migration_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING",
        comment="PENDING/RUNNING/COMPLETED/PARTIAL_FAILED/FAILED",
    )
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cursor_model: Mapped[str | None] = mapped_column(String(50))
    cursor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    page_size: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    scanned_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    converted_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    diff_report_json: Mapped[dict | None] = mapped_column(JSON)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class GraduationTemplateAssetPolicy(PKMixin, TenantMixin, CommonMixin, Base):
    """模板业务元数据与公共资产当前版本之间的稳定映射。"""

    __tablename__ = "t_gd_template_asset_policy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "template_id", name="uk_gd_template_asset_policy_template"),
        UniqueConstraint("tenant_id", "template_code", name="uk_gd_template_asset_policy_code"),
        Index(
            "ix_gd_template_asset_scope",
            "tenant_id", "batch_id", "college_id", "major_id", "status", "is_deleted",
        ),
    )

    template_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    template_code: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    college_id: Mapped[str | None] = mapped_column(String(64), index=True)
    major_id: Mapped[str | None] = mapped_column(String(64), index=True)
    asset_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    current_version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    variable_schema_json: Mapped[dict | None] = mapped_column(JSON)
    scope_json: Mapped[dict | None] = mapped_column(JSON)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
