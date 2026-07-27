"""有效成绩策略快照模型。"""
from __future__ import annotations

from sqlalchemy import BigInteger, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AaEffectiveGradePolicySnapshot(PKMixin, TenantMixin, CommonMixin, Base):
    """每次正式成绩写入/更正时冻结采用的有效成绩规则和课程身份。

    append-only；event_key保证网络重试幂等。历史无courseId成绩不自动猜测，只记录LEGACY_NAME_KEY欠账。
    """

    __tablename__ = "t_aa_effective_grade_policy_snapshot"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_key", name="uk_aa_effective_grade_policy_event"),
        Index("ix_aa_effective_grade_policy_grade", "tenant_id", "academic_grade_id"),
        Index("ix_aa_effective_grade_policy_course", "tenant_id", "course_id", "attempt_no"),
        Index("ix_aa_effective_grade_policy_source", "tenant_id", "source_biz_type", "source_biz_id"),
    )

    academic_grade_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    event_key: Mapped[str] = mapped_column(String(160), nullable=False, comment="幂等事件键")
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="PUBLISH/MAKEUP/CLEARANCE/RECHECK/CHANGE")
    source_biz_type: Mapped[str | None] = mapped_column(String(50))
    source_biz_id: Mapped[int | None] = mapped_column(BigInteger)

    policy_code: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    policy_json: Mapped[str] = mapped_column(Text, nullable=False)
    policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    identity_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="COURSE_ID/COURSE_CODE/LEGACY_NAME_KEY")
    identity_key: Mapped[str] = mapped_column(String(300), nullable=False)
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    course_code: Mapped[str | None] = mapped_column(String(50))
    course_version: Mapped[int | None] = mapped_column(Integer)
    attempt_no: Mapped[int | None] = mapped_column(Integer)
    grade_source: Mapped[str | None] = mapped_column(String(30))
    decision_json: Mapped[str] = mapped_column(Text, nullable=False, comment="本次成绩事实与有效性判断快照")
