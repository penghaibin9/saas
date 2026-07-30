"""毕业设计材料中心：批次材料规则与规则项。

文件字节与版本仍由公共 FileAsset/FileVersion/FileBinding 承担；本文件只描述
毕业设计批次要求哪些材料、允许哪些格式和审核规则，禁止复制公共文件模型。
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class GraduationMaterialRule(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_material_rule"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "batch_id", "rule_code", "rule_version",
            name="uk_gd_material_rule_version",
        ),
        Index(
            "ix_gd_material_rule_active",
            "tenant_id", "batch_id", "status", "is_deleted",
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
    applicable_scope_json: Mapped[dict | None] = mapped_column(JSON)
    required_items_json: Mapped[list | None] = mapped_column(JSON)
    allowed_ext_json: Mapped[list | None] = mapped_column(JSON)
    max_files: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=50 * 1024 * 1024)
    remark: Mapped[str | None] = mapped_column(String(500))


class GraduationMaterialItem(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_gd_material_item"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "rule_id", "material_code",
            name="uk_gd_material_item_code",
        ),
        Index(
            "ix_gd_material_item_stage",
            "tenant_id", "rule_id", "biz_stage", "sort_no", "is_deleted",
        ),
    )

    rule_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    biz_stage: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="PROPOSAL/FINAL_DRAFT/FINAL_APPROVED/TEMPLATE",
    )
    material_code: Mapped[str] = mapped_column(String(100), nullable=False)
    material_name: Mapped[str] = mapped_column(String(200), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    allowed_ext_json: Mapped[list | None] = mapped_column(JSON)
    max_files: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=50 * 1024 * 1024)
    description: Mapped[str | None] = mapped_column(String(500))
