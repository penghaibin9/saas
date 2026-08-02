"""SYS-12 学年学期治理投影与业务日历窗口（V6 控制面）。

设计来源
────────
- ``existing_code``：教务中心的 ``t_aa_term`` / ``t_aa_calendar_event`` 已是学校学期时间轴的
  事实源，且被考勤、教学任务、归档等大量教务链路按 ``term_id`` 依赖。本模块**不复制、不替代**
  这些表，只在系统管理侧建立治理投影，避免出现第二个"当前学期"。
- ``project_rule``：系统管理只做治理与统一读取入口，业务数据仍由业务 owner 写入。
- V6 SYS-12 卡：状态机 DRAFT→VALIDATED→SCHEDULED→ACTIVE→CLOSING→CLOSED→ARCHIVED；
  同租户同类型仅一个 ACTIVE；公共读取只允许 CalendarResolver。

与 ``t_aa_term`` 的关系
──────────────────────
``t_aa_term.status``（DRAFT/PUBLISHED/FROZEN/ARCHIVED）和 ``is_current`` 继续由教务维护，
是教务自己的发布状态；本表的 ``governance_status`` 是**全校统一切换**的治理状态，二者通过
``term_id`` 一一对应。教务侧发布与否不直接等于全校已切换——这正是 SYS-12 要收口的问题。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, BigInteger, DateTime, Index, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (AuditTimeMixin, Base, CommonMixin, PKMixin,
                             TenantMixin)

# 治理状态机（唯一权威定义，service 层从此处导入，禁止各处硬编码字符串）
CALENDAR_STATUS_DRAFT = "DRAFT"
CALENDAR_STATUS_VALIDATED = "VALIDATED"
CALENDAR_STATUS_SCHEDULED = "SCHEDULED"
CALENDAR_STATUS_ACTIVE = "ACTIVE"
CALENDAR_STATUS_CLOSING = "CLOSING"
CALENDAR_STATUS_CLOSED = "CLOSED"
CALENDAR_STATUS_ARCHIVED = "ARCHIVED"

CALENDAR_STATUSES = (
    CALENDAR_STATUS_DRAFT,
    CALENDAR_STATUS_VALIDATED,
    CALENDAR_STATUS_SCHEDULED,
    CALENDAR_STATUS_ACTIVE,
    CALENDAR_STATUS_CLOSING,
    CALENDAR_STATUS_CLOSED,
    CALENDAR_STATUS_ARCHIVED,
)

# 只有处于 ACTIVE 的行才写入该哨兵值；其余状态写 NULL。
# MySQL 唯一索引允许多个 NULL，因此 (tenant_id, calendar_type, active_key) 唯一
# 等价于"同租户同类型至多一个 ACTIVE"，并且该约束由数据库强制，并发激活也无法穿透。
ACTIVE_SENTINEL = "ACTIVE"

CALENDAR_TYPE_ACADEMIC = "ACADEMIC"


class AcademicCalendarGovernance(PKMixin, TenantMixin, CommonMixin, Base):
    """学期治理投影：一条记录对应一个 ``t_aa_term``。"""

    __tablename__ = "t_academic_calendar_governance"

    term_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="关联 t_aa_term.id")
    calendar_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CALENDAR_TYPE_ACADEMIC, comment="日历类型，预留多类型日历"
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Shanghai", comment="学校时区，定时激活按此换算"
    )
    governance_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=CALENDAR_STATUS_DRAFT, index=True, comment="全校统一切换状态"
    )
    active_key: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="ACTIVE 哨兵；配合唯一索引保证同类型只有一个 ACTIVE"
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, comment="排期激活时间（UTC）")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    closing_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_transition_reason: Mapped[str | None] = mapped_column(String(1000))

    __table_args__ = (
        UniqueConstraint("tenant_id", "term_id", name="uk_calendar_governance_term"),
        UniqueConstraint("tenant_id", "calendar_type", "active_key", name="uk_calendar_single_active"),
        Index("idx_calendar_governance_status", "tenant_id", "governance_status", "scheduled_at"),
    )


class CalendarWindow(PKMixin, TenantMixin, CommonMixin, Base):
    """业务日历窗口：考试/迎新/实习/毕设/就业等按模块登记的时间窗。

    与教务 ``t_aa_calendar_event`` 的区别：后者是教务自身的校历事件（含调休），本表是
    **跨模块**的业务窗口，带 ``module_code``，供各模块 resolver 判断"现在能不能做某事"。
    """

    __tablename__ = "t_calendar_window"

    term_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    window_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="EXAM/ORIENTATION/INTERNSHIP/GRADUATION/EMPLOYMENT 等")
    module_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="消费模块，对应 CalendarConsumer 注册表")
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    config_json: Mapped[dict | None] = mapped_column(JSON, comment="窗口附加配置，须有 schema 校验，不得当垃圾桶")

    __table_args__ = (
        UniqueConstraint("tenant_id", "term_id", "window_type", "module_code", name="uk_calendar_window"),
        Index("idx_calendar_window_range", "tenant_id", "module_code", "start_at", "end_at"),
    )


class CalendarTransitionEvent(PKMixin, TenantMixin, AuditTimeMixin, Base):
    """学期切换审计流水（append-only，按基类约定不带 is_deleted/version）。"""

    __tablename__ = "t_calendar_transition_event"

    term_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(String(1000))
    blockers_json: Mapped[dict | None] = mapped_column(JSON, comment="阻断项快照，便于事后解释为何拒绝")
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)

    __table_args__ = (
        Index("idx_calendar_transition_term_time", "tenant_id", "term_id", "created_at"),
    )
