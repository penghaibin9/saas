"""GPA 绩点换算策略：租户级、可版本化，历史成绩绩点冻结不随新版本重算（P1 GPA）。

原实现 `_course_point(score)` 是硬编码公式（60→1.0，100→5.0），全租户统一、无法配置，且每次
`_refresh_aggregates` 都用"当前"公式重算全部历史成绩——学校一旦调整绩点口径，已毕业学生的
历史 GPA 会被静默改写。本策略表把绩点换算变成可发布版本的租户配置，配合 `t_acad_grade` 上
冻结的 `gpa_point`/`gpa_policy_code`/`gpa_policy_version` 三列，保证每条成绩记录第一次计入
GPA 时用的是哪个策略版本，此后永远沿用那个版本的换算结果，不随后续策略升级改变。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AaGpaPointPolicy(PKMixin, TenantMixin, CommonMixin, Base):
    """租户级、按版本发布的绩点换算策略。

    与 AaEffectiveGradePolicy 同一套版本化数据库合同：
    - ``UNIQUE(tenant_id, policy_code, policy_version)``：同一策略代码可以发布 V1/V2/V3
      版本链，已冻结绩点的历史成绩继续引用发布时的那个版本，不因后续版本升级而改变；
    - ``UNIQUE(tenant_id, active_scope_key)``：``active_scope_key`` 只在 ACTIVE 行非空
      （目前不按学期区分范围，固定为 "BASE"），非 ACTIVE 行置 NULL——同一租户同时只能有
      一条 ACTIVE 策略由数据库唯一索引兜底，而不是先查后写。
    """

    __tablename__ = "t_aa_gpa_point_policy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "policy_code", "policy_version", name="uk_aa_gpa_policy_ver"),
        UniqueConstraint("tenant_id", "active_scope_key", name="uk_aa_gpa_policy_scope"),
        Index("ix_aa_gpa_policy_active", "tenant_id", "status"),
    )

    policy_code: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active_scope_key: Mapped[str | None] = mapped_column(
        String(40), comment="ACTIVE 行固定为 'BASE'；非 ACTIVE 行为 NULL")
    scale_type: Mapped[str] = mapped_column(String(20), nullable=False, default="LINEAR", comment="LINEAR/BANDS")
    linear_fail_score: Mapped[int | None] = mapped_column(Integer, comment="LINEAR：低于此分绩点为0")
    linear_anchor_score: Mapped[int | None] = mapped_column(Integer, comment="LINEAR：绩点=(分-锚点)/除数")
    linear_divisor: Mapped[int | None] = mapped_column(Integer)
    bands_json: Mapped[str | None] = mapped_column(
        Text, comment='BANDS：[{"minScore":90,"maxScore":100,"point":4.0}, ...]，按分数区间取绩点')
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", comment="DRAFT/ACTIVE/SUPERSEDED")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(String(200))
