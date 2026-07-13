"""13A-D 学生活动 波次3 · 党团建设（07 卡）模型。

党/团员发展阶段台账：t_affairs_league_dev（一生一条，记当前阶段）+ t_affairs_league_dev_stage
（阶段流转 append-only，材料 file_id 脱敏、不落明文）。阶段码遵循公开《中国共产党发展党员工作
细则》通用五阶段；各校时限/审批权限/政治面貌回写属校本制度，不在模型内写死（见历史欠账）。
敏感：材料仅存 file_id，列表接口不返回明文；查看/下载另走授权+审计（后续接入）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin

# 党员发展五阶段（公开国标通用码）；团员发展用 LEAGUE_* 前缀简化
PARTY_STAGES = ("APPLICANT", "ACTIVIST", "DEVELOPMENT_TARGET", "PROBATIONARY", "FULL_MEMBER")


class AffairsLeagueDev(PKMixin, TenantMixin, CommonMixin, Base):
    """党团发展台账（一生一条）。dev_type PARTY党员/LEAGUE团员；current_stage 当前阶段；
    status ONGOING发展中/COMPLETED已转正/TERMINATED终止。"""
    __tablename__ = "t_affairs_league_dev"

    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    dev_type: Mapped[str] = mapped_column(String(30), nullable=False, default="PARTY",
                                          comment="PARTY党员发展/LEAGUE团员发展")
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="APPLICANT",
                                               comment="当前阶段码（五阶段）")
    branch_name: Mapped[str | None] = mapped_column(String(200), comment="党支部/团支部")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ONGOING", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (UniqueConstraint("tenant_id", "student_id", "dev_type",
                                       name="uk_league_dev_student_type"),)


class AffairsLeagueDevStage(PKMixin, TenantMixin, CommonMixin, Base):
    """阶段流转记录（append-only）。material_file_id 脱敏仅存引用；不落材料明文。"""
    __tablename__ = "t_affairs_league_dev_stage"

    dev_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    from_stage: Mapped[str | None] = mapped_column(String(50))
    to_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    material_file_id: Mapped[int | None] = mapped_column(BigInteger, comment="阶段材料附件(脱敏,仅引用)")
    operator: Mapped[str | None] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(String(1000))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
