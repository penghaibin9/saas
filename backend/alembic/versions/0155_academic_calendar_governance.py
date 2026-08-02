"""SYS-12：学年学期治理投影、跨模块业务窗口与切换审计。

不新建第二套学期主表：``t_aa_term`` 仍是学期时间轴事实源，本迁移只增加系统管理侧的
治理投影（1:1 关联 term_id）、跨模块业务窗口和切换流水。

``uk_calendar_single_active`` 是本卡的核心安全约束：``active_key`` 仅在 ACTIVE 行写入
哨兵值 'ACTIVE'，其余状态为 NULL；MySQL 唯一索引允许多个 NULL，因此该索引等价于
"同租户同类型至多一个 ACTIVE"，并发激活由数据库兜底，不依赖应用层先查后写。

Revision ID: 0155_academic_calendar_governance
Revises: 0154_file_storage_quota_reservation
Create Date: 2026-08-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0155_academic_calendar_governance"
down_revision = "0154_file_storage_quota_reservation"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0155_academic_calendar_governance requires MySQL")


def upgrade() -> None:
    _require_mysql()
    insp = inspect(op.get_bind())

    if not insp.has_table("t_academic_calendar_governance"):
        op.create_table(
            "t_academic_calendar_governance",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("term_id", sa.BigInteger(), nullable=False),
            sa.Column("calendar_type", sa.String(32), nullable=False, server_default="ACADEMIC"),
            sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Shanghai"),
            sa.Column("governance_status", sa.String(24), nullable=False, server_default="DRAFT"),
            sa.Column("active_key", sa.String(16), nullable=True),
            sa.Column("scheduled_at", sa.DateTime()),
            sa.Column("activated_at", sa.DateTime()),
            sa.Column("closing_started_at", sa.DateTime()),
            sa.Column("closed_at", sa.DateTime()),
            sa.Column("archived_at", sa.DateTime()),
            sa.Column("last_transition_reason", sa.String(1000)),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_academic_calendar_governance_tenant_id", "t_academic_calendar_governance", ["tenant_id"])
        op.create_index("ix_t_academic_calendar_governance_term_id", "t_academic_calendar_governance", ["term_id"])
        op.create_index(
            "ix_t_academic_calendar_governance_governance_status",
            "t_academic_calendar_governance",
            ["governance_status"],
        )
        op.create_unique_constraint(
            "uk_calendar_governance_term", "t_academic_calendar_governance", ["tenant_id", "term_id"]
        )
        # 核心并发安全约束，见模块 docstring
        op.create_unique_constraint(
            "uk_calendar_single_active",
            "t_academic_calendar_governance",
            ["tenant_id", "calendar_type", "active_key"],
        )
        op.create_index(
            "idx_calendar_governance_status",
            "t_academic_calendar_governance",
            ["tenant_id", "governance_status", "scheduled_at"],
        )

    if not insp.has_table("t_calendar_window"):
        op.create_table(
            "t_calendar_window",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("term_id", sa.BigInteger(), nullable=False),
            sa.Column("window_type", sa.String(32), nullable=False),
            sa.Column("module_code", sa.String(64), nullable=False),
            sa.Column("start_at", sa.DateTime(), nullable=False),
            sa.Column("end_at", sa.DateTime(), nullable=False),
            sa.Column("config_json", sa.JSON()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_calendar_window_tenant_id", "t_calendar_window", ["tenant_id"])
        op.create_index("ix_t_calendar_window_term_id", "t_calendar_window", ["term_id"])
        op.create_unique_constraint(
            "uk_calendar_window", "t_calendar_window", ["tenant_id", "term_id", "window_type", "module_code"]
        )
        op.create_index(
            "idx_calendar_window_range", "t_calendar_window", ["tenant_id", "module_code", "start_at", "end_at"]
        )

    if not insp.has_table("t_calendar_transition_event"):
        op.create_table(
            "t_calendar_transition_event",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("term_id", sa.BigInteger(), nullable=False),
            sa.Column("from_status", sa.String(24)),
            sa.Column("to_status", sa.String(24), nullable=False),
            sa.Column("actor_user_id", sa.BigInteger()),
            sa.Column("reason", sa.String(1000)),
            sa.Column("blockers_json", sa.JSON()),
            sa.Column("trace_id", sa.String(64)),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger()),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_calendar_transition_event_tenant_id", "t_calendar_transition_event", ["tenant_id"])
        op.create_index("ix_t_calendar_transition_event_term_id", "t_calendar_transition_event", ["term_id"])
        op.create_index("ix_t_calendar_transition_event_trace_id", "t_calendar_transition_event", ["trace_id"])
        op.create_index(
            "idx_calendar_transition_term_time", "t_calendar_transition_event", ["tenant_id", "term_id", "created_at"]
        )

    # 回填：把教务已设为当前学期的行投影成 ACTIVE，保证升级后 resolver 立即可用，
    # 不出现"升级完没有任何当前学期"的空窗。
    #
    # 注意 t_aa_term.is_current 历史上没有唯一约束，同一租户可能已存在多条 is_current=1
    # 的脏数据。INSERT...SELECT 的 NOT EXISTS 看不到本语句正在插入的行，若直接按
    # is_current 过滤会一次插入多条 ACTIVE 并撞 uk_calendar_single_active 导致升级失败。
    # 因此这里用 MIN(id) 对每个租户去重，保证每租户至多回填一条；脏数据留给页面上的
    # 一致性检查暴露，迁移不静默改教务事实源。
    op.execute(
        """
        INSERT INTO t_academic_calendar_governance
            (tenant_id, term_id, calendar_type, timezone, governance_status, active_key,
             activated_at, last_transition_reason, created_at, updated_at, is_deleted, version)
        SELECT t.tenant_id, t.id, 'ACADEMIC', 'Asia/Shanghai', 'ACTIVE', 'ACTIVE',
               UTC_TIMESTAMP(), '0155 回填：沿用教务已设当前学期', UTC_TIMESTAMP(), UTC_TIMESTAMP(), 0, 0
        FROM t_aa_term t
        JOIN (
            SELECT tenant_id, MIN(id) AS keep_id
            FROM t_aa_term
            WHERE is_current = 1 AND is_deleted = 0
            GROUP BY tenant_id
        ) pick ON pick.tenant_id = t.tenant_id AND pick.keep_id = t.id
        WHERE NOT EXISTS (
              SELECT 1 FROM t_academic_calendar_governance g
              WHERE g.tenant_id = t.tenant_id
                AND (g.term_id = t.id
                     OR (g.calendar_type = 'ACADEMIC' AND g.active_key = 'ACTIVE'))
          )
        """
    )


def downgrade() -> None:
    # 只回退本迁移新增的治理投影，不触碰 t_aa_term 等教务事实源。
    for table in ("t_calendar_transition_event", "t_calendar_window", "t_academic_calendar_governance"):
        if inspect(op.get_bind()).has_table(table):
            op.drop_table(table)
