"""13A-P5: 建谈话 plan/record + 家校 contact_log 3 表

Revision ID: 0007_13a_p5_talk_family
Revises: 0006_13a_p4_discipline_risk
Create Date: 2026-07-06

谈话记录集中兑现 P2-P4 进360；家校 append-only 不存号码本体（号码在 t_student_contact）。
幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0007_13a_p5_talk_family"
down_revision = "0006_13a_p4_discipline_risk"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
PLAN = "t_affairs_talk_plan"
RECORD = "t_affairs_talk_record"
FAMILY = "t_affairs_family_contact_log"


def _has(bind, table):
    return table in inspect(bind).get_table_names()


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


def _create(bind, table, cols, indexes=()):
    if _has(bind, table):
        return
    op.create_table(table, *cols)
    for ix_col in indexes:
        op.create_index(f"ix_{table}_{ix_col}", table, [ix_col])


def upgrade() -> None:
    bind = op.get_bind()

    _create(bind, PLAN, _pk_tenant(
        sa.Column("plan_name", sa.String(length=200), nullable=True),
        sa.Column("teacher_id", sa.BigInteger(), nullable=True),
        sa.Column("topic_type", sa.String(length=50), nullable=False),
        sa.Column("planned_at", sa.DateTime(), nullable=True),
        sa.Column("student_ids_json", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "teacher_id", "status"))

    _create(bind, RECORD, _pk_tenant(
        sa.Column("plan_id", sa.BigInteger(), nullable=True),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_id", sa.BigInteger(), nullable=True),
        sa.Column("topic_type", sa.String(length=50), nullable=False),
        sa.Column("topic", sa.String(length=500), nullable=True),
        sa.Column("talk_at", sa.DateTime(), nullable=True),
        sa.Column("content", sa.String(length=2000), nullable=True),
        sa.Column("result", sa.String(length=50), nullable=True),
        sa.Column("need_follow", sa.Boolean(), nullable=True),
        sa.Column("related_risk_id", sa.BigInteger(), nullable=True),
        sa.Column("related_contact_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "plan_id", "student_id", "teacher_id", "status"))

    _create(bind, FAMILY, _pk_tenant(
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_id", sa.BigInteger(), nullable=True),
        sa.Column("contact_type", sa.String(length=50), nullable=False),
        sa.Column("contact_reason", sa.String(length=500), nullable=True),
        sa.Column("contact_result", sa.String(length=1000), nullable=True),
        sa.Column("related_risk_id", sa.BigInteger(), nullable=True),
        sa.Column("full_phone_viewed", sa.Boolean(), nullable=False),
        sa.Column("view_reason", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
    ), indexes=("tenant_id", "student_id", "teacher_id"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in (FAMILY, RECORD, PLAN):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
