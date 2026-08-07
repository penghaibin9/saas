"""包 2：有效成绩策略版本身份、活动范围唯一合同与历史导入欠账登记。

Revision ID: 20260806_aa_pkg2_policy
Revises: 20260806_aa_pkg5_concur
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "20260806_aa_pkg2_policy"
down_revision = "20260806_aa_pkg5_concur"
branch_labels = None
depends_on = None

# alembic_version.version_num 的正式合同为 VARCHAR(32)，迁移 ID 必须稳定落入该边界。
assert len(revision) <= 32

_POLICY = "t_aa_effective_grade_policy"
_BYPASS = "t_aa_effective_grade_policy_bypass"
_UK_CODE = "uk_aa_effective_grade_policy_code"
_UK_VERSION = "uk_aa_effective_grade_policy_ver"
_UK_SCOPE = "uk_aa_effective_grade_policy_scope"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260806_aa_pkg2_policy requires MySQL")


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())

    if _POLICY in tables:
        columns = {row["name"] for row in inspect(bind).get_columns(_POLICY)}
        if "active_scope_key" not in columns:
            op.add_column(_POLICY, sa.Column(
                "active_scope_key", sa.String(length=40), nullable=True,
                comment="ACTIVE 行的生效范围键（学期ID 或 BASE）；非 ACTIVE 行为 NULL",
            ))
        # 回填：现存 ACTIVE 行按生效学期归位；SUPERSEDED/DRAFT 一律留空，不占用活动范围。
        bind.execute(text(
            f"UPDATE {_POLICY} SET active_scope_key = CASE "
            "WHEN effective_from_term_id IS NULL THEN 'BASE' "
            "ELSE CAST(effective_from_term_id AS CHAR) END "
            "WHERE status = 'ACTIVE' AND is_deleted = 0 AND active_scope_key IS NULL"
        ))
        # 同一范围出现历史重复 ACTIVE 时，保留版本最高（同版本取 id 最大）的那条，
        # 其余降级为 SUPERSEDED 并让出范围键——否则新唯一索引建不起来。
        bind.execute(text(
            f"UPDATE {_POLICY} p JOIN ("
            f"  SELECT p1.id FROM {_POLICY} p1 JOIN {_POLICY} p2 "
            "   ON p1.tenant_id = p2.tenant_id AND p1.active_scope_key = p2.active_scope_key "
            "  AND p1.active_scope_key IS NOT NULL "
            "  AND (p2.policy_version > p1.policy_version "
            "       OR (p2.policy_version = p1.policy_version AND p2.id > p1.id))"
            ") loser ON loser.id = p.id "
            "SET p.active_scope_key = NULL, p.status = 'SUPERSEDED'"
        ))

        indexes = {row["name"] for row in inspect(bind).get_indexes(_POLICY)}
        constraints = {row["name"] for row in inspect(bind).get_unique_constraints(_POLICY)}
        existing = indexes | constraints
        if _UK_CODE in existing:
            # 旧合同把 policy_code 锁死为租户内唯一，同一策略无法发布 V2；必须先解除。
            op.drop_constraint(_UK_CODE, _POLICY, type_="unique")
        if _UK_VERSION not in existing:
            op.create_unique_constraint(_UK_VERSION, _POLICY, ["tenant_id", "policy_code", "policy_version"])
        if _UK_SCOPE not in existing:
            op.create_unique_constraint(_UK_SCOPE, _POLICY, ["tenant_id", "active_scope_key"])

    if _BYPASS not in tables:
        op.create_table(
            _BYPASS,
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("source", sa.String(length=50), nullable=False),
            sa.Column("operator", sa.String(length=100), nullable=False),
            sa.Column("batch_no", sa.String(length=100), nullable=False),
            sa.Column("debt_reason", sa.String(length=500), nullable=False),
            sa.Column("grade_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.PrimaryKeyConstraint("id", name="pk_t_aa_effective_grade_policy_bypass"),
            sa.UniqueConstraint("tenant_id", "batch_no", name="uk_aa_grade_policy_bypass_batch"),
        )
        op.create_index("ix_aa_grade_policy_bypass_tenant", _BYPASS, ["tenant_id", "source"], unique=False)


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())

    if _BYPASS in tables:
        op.drop_index("ix_aa_grade_policy_bypass_tenant", table_name=_BYPASS)
        op.drop_table(_BYPASS)

    if _POLICY in tables:
        indexes = {row["name"] for row in inspect(bind).get_indexes(_POLICY)}
        constraints = {row["name"] for row in inspect(bind).get_unique_constraints(_POLICY)}
        existing = indexes | constraints
        if _UK_SCOPE in existing:
            op.drop_constraint(_UK_SCOPE, _POLICY, type_="unique")
        if _UK_VERSION in existing:
            op.drop_constraint(_UK_VERSION, _POLICY, type_="unique")
        if _UK_CODE not in existing:
            op.create_unique_constraint(_UK_CODE, _POLICY, ["tenant_id", "policy_code"])
        columns = {row["name"] for row in inspect(bind).get_columns(_POLICY)}
        if "active_scope_key" in columns:
            op.drop_column(_POLICY, "active_scope_key")
