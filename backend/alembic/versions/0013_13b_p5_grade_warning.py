"""13B-P5: 成绩录入 grade_task/record 2 表 + t_acad_warning 加 source_code/rule_code

Revision ID: 0013_13b_p5_grade_warning
Revises: 0012_13b_p4_schedule
Create Date: 2026-07-06

成绩平时+期末按比例合成，发布投影 t_acad_grade(复用学业过程域，不新建成绩表)；
预警规则引擎复用 t_acad_warning 加 2 列(source_code/rule_code)。幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0013_13b_p5_grade_warning"
down_revision = "0012_13b_p4_schedule"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
GT = "t_aa_grade_task"
GR = "t_aa_grade_record"
WARN = "t_acad_warning"


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

    # t_acad_warning 加列
    if _has(bind, WARN):
        cols = _cols(bind, WARN)
        for name in ("source_code", "rule_code"):
            if name not in cols:
                op.add_column(WARN, sa.Column(name, sa.String(length=50), nullable=True))
        if "source_code" in _cols(bind, WARN):
            idx = {i["name"] for i in inspect(bind).get_indexes(WARN)}
            if "ix_t_acad_warning_source_code" not in idx:
                op.create_index("ix_t_acad_warning_source_code", WARN, ["source_code"])

    _create(bind, GT, _pk_tenant(
        sa.Column("teaching_task_id", sa.BigInteger(), nullable=True),
        sa.Column("term_id", sa.BigInteger(), nullable=True),
        sa.Column("term_code", sa.String(length=50), nullable=True),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("course_name", sa.String(length=200), nullable=True),
        sa.Column("class_id", sa.BigInteger(), nullable=True),
        sa.Column("teacher_key", sa.String(length=100), nullable=True),
        sa.Column("credit", sa.Numeric(4, 1), nullable=True),
        sa.Column("usual_ratio", sa.Integer(), nullable=False),
        sa.Column("final_ratio", sa.Integer(), nullable=False),
        sa.Column("pass_line", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("publish_at", sa.DateTime(), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "teaching_task_id", "term_id", "class_id", "status"))

    _create(bind, GR, _pk_tenant(
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("usual_score", sa.Integer(), nullable=True),
        sa.Column("final_score", sa.Integer(), nullable=True),
        sa.Column("total_score", sa.Integer(), nullable=True),
        sa.Column("pass_status", sa.String(length=50), nullable=True),
        sa.Column("acad_grade_id", sa.BigInteger(), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "task_id", "student_id"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in (GR, GT):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
    if _has(bind, WARN):
        cols = _cols(bind, WARN)
        for idx in inspect(bind).get_indexes(WARN):
            if "source_code" in (idx.get("column_names") or []):
                op.drop_index(idx["name"], table_name=WARN)
        with op.batch_alter_table(WARN) as batch:
            for c in ("source_code", "rule_code"):
                if c in cols:
                    batch.drop_column(c)
