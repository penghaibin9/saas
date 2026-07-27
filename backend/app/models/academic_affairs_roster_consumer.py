"""R9 选课、考勤、考务、成绩统一名单消费证据。

旧业务表继续保留自己的快照字段；本表只保存“某个业务对象当时冻结了哪一版正式名单”，
避免同时改动三张已经大量使用的表，并为后续统计/审计提供统一查询入口。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin


class AaRosterConsumerSnapshot(PKMixin, TenantMixin, CommonMixin, Base):
    """名单消费者快照。

    consumer_type: ATTENDANCE_SESSION / EXAM_COURSE / GRADE_TASK。
    同一消费者只允许一条 ACTIVE 快照；名单发生变化时旧消费者必须按业务规则重建/退回，不能静默换版。
    """

    __tablename__ = "t_aa_roster_consumer_snapshot"

    consumer_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    consumer_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
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
        UniqueConstraint("tenant_id", "consumer_type", "consumer_id", name="uk_aa_roster_consumer"),
    )
