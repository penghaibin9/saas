"""13A-P3: 建困难认定 4 表 + 奖助 3 表

Revision ID: 0005_13a_p3_aid_funding
Revises: 0004_13a_p2_leave
Create Date: 2026-07-06

困难认定：t_affairs_aid_batch / _apply(12态,唯一键 batch+student) / _family_economy(强敏感隔离) /
_level_history(困难库,append-only)；奖助：t_affairs_funding_project / _batch / _application(唯一键 batch+student)。
幂等：inspect 检测已存在则跳过（与 create_all 共存不冲突）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0005_13a_p3_aid_funding"
down_revision = "0004_13a_p2_leave"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")

AID_BATCH = "t_affairs_aid_batch"
AID_APPLY = "t_affairs_aid_apply"
AID_FAMILY = "t_affairs_aid_family_economy"
AID_HISTORY = "t_affairs_aid_level_history"
FUND_PROJECT = "t_affairs_funding_project"
FUND_BATCH = "t_affairs_funding_batch"
FUND_APP = "t_affairs_funding_application"


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


def _audit_time_cols():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
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

    # ── 困难认定 4 表 ──
    _create(bind, AID_BATCH, _pk_tenant(
        sa.Column("batch_name", sa.String(length=200), nullable=False),
        sa.Column("year_code", sa.String(length=50), nullable=False),
        sa.Column("apply_start", sa.DateTime(), nullable=True),
        sa.Column("apply_end", sa.DateTime(), nullable=True),
        sa.Column("publicity_days", sa.Integer(), nullable=True),
        sa.Column("level_config_json", sa.String(length=2000), nullable=True),
        sa.Column("scope_json", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "year_code", "status"))

    _create(bind, AID_APPLY, _pk_tenant(
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("apply_level", sa.String(length=50), nullable=True),
        sa.Column("suggest_level", sa.String(length=50), nullable=True),
        sa.Column("final_level", sa.String(length=50), nullable=True),
        sa.Column("statement", sa.String(length=1000), nullable=True),
        sa.Column("class_review_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("class_review_rank", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
        sa.Column("publicity_at", sa.DateTime(), nullable=True),
        sa.Column("result_at", sa.DateTime(), nullable=True),
        sa.Column("return_reason", sa.String(length=500), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "batch_id", "student_id", "status"),
       uniques=(("uk_aid_apply_batch_student", ("tenant_id", "batch_id", "student_id")),))

    _create(bind, AID_FAMILY, _pk_tenant(
        sa.Column("apply_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=True),
        sa.Column("member_count", sa.Integer(), nullable=True),
        sa.Column("family_members_json", sa.String(length=2000), nullable=True),
        sa.Column("income_encrypted", sa.String(length=200), nullable=True),
        sa.Column("debt_encrypted", sa.String(length=200), nullable=True),
        sa.Column("special_flags_json", sa.String(length=500), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "apply_id", "student_id"))

    _create(bind, AID_HISTORY, _pk_tenant(
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("from_level", sa.String(length=50), nullable=True),
        sa.Column("to_level", sa.String(length=50), nullable=True),
        sa.Column("change_type", sa.String(length=50), nullable=False),
        sa.Column("apply_id", sa.BigInteger(), nullable=True),
        sa.Column("batch_id", sa.BigInteger(), nullable=True),
        sa.Column("year_code", sa.String(length=50), nullable=True),
        sa.Column("effective_at", sa.DateTime(), nullable=False),
        *_audit_time_cols(),
    ), indexes=("tenant_id", "student_id", "apply_id", "batch_id"))

    # ── 奖助 3 表 ──
    _create(bind, FUND_PROJECT, _pk_tenant(
        sa.Column("project_name", sa.String(length=200), nullable=False),
        sa.Column("project_type", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("quota", sa.Integer(), nullable=True),
        sa.Column("condition_json", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "project_type"))

    _create(bind, FUND_BATCH, _pk_tenant(
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("project_type", sa.String(length=50), nullable=True),
        sa.Column("year_code", sa.String(length=50), nullable=False),
        sa.Column("apply_start", sa.DateTime(), nullable=True),
        sa.Column("apply_end", sa.DateTime(), nullable=True),
        sa.Column("publicity_days", sa.Integer(), nullable=True),
        sa.Column("quota", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "project_id", "project_type", "year_code"))

    _create(bind, FUND_APP, _pk_tenant(
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("apply_source", sa.String(length=20), nullable=False),
        sa.Column("project_type", sa.String(length=50), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("statement", sa.String(length=1000), nullable=True),
        sa.Column("check_snapshot_json", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
        sa.Column("publicity_at", sa.DateTime(), nullable=True),
        sa.Column("result_at", sa.DateTime(), nullable=True),
        sa.Column("return_reason", sa.String(length=500), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "batch_id", "student_id", "project_type", "status"),
       uniques=(("uk_funding_app_batch_student", ("tenant_id", "batch_id", "student_id")),))


def downgrade() -> None:
    bind = op.get_bind()
    for table in (FUND_APP, FUND_BATCH, FUND_PROJECT, AID_HISTORY, AID_FAMILY, AID_APPLY, AID_BATCH):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
