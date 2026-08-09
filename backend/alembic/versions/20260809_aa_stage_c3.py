"""Stage C3: immutable graduation runs, archive manifests and correction cases.

Revision ID: 20260809_aa_stage_c3
Revises: 20260809_aa_fact_c1
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260809_aa_stage_c3"
down_revision = "20260809_aa_fact_c1"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _create_graduation_run() -> None:
    name = "t_aa_graduation_evaluation_run"
    bind = op.get_bind()
    if _has_table(bind, name):
        return
    op.create_table(
        name,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("result_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("run_no", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.BigInteger(), nullable=True),
        sa.Column("input_snapshot_json", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("item_results_json", sa.Text(), nullable=False),
        sa.Column("overall", sa.String(length=50), nullable=False),
        sa.Column("evaluator_version", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "result_id", "run_no", name="uk_aa_grad_eval_run"),
    )
    for col in ("tenant_id", "batch_id", "result_id", "student_id", "program_id", "overall"):
        op.create_index(f"ix_{name}_{col}", name, [col], unique=False)
    op.create_index("ix_aa_grad_eval_student", name,
                    ["tenant_id", "batch_id", "student_id", "run_no"], unique=False)


def _create_graduation_decision() -> None:
    name = "t_aa_graduation_decision_fact"
    bind = op.get_bind()
    if _has_table(bind, name):
        return
    op.create_table(
        name,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("result_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("evaluation_run_id", sa.BigInteger(), nullable=False),
        sa.Column("conclusion", sa.String(length=50), nullable=False),
        sa.Column("decision_at", sa.DateTime(), nullable=False),
        sa.Column("decision_by", sa.BigInteger(), nullable=True),
        sa.Column("review_note", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "result_id", name="uk_aa_grad_decision_result"),
    )
    for col in ("tenant_id", "batch_id", "result_id", "student_id", "evaluation_run_id"):
        op.create_index(f"ix_{name}_{col}", name, [col], unique=False)
    op.create_index("ix_aa_grad_decision_eval", name, ["tenant_id", "evaluation_run_id"], unique=False)


def _create_archive_manifest() -> None:
    name = "t_aa_archive_manifest"
    bind = op.get_bind()
    if _has_table(bind, name):
        return
    op.create_table(
        name,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("term_id", sa.BigInteger(), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("archive_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("domain_counts_json", sa.Text(), nullable=False),
        sa.Column("domain_hashes_json", sa.Text(), nullable=False),
        sa.Column("max_ids_json", sa.Text(), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("supersedes_id", sa.BigInteger(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=False),
        sa.Column("archived_by", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "archive_batch_id", "version_no", name="uk_aa_archive_manifest_version"),
    )
    for col in ("tenant_id", "term_id", "archive_batch_id", "supersedes_id"):
        op.create_index(f"ix_{name}_{col}", name, [col], unique=False)
    op.create_index("ix_aa_archive_manifest_latest", name,
                    ["tenant_id", "archive_batch_id", "version_no"], unique=False)


def _create_archive_correction() -> None:
    name = "t_aa_post_archive_correction_case"
    bind = op.get_bind()
    if _has_table(bind, name):
        return
    op.create_table(
        name,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="逻辑删除"),
        sa.Column("version", sa.Integer(), nullable=False, comment="乐观锁"),
        sa.Column("archive_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("correction_no", sa.Integer(), nullable=False),
        sa.Column("business_type", sa.String(length=30), nullable=False, comment="GRADE/GRADUATION"),
        sa.Column("target_ref", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("correction_json", sa.Text(), nullable=False),
        sa.Column("evidence_manifest", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("second_approved_by", sa.BigInteger(), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("resulting_manifest_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False,
                  comment="PENDING_SECOND_APPROVAL/APPLIED/REJECTED"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "archive_batch_id", "correction_no", name="uk_aa_archive_correction_no"),
    )
    for col in ("tenant_id", "archive_batch_id", "resulting_manifest_id", "status"):
        op.create_index(f"ix_{name}_{col}", name, [col], unique=False)
    op.create_index("ix_aa_archive_correction_status", name,
                    ["tenant_id", "archive_batch_id", "status"], unique=False)


def upgrade() -> None:
    _create_graduation_run()
    _create_graduation_decision()
    _create_archive_manifest()
    _create_archive_correction()


def downgrade() -> None:
    bind = op.get_bind()
    for name in (
        "t_aa_post_archive_correction_case",
        "t_aa_archive_manifest",
        "t_aa_graduation_decision_fact",
        "t_aa_graduation_evaluation_run",
    ):
        if _has_table(bind, name):
            op.drop_table(name)
