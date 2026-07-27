"""R9 选课、考勤、考务、成绩统一名单消费证据。

旧业务表继续保留自己的快照字段；本表保存“某个业务对象每次提交时冻结了哪一版正式名单”，
既支持当前名单一致性校验，也完整保留退回重提后的历史证据。
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AaRosterConsumerSnapshot(PKMixin, TenantMixin, CommonMixin, Base):
    """名单消费者快照。

    consumer_type: ATTENDANCE_SESSION / EXAM_COURSE / GRADE_TASK。
    同一消费者可保留多版历史；同一时刻只应存在一条 ACTIVE 快照，旧版标记 SUPERSEDED。
    """

    __tablename__ = "t_aa_roster_consumer_snapshot"

    consumer_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    consumer_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    teaching_task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teaching_class_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    roster_version_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    roster_version_no: Mapped[int | None] = mapped_column(Integer)
    roster_source: Mapped[str] = mapped_column(String(40), nullable=False)
    roster_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    student_ids_json: Mapped[str] = mapped_column(Text, nullable=False, comment="排序去重后的学生ID数组，仅作审计证据")
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    captured_by: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "consumer_type", "consumer_id", "snapshot_version",
            name="uk_aa_roster_consumer_version",
        ),
    )


# 确保 Base.metadata.create_all 同时注册 R10 兼容扩展表。
from app.models.academic_affairs_r10 import (  # noqa: E402,F401
    AaGradeComponentScore,
    AaGradeSchemeSnapshot,
    AaStatsSnapshot,
)
