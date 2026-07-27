"""学工材料补交版本与安全批次主表/明细表。

Revision ID: 0127_affairs_material_batch_ops
Revises: 0126_aa_grade_task_uniqueness_guard
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0127_affairs_material_batch_ops"
down_revision = "0126_aa_grade_task_uniqueness_guard"
branch_labels = None
depends_on = None


def _tables(bind) -> set[str]:
    return set(inspect(bind).get_table_names())


def _common_columns():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)

    if "t_affairs_material_requirement" not in tables:
        op.create_table(
            "t_affairs_material_requirement",
            *_common_columns(),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("biz_type", sa.String(50), nullable=False),
            sa.Column("biz_id", sa.BigInteger(), nullable=False),
            sa.Column("item_code", sa.String(100), nullable=False),
            sa.Column("item_name", sa.String(200), nullable=False),
            sa.Column("requirement_reason", sa.String(500), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="MISSING"),
            sa.Column("return_round", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("due_at", sa.DateTime(), nullable=True),
            sa.Column("review_owner_id", sa.BigInteger(), nullable=True),
            sa.Column("current_submission_id", sa.BigInteger(), nullable=True),
            sa.Column("accepted_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "tenant_id", "biz_type", "biz_id", "item_code",
                name="uk_affairs_material_requirement_biz_item",
            ),
        )
        op.create_index(
            "ix_affairs_material_requirement_tenant_id",
            "t_affairs_material_requirement", ["tenant_id"],
        )
        op.create_index(
            "ix_affairs_material_requirement_student_id",
            "t_affairs_material_requirement", ["student_id"],
        )
        op.create_index(
            "ix_affairs_material_requirement_review_owner_id",
            "t_affairs_material_requirement", ["review_owner_id"],
        )
        op.create_index(
            "ix_affairs_material_requirement_current_submission_id",
            "t_affairs_material_requirement", ["current_submission_id"],
        )
        op.create_index(
            "ix_affairs_material_requirement_biz",
            "t_affairs_material_requirement", ["tenant_id", "biz_type", "biz_id", "status"],
        )

    tables = _tables(bind)
    if "t_affairs_material_submission" not in tables:
        op.create_table(
            "t_affairs_material_submission",
            *_common_columns(),
            sa.Column("requirement_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("affairs_attachment_id", sa.BigInteger(), nullable=False),
            sa.Column("file_id", sa.BigInteger(), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="SUBMITTED"),
            sa.Column("submitted_by", sa.String(64), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=False),
            sa.Column("reviewed_by", sa.String(64), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("review_note", sa.String(500), nullable=True),
            sa.Column("supersedes_id", sa.BigInteger(), nullable=True),
            sa.UniqueConstraint(
                "tenant_id", "requirement_id", "version_no",
                name="uk_affairs_material_submission_version",
            ),
        )
        op.create_index(
            "ix_affairs_material_submission_tenant_id",
            "t_affairs_material_submission", ["tenant_id"],
        )
        op.create_index(
            "ix_affairs_material_submission_requirement_id",
            "t_affairs_material_submission", ["requirement_id"],
        )
        op.create_index(
            "ix_affairs_material_submission_student_id",
            "t_affairs_material_submission", ["student_id"],
        )
        op.create_index(
            "ix_affairs_material_submission_attachment_id",
            "t_affairs_material_submission", ["affairs_attachment_id"],
        )
        op.create_index(
            "ix_affairs_material_submission_supersedes_id",
            "t_affairs_material_submission", ["supersedes_id"],
        )
        op.create_index(
            "ix_affairs_material_submission_requirement",
            "t_affairs_material_submission", ["tenant_id", "requirement_id", "status", "version_no"],
        )

    tables = _tables(bind)
    if "t_affairs_batch_job" not in tables:
        op.create_table(
            "t_affairs_batch_job",
            *_common_columns(),
            sa.Column("batch_no", sa.String(64), nullable=False),
            sa.Column("job_type", sa.String(50), nullable=False),
            sa.Column("idempotency_key", sa.String(128), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
            sa.Column("requested_by", sa.String(64), nullable=False),
            sa.Column("retry_of_id", sa.BigInteger(), nullable=True),
            sa.Column("request_json", sa.JSON(), nullable=True),
            sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("pending_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.String(1000), nullable=True),
            sa.UniqueConstraint("tenant_id", "batch_no", name="uk_affairs_batch_job_no"),
            sa.UniqueConstraint(
                "tenant_id", "job_type", "idempotency_key",
                name="uk_affairs_batch_job_idempotency",
            ),
        )
        op.create_index("ix_affairs_batch_job_tenant_id", "t_affairs_batch_job", ["tenant_id"])
        op.create_index("ix_affairs_batch_job_retry_of_id", "t_affairs_batch_job", ["retry_of_id"])
        op.create_index(
            "ix_affairs_batch_job_status",
            "t_affairs_batch_job", ["tenant_id", "job_type", "status"],
        )

    tables = _tables(bind)
    if "t_affairs_batch_job_item" not in tables:
        op.create_table(
            "t_affairs_batch_job_item",
            *_common_columns(),
            sa.Column("batch_job_id", sa.BigInteger(), nullable=False),
            sa.Column("item_key", sa.String(128), nullable=False),
            sa.Column("todo_type", sa.String(50), nullable=True),
            sa.Column("biz_type", sa.String(50), nullable=False),
            sa.Column("biz_id", sa.BigInteger(), nullable=False),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("expected_version", sa.Integer(), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_code", sa.String(100), nullable=True),
            sa.Column("error_message", sa.String(1000), nullable=True),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "tenant_id", "batch_job_id", "item_key",
                name="uk_affairs_batch_job_item_key",
            ),
        )
        op.create_index("ix_affairs_batch_job_item_tenant_id", "t_affairs_batch_job_item", ["tenant_id"])
        op.create_index("ix_affairs_batch_job_item_batch_job_id", "t_affairs_batch_job_item", ["batch_job_id"])
        op.create_index(
            "ix_affairs_batch_job_item_status",
            "t_affairs_batch_job_item", ["tenant_id", "batch_job_id", "status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)
    if "t_affairs_batch_job_item" in tables:
        op.drop_table("t_affairs_batch_job_item")
    tables = _tables(bind)
    if "t_affairs_batch_job" in tables:
        op.drop_table("t_affairs_batch_job")
    tables = _tables(bind)
    if "t_affairs_material_submission" in tables:
        op.drop_table("t_affairs_material_submission")
    tables = _tables(bind)
    if "t_affairs_material_requirement" in tables:
        op.drop_table("t_affairs_material_requirement")
