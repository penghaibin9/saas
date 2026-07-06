"""13B-P2: 培养方案 3 表 + t_aa_status_change 加列(current_node/expire_date)

Revision ID: 0010_13b_p2_status_change_program
Revises: 0009_13b_p1_term_registration
Create Date: 2026-07-06

学籍异动多节点审批(current_node) + 休学到期日(expire_date, 真实业务补充)；培养方案编制骨架。
幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0010_13b_p2_status_change_program"
down_revision = "0009_13b_p1_term_registration"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
SC = "t_aa_status_change"
PROG = "t_aa_program"
PC = "t_aa_program_course"
PB = "t_aa_program_binding"


def _has(bind, table):
    return table in inspect(bind).get_table_names()


def _cols(bind, table):
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _pk_tenant(*extra):
    return [sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False), *extra]


def _common_cols():
    return [sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False)]


def _create(bind, table, cols, indexes=()):
    if _has(bind, table):
        return
    op.create_table(table, *cols)
    for ix in indexes:
        op.create_index(f"ix_{table}_{ix}", table, [ix])


def upgrade() -> None:
    bind = op.get_bind()
    # status_change 加列
    if _has(bind, SC):
        cols = _cols(bind, SC)
        for name, coltype in (("expire_date", sa.DateTime()), ("current_node", sa.String(length=50))):
            if name not in cols:
                op.add_column(SC, sa.Column(name, coltype, nullable=True))

    _create(bind, PROG, _pk_tenant(
        sa.Column("program_name", sa.String(length=200), nullable=False),
        sa.Column("major_id", sa.BigInteger(), nullable=True),
        sa.Column("grade_year", sa.String(length=20), nullable=True),
        sa.Column("total_credits", sa.Integer(), nullable=True),
        sa.Column("requirement_json", sa.String(length=2000), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("prev_version_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "major_id", "status"))

    _create(bind, PC, _pk_tenant(
        sa.Column("program_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("course_name", sa.String(length=200), nullable=True),
        sa.Column("open_term_no", sa.Integer(), nullable=True),
        sa.Column("module", sa.String(length=50), nullable=True),
        sa.Column("credit_snapshot", sa.Integer(), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "program_id"))

    _create(bind, PB, _pk_tenant(
        sa.Column("program_id", sa.BigInteger(), nullable=False),
        sa.Column("major_id", sa.BigInteger(), nullable=True),
        sa.Column("grade_year", sa.String(length=20), nullable=True),
        sa.Column("class_id", sa.BigInteger(), nullable=True),
        sa.Column("bound_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "program_id"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in (PB, PC, PROG):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
    if _has(bind, SC):
        cols = _cols(bind, SC)
        drop = [c for c in ("expire_date", "current_node") if c in cols]
        if drop:
            with op.batch_alter_table(SC) as batch:
                for c in drop:
                    batch.drop_column(c)
