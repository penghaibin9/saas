"""13A 统一附件兼容台账。

阶段 5 后，文件字节、逻辑资产、版本和授权关系分别由 FileObject、FileAsset、
FileVersion、FileBinding 承载；本表只保留旧接口需要的附件编号与业务回链，并双写
公共引用，不能再作为文件授权真相源。
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AffairsAttachment(PKMixin, TenantMixin, CommonMixin, Base):
    """学工旧附件 DTO 的持久化 adapter。"""
    __tablename__ = "t_affairs_attachment"

    biz_type: Mapped[str] = mapped_column(
        String(40), nullable=False,
        comment="DISCIPLINE/DISCIPLINE_APPEAL/LEAGUE/CLUB/FUNDING/REDUCTION/LOAN/HOME_SCHOOL/MATERIAL_SUPPLEMENT",
    )
    biz_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="业务记录 id")
    file_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="兼容回链 t_file_object.id")
    file_name: Mapped[str | None] = mapped_column(String(255), comment="展示名（不含路径）")
    note: Mapped[str | None] = mapped_column(String(500))

    asset_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    file_version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    binding_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    sensitivity_level: Mapped[str] = mapped_column(
        String(30), nullable=False, default="SENSITIVE",
        comment="NORMAL/PERSONAL/SENSITIVE/HIGHLY_SENSITIVE",
    )
    source_channel: Mapped[str] = mapped_column(
        String(40), nullable=False, default="LEGACY_ADAPTER",
        comment="LEGACY_ADAPTER/MATERIAL_SUBMISSION/BACKFILL",
    )

    __table_args__ = (
        Index("ix_affairs_attachment_biz", "tenant_id", "biz_type", "biz_id"),
        Index(
            "ix_affairs_attachment_public_binding",
            "tenant_id", "biz_type", "biz_id", "file_version_id",
        ),
    )
