"""课表管理 Tier1 续工（班级课表/教师课表/教室课表/课表发布/课表导出）：

新建 t_aa_schedule_publish（课表发布记录：设计原列此表，此前仅落 batch.status/publish_at，
本次补齐可追溯的发布/作废流水，供「课表发布」三级页展示历史与通知回执）。

Revision ID: aa_schedule_tier1_r2
Revises: aa_jxrw_tier1_r1
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_schedule_tier1_r2"
down_revision = "aa_bkcx_tier1_r2"
branch_labels = None
depends_on = None

_COMMON = [
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("created_by", sa.BigInteger()),
    sa.Column("updated_by", sa.BigInteger()),
    sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
]


def _pk_tenant():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
    ]


def _has_table(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "t_aa_schedule_publish"):
        op.create_table(
            "t_aa_schedule_publish", *_pk_tenant(),
            sa.Column("batch_id", sa.BigInteger(), nullable=False, comment="→ t_aa_schedule_batch"),
            sa.Column("term_id", sa.BigInteger()),
            sa.Column("action", sa.String(30), nullable=False, server_default="PUBLISH",
                     comment="PUBLISH/VOID_REISSUE"),
            sa.Column("operator_name", sa.String(100)),
            sa.Column("notified_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("note", sa.String(500)),
            *_COMMON)
        op.create_index("ix_aa_sched_pub_batch", "t_aa_schedule_publish", ["tenant_id", "batch_id"])
        op.create_index("ix_aa_sched_pub_term", "t_aa_schedule_publish", ["tenant_id", "term_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "t_aa_schedule_publish"):
        op.drop_table("t_aa_schedule_publish")
