"""13A-D 心理关注：t_affairs_psy_referral 心理转介与回访（转介→回访→升级/关闭 闭环）

Revision ID: 0044_13a_psy_referral
Revises: 0043_gd_final_attachments
Create Date: 2026-07-12

说明：心理转介/回访状态闭环表。note 涉密明细（应用层遮蔽 + SENSITIVE_VIEW 审计）；危机升级复用
风险中枢（source=MENTAL 的 t_affairs_risk_record），本表 risk_id 回链，不另建危机表。
幂等：表已存在则跳过。注：本仓库存在实习域未提交迁移(0035-0041)，完整 upgrade 需其先落库；
测试用 metadata.create_all 不受影响。回滚：downgrade 直接 drop 本表。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0044_13a_psy_referral"
down_revision = "0043_gd_final_attachments"
branch_labels = None
depends_on = None

TABLE = "t_affairs_psy_referral"


def _has_table(bind, table) -> bool:
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, TABLE):
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("level", sa.String(length=20), nullable=False, server_default="FOCUS"),
        sa.Column("channel", sa.String(length=50)),
        sa.Column("reason_summary", sa.String(length=500)),
        sa.Column("note", sa.String(length=1000)),
        sa.Column("referrer", sa.String(length=100)),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="REFERRED"),
        sa.Column("last_follow_time", sa.DateTime()),
        sa.Column("closed_reason", sa.String(length=500)),
        sa.Column("risk_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_psy_referral_tenant_student", TABLE, ["tenant_id", "student_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, TABLE):
        op.drop_table(TABLE)
