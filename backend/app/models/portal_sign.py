"""学生 PC 门户 · 电子签署记录（可插拔 provider）。

默认 provider=reliable_log：可靠留痕 = 签署内容 SHA-256 哈希快照 + 时间戳 + 签署人 + 审计，
事后可验证内容未被篡改（比对 content_hash）。法律级 provider（法大大/e签宝/CA + 实名 + 可信
时间戳）需甲方采购持牌平台密钥后接入，本表结构预留 provider 字段，不改结构即可升级。
append-only 语义（不改不删），故不继承 CommonMixin。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TenantMixin


class PortalSignRecord(PKMixin, TenantMixin, Base):
    """t_portal_sign_record：学生电子签署留痕（行级隔离 tenant_id）。"""
    __tablename__ = "t_portal_sign_record"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="签署学生")
    biz_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                          comment="业务类型：GRADUATION_TASKBOOK/INTERNSHIP_AGREEMENT/FUNDING_COMMIT...")
    biz_id: Mapped[str | None] = mapped_column(String(64), index=True, comment="业务对象ID")
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, comment="签署内容 SHA-256（防篡改快照）")
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="reliable_log",
                                          comment="reliable_log(默认可靠留痕)/法律级provider(待采购)")
    signer_name: Mapped[str | None] = mapped_column(String(100), comment="签署人姓名（快照）")
    signed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow,
                                                comment="签署时间戳")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
