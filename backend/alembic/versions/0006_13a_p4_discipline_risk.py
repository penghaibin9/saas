"""13A-P4: 处分 case/remove_apply + 风险 record/handle 4 表 + t_cs_discipline 加 source_case_id

Revision ID: 0006_13a_p4_discipline_risk
Revises: 0005_13a_p3_aid_funding
Create Date: 2026-07-06

处分投影：EFFECTIVE 事务内写 t_cs_discipline 一行（应用层），source_case_id 回链本域 case。
风险：(tenant_id, source, source_ref_id) 唯一防重复建单。幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0006_13a_p4_discipline_risk"
down_revision = "0005_13a_p3_aid_funding"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
DISC = "t_cs_discipline"
CASE = "t_affairs_discipline_case"
REMOVE = "t_affairs_discipline_remove_apply"
RISK = "t_affairs_risk_record"
HANDLE = "t_affairs_risk_handle_record"


def _has(bind, table):
    return table in inspect(bind).get_table_names()


def _cols(bind, table):
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _pk_tenant(*extra):
    return [
        sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        *extra,
    ]


def _common_cols():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    ]


def _create(bind, table, cols, indexes=(), uniques=()):
    if _has(bind, table):
        return
    op.create_table(table, *cols)
    for ix_col in indexes:
        op.create_index(f"ix_{table}_{ix_col}", table, [ix_col])
    for name, ucols in uniques:
        op.create_unique_constraint(name, table, list(ucols))


def upgrade() -> None:
    bind = op.get_bind()

    # t_cs_discipline 加 source_case_id（nullable）
    if _has(bind, DISC) and "source_case_id" not in _cols(bind, DISC):
        op.add_column(DISC, sa.Column("source_case_id", sa.BigInteger(), nullable=True))
        cur_idx = {i["name"] for i in inspect(bind).get_indexes(DISC)}
        if "ix_t_cs_discipline_source_case_id" not in cur_idx:
            op.create_index("ix_t_cs_discipline_source_case_id", DISC, ["source_case_id"])

    _create(bind, CASE, _pk_tenant(
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("disc_type", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("doc_no", sa.String(length=100), nullable=True),
        sa.Column("decide_date", sa.DateTime(), nullable=True),
        sa.Column("effective_at", sa.DateTime(), nullable=True),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
        sa.Column("cs_discipline_id", sa.BigInteger(), nullable=True),
        sa.Column("return_reason", sa.String(length=500), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "student_id", "status", "workflow_instance_id"))

    _create(bind, REMOVE, _pk_tenant(
        sa.Column("case_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=True),
        sa.Column("apply_reason", sa.String(length=1000), nullable=True),
        sa.Column("min_months_check", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("current_node", sa.String(length=50), nullable=True),
        sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
        sa.Column("return_reason", sa.String(length=500), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "case_id", "student_id"))

    _create(bind, RISK, _pk_tenant(
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_ref_id", sa.BigInteger(), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("detail", sa.String(length=1000), nullable=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=True),
        sa.Column("deadline_at", sa.DateTime(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=True),
        sa.Column("escalated_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("closed_reason", sa.String(length=500), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "student_id", "source", "owner_id", "status"),
       uniques=(("uk_risk_source_ref", ("tenant_id", "source", "source_ref_id")),))

    _create(bind, HANDLE, _pk_tenant(
        sa.Column("risk_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("content", sa.String(length=1000), nullable=True),
        sa.Column("operator", sa.String(length=100), nullable=True),
        sa.Column("from_status", sa.String(length=50), nullable=True),
        sa.Column("to_status", sa.String(length=50), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "risk_id"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in (HANDLE, RISK, REMOVE, CASE):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
    if _has(bind, DISC) and "source_case_id" in _cols(bind, DISC):
        for idx in inspect(bind).get_indexes(DISC):
            if "source_case_id" in (idx.get("column_names") or []):
                op.drop_index(idx["name"], table_name=DISC)
        with op.batch_alter_table(DISC) as batch:
            batch.drop_column("source_case_id")
