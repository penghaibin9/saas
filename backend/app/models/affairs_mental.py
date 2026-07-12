"""13A-D 心理关注 · 转介与回访模型（转介→回访→升级/关闭 状态闭环）。

红线（权限总控 §10.2）：note 为涉密明细，非授权角色一律不返回；查看明文须原因 + SENSITIVE_VIEW 审计。
系统不做任何自动诊断：等级/事由均由心理老师人工登记，不含算法诊断结论。
危机升级复用风险中枢（source=MENTAL 的 t_affairs_risk_record），本表 risk_id 回链，不另建危机表。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin

# 关注等级（人工登记，非系统诊断）：一般关注 / 重点关注 / 危机
PSY_LEVELS = ("GENERAL", "FOCUS", "CRISIS")
# 转介状态机：转介 → 回访(持续) → 关闭；或 → 危机升级(接风险中枢)
PSY_REFERRAL_STATUS = ("REFERRED", "FOLLOWING", "ESCALATED", "CLOSED")


class PsyReferral(PKMixin, TenantMixin, CommonMixin, Base):
    """t_affairs_psy_referral 心理转介与回访。REFERRED/FOLLOWING/ESCALATED/CLOSED。"""
    __tablename__ = "t_affairs_psy_referral"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="FOCUS",
                                       comment="GENERAL/FOCUS/CRISIS，人工登记")
    channel: Mapped[str | None] = mapped_column(String(50), comment="转介去向：校医院/专业机构/家长/校内咨询")
    reason_summary: Mapped[str | None] = mapped_column(String(500), comment="转介事由摘要（非诊断结论）")
    note: Mapped[str | None] = mapped_column(String(1000), comment="涉密明细：非授权角色不返回")
    referrer: Mapped[str | None] = mapped_column(String(100), comment="转介登记人")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="REFERRED")
    last_follow_time: Mapped[datetime | None] = mapped_column(DateTime, comment="最近回访时间")
    closed_reason: Mapped[str | None] = mapped_column(String(500))
    risk_id: Mapped[int | None] = mapped_column(BigInteger, comment="危机升级时关联的风险中枢记录 id")
