"""13B-P6: 毕业预审 batch + result 2 表

Revision ID: 0014_13b_p6_graduation_audit
Revises: 0013_13b_p5_grade_warning
Create Date: 2026-07-06

七项跨域供数三态判定(item_results_json 收敛不建 item 表)；终审经 change_student_status 写主档。
唯一键(tenant,batch,student)。幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0014_13b_p6_graduation_audit"
down_revision = "0013_13b_p5_grade_warning"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
GB = "t_aa_graduation_audit_batch"
GRR = "t_aa_graduation_audit_result"


def _has(bind, table):
    return table in inspect(bind).get_table_names()


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


def _create(bind, table, cols, indexes=(), uniques=()):
    if _has(bind, table):
        return
    op.create_table(table, *cols)
    for ix in indexes:
        op.create_index(f"ix_{table}_{ix}", table, [ix])
    for name, ucols in uniques:
        op.create_unique_constraint(name, table, list(ucols))


def upgrade() -> None:
    bind = op.get_bind()

    _create(bind, GB, _pk_tenant(
        sa.Column("batch_name", sa.String(length=200), nullable=False),
        sa.Column("grade_year", sa.String(length=20), nullable=True),
        sa.Column("major_id", sa.BigInteger(), nullable=True),
        sa.Column("scope_json", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("generate_at", sa.DateTime(), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "grade_year", "major_id", "status"))

    _create(bind, GRR, _pk_tenant(
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("item_results_json", sa.String(length=4000), nullable=True),
        sa.Column("overall", sa.String(length=50), nullable=True),
        sa.Column("conclusion", sa.String(length=50), nullable=True),
        sa.Column("rerun_count", sa.Integer(), nullable=False),
        sa.Column("review_note", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "batch_id", "student_id", "status"),
       uniques=(("uk_aa_grad_audit", ("tenant_id", "batch_id", "student_id")),))


def downgrade() -> None:
    bind = op.get_bind()
    for table in (GRR, GB):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
