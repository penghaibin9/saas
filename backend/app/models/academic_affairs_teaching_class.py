"""V2-02 独立教学班及名单版本模型。

兼容策略：AaTeachingTask 继续保留历史教学班文本、教师和预计人数字段；本文件建立正式教学班、
教师关系、名单版本和成员事实，迁移期由服务层双写，不直接删除旧字段。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BigIntPK, CommonMixin, PKMixin, TenantMixin


class AaTeachingClass(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_aa_teaching_class"
    __table_args__ = (
        UniqueConstraint("tenant_id", "teaching_task_id", name="uk_aa_tc_task"),
        UniqueConstraint("tenant_id", "term_id", "class_code", name="uk_aa_tc_term_code"),
        Index("ix_aa_tc_term_course", "tenant_id", "term_id", "course_id"),
        Index("ix_aa_tc_status", "tenant_id", "status"),
    )

    teaching_task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="兼容来源教学任务ID")
    term_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    class_code: Mapped[str] = mapped_column(String(80), nullable=False)
    class_name: Mapped[str] = mapped_column(String(160), nullable=False)
    class_type: Mapped[str] = mapped_column(String(24), nullable=False, default="ADMIN", comment="ADMIN/SELECTION/MERGED/RETAKE/LAYERED")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="TEACHING_TASK")
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_roster_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    current_roster_version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    roster_status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT", comment="DRAFT/LOCKED")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE", comment="ACTIVE/ARCHIVED")
    source_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class AaTeachingClassTeacher(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_aa_teaching_class_teacher"
    __table_args__ = (
        UniqueConstraint("tenant_id", "teaching_class_id", "teacher_key", "role_type", name="uk_aa_tc_teacher"),
        Index("ix_aa_tc_teacher_key", "tenant_id", "teacher_key", "status"),
    )

    teaching_class_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    teacher_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    teacher_key: Mapped[str] = mapped_column(String(100), nullable=False)
    teacher_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role_type: Mapped[str] = mapped_column(String(24), nullable=False, default="PRIMARY", comment="PRIMARY/CO_TEACHER")
    start_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")


class AaTeachingClassRosterVersion(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_aa_teaching_class_roster_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "teaching_class_id", "version_no", name="uk_aa_tc_roster_version"),
        UniqueConstraint("tenant_id", "teaching_class_id", "roster_hash", name="uk_aa_tc_roster_hash"),
        Index("ix_aa_tc_roster_status", "tenant_id", "teaching_class_id", "status"),
    )

    teaching_class_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="ADMIN_CLASS/SELECTION_LOCK/MANUAL/RETAKE")
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    roster_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="LOCKED", comment="LOCKED/SUPERSEDED")
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)


class AaTeachingClassMember(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_aa_teaching_class_member"
    __table_args__ = (
        UniqueConstraint("tenant_id", "roster_version_id", "student_id", name="uk_aa_tc_member_version_student"),
        Index("ix_aa_tc_member_student", "tenant_id", "student_id", "status"),
        Index("ix_aa_tc_member_class", "tenant_id", "teaching_class_id", "roster_version_id"),
    )

    teaching_class_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    roster_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
