"""Stage C3 closeout: official correction facts and versioned graduation decisions.

Revision ID: 20260809_aa_stage_c3_fact_v2
Revises: 20260809_aa_fact_time_precision_c1
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260809_aa_stage_c3_fact_v2"
down_revision = "20260809_aa_fact_time_precision_c1"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return set()
    return {str(row["name"]) for row in inspector.get_columns(table)}


def _unique_names(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return set()
    return {str(row.get("name")) for row in inspector.get_unique_constraints(table) if row.get("name")}


def _index_names(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return set()
    return {str(row.get("name")) for row in inspector.get_indexes(table) if row.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    decision = "t_aa_graduation_decision_fact"
    correction = "t_aa_post_archive_correction_case"

    cols = _columns(bind, decision)
    if decision and cols:
        if "decision_no" not in cols:
            op.add_column(decision, sa.Column("decision_no", sa.Integer(), nullable=True))
            op.execute(sa.text(f"UPDATE {decision} SET decision_no = 1 WHERE decision_no IS NULL"))
            op.alter_column(decision, "decision_no", existing_type=sa.Integer(), nullable=False)
        if "supersedes_id" not in cols:
            op.add_column(decision, sa.Column("supersedes_id", sa.BigInteger(), nullable=True))
        if "correction_case_id" not in cols:
            op.add_column(decision, sa.Column("correction_case_id", sa.BigInteger(), nullable=True))

        uniques = _unique_names(bind, decision)
        if "uk_aa_grad_decision_result" in uniques:
            op.drop_constraint("uk_aa_grad_decision_result", decision, type_="unique")
        uniques = _unique_names(bind, decision)
        if "uk_aa_grad_decision_version" not in uniques:
            op.create_unique_constraint(
                "uk_aa_grad_decision_version", decision,
                ["tenant_id", "result_id", "decision_no"],
            )
        if "uk_aa_grad_decision_correction_case" not in uniques:
            op.create_unique_constraint(
                "uk_aa_grad_decision_correction_case", decision,
                ["tenant_id", "correction_case_id"],
            )

        indexes = _index_names(bind, decision)
        if "ix_aa_grad_decision_supersedes_id" not in indexes:
            op.create_index("ix_aa_grad_decision_supersedes_id", decision, ["supersedes_id"], unique=False)
        if "ix_aa_grad_decision_correction_case_id" not in indexes:
            op.create_index("ix_aa_grad_decision_correction_case_id", decision, ["correction_case_id"], unique=False)
        if "ix_aa_grad_decision_latest" not in indexes:
            op.create_index(
                "ix_aa_grad_decision_latest", decision,
                ["tenant_id", "result_id", "decision_no"], unique=False,
            )

    cols = _columns(bind, correction)
    if correction and cols:
        if "official_fact_type" not in cols:
            op.add_column(correction, sa.Column("official_fact_type", sa.String(length=50), nullable=True))
        if "official_fact_id" not in cols:
            op.add_column(correction, sa.Column("official_fact_id", sa.BigInteger(), nullable=True))
        indexes = _index_names(bind, correction)
        if "ix_t_aa_post_archive_correction_case_official_fact_id" not in indexes:
            op.create_index(
                "ix_t_aa_post_archive_correction_case_official_fact_id",
                correction, ["official_fact_id"], unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    decision = "t_aa_graduation_decision_fact"
    correction = "t_aa_post_archive_correction_case"

    if _columns(bind, correction):
        indexes = _index_names(bind, correction)
        if "ix_t_aa_post_archive_correction_case_official_fact_id" in indexes:
            op.drop_index("ix_t_aa_post_archive_correction_case_official_fact_id", table_name=correction)
        cols = _columns(bind, correction)
        if "official_fact_id" in cols:
            op.drop_column(correction, "official_fact_id")
        if "official_fact_type" in cols:
            op.drop_column(correction, "official_fact_type")

    if _columns(bind, decision):
        duplicate = bind.execute(sa.text(
            f"SELECT 1 FROM {decision} GROUP BY tenant_id, result_id HAVING COUNT(*) > 1 LIMIT 1"
        )).first()
        if duplicate:
            raise RuntimeError(
                "Cannot downgrade Stage C3 decision versioning after corrected graduation decisions exist"
            )
        indexes = _index_names(bind, decision)
        for name in (
            "ix_aa_grad_decision_latest",
            "ix_aa_grad_decision_correction_case_id",
            "ix_aa_grad_decision_supersedes_id",
        ):
            if name in indexes:
                op.drop_index(name, table_name=decision)
        uniques = _unique_names(bind, decision)
        for name in ("uk_aa_grad_decision_correction_case", "uk_aa_grad_decision_version"):
            if name in uniques:
                op.drop_constraint(name, decision, type_="unique")
        if "uk_aa_grad_decision_result" not in _unique_names(bind, decision):
            op.create_unique_constraint("uk_aa_grad_decision_result", decision, ["tenant_id", "result_id"])
        cols = _columns(bind, decision)
        for name in ("correction_case_id", "supersedes_id", "decision_no"):
            if name in cols:
                op.drop_column(decision, name)
