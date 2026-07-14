"""13A 统一附件回链（违纪/送达/申诉/党团/减免贷款回执/家校 等业务材料）。

file 字节仍走 t_file_object（file_service 真实上传）；本表只登记 (biz_type,biz_id,file_id) 回链 +
上传人。查看/下载另走 require_permission(按 biz_type) + t_security_audit_log(SENSITIVE_EXPORT)，
列表接口只返回展示名+id，不返回路径/明文。
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AffairsAttachment(PKMixin, TenantMixin, CommonMixin, Base):
    """学工业务材料附件回链。biz_type 决定授权/审计口径，file_id 回链 t_file_object。"""
    __tablename__ = "t_affairs_attachment"

    biz_type: Mapped[str] = mapped_column(
        String(40), nullable=False,
        comment="DISCIPLINE/DISCIPLINE_APPEAL/LEAGUE/CLUB/FUNDING/REDUCTION/LOAN/HOME_SCHOOL")
    biz_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="业务记录 id")
    file_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="回链 t_file_object.id")
    file_name: Mapped[str | None] = mapped_column(String(255), comment="展示名（不含路径）")
    note: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (Index("ix_affairs_attachment_biz", "tenant_id", "biz_type", "biz_id"),)
