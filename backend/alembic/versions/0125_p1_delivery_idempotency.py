"""P1：投递作业唯一约束 + 幂等持久化表。

Revision ID: 0125_p1_delivery_idempotency
Revises: 0124_merge_aa_bugfix_and_internship

兼容说明：0001 历史迁移会导入运行时当前 metadata，空库升级时 t_idempotency_record
可能已提前创建，故先查表再执行原始 DDL（同 0103/0104/0105 约定）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0125_p1_delivery_idempotency"
down_revision = "0124_merge_aa_bugfix_and_internship"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _unique_constraint_names(table: str) -> set:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return set()
    return {uc["name"] for uc in sa.inspect(bind).get_unique_constraints(table)}


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        op.execute("""
            DELETE j1 FROM t_message_delivery_job j1
            INNER JOIN t_message_delivery_job j2
              ON j1.tenant_id = j2.tenant_id
             AND j1.campaign_id = j2.campaign_id
             AND j1.cursor_start = j2.cursor_start
             AND j1.id > j2.id
        """)
    else:
        # SQLite / 其他：用子查询删重复
        op.execute("""
            DELETE FROM t_message_delivery_job
            WHERE id NOT IN (
              SELECT MIN(id) FROM t_message_delivery_job
              GROUP BY tenant_id, campaign_id, cursor_start
            )
        """)

    if "uk_msg_delivery_job_campaign_cursor" not in _unique_constraint_names("t_message_delivery_job"):
        op.create_unique_constraint(
            "uk_msg_delivery_job_campaign_cursor",
            "t_message_delivery_job",
            ["tenant_id", "campaign_id", "cursor_start"],
        )

    if not _has_table("t_idempotency_record"):
        op.create_table(
            "t_idempotency_record",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.String(64), nullable=False),
            sa.Column("operation", sa.String(100), nullable=False),
            sa.Column("key_hash", sa.String(64), nullable=False),
            sa.Column("fingerprint", sa.String(64), nullable=False),
            sa.Column("state", sa.String(32), nullable=False, server_default="PROCESSING"),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("tenant_id", "user_id", "operation", "key_hash",
                                name="uk_idempotency_tenant_user_op_key"),
        )
        op.create_index("ix_idempotency_expires", "t_idempotency_record", ["expires_at"])
        op.create_index("ix_idempotency_tenant_id", "t_idempotency_record", ["tenant_id"])


def downgrade() -> None:
    if _has_table("t_idempotency_record"):
        op.drop_index("ix_idempotency_tenant_id", table_name="t_idempotency_record")
        op.drop_index("ix_idempotency_expires", table_name="t_idempotency_record")
        op.drop_table("t_idempotency_record")
    op.drop_constraint("uk_msg_delivery_job_campaign_cursor",
                       "t_message_delivery_job", type_="unique")
