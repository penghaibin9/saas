"""O5 signed orientation check-in and enrollment finalization authority.

Revision ID: 20260901_orientation_checkin_o5
Revises: 20260901_dorm_presence_d6
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260901_orientation_checkin_o5"
down_revision = "20260901_dorm_presence_d6"
branch_labels = None
depends_on = None

TOKEN = "t_orientation_checkin_token"
RECORD = "t_orientation_checkin_record"
FINALIZE = "t_orientation_enrollment_finalize"


def _preflight() -> None:
    existing = set(inspect(op.get_bind()).get_table_names())
    collisions = sorted(existing.intersection({TOKEN, RECORD, FINALIZE}))
    if collisions:
        raise RuntimeError(
            "O5 preflight failed before DDL: tables already exist outside this revision: "
            + ",".join(collisions)
        )


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    ]


def upgrade() -> None:
    _preflight()
    op.create_table(
        TOKEN,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("orientation_student_id", sa.BigInteger(), nullable=False),
        sa.Column("nonce_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("issued_by", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_by", sa.BigInteger(), nullable=True),
        sa.Column("checkin_record_id", sa.BigInteger(), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint("tenant_id", "nonce_hash", name="uk_ori_checkin_token_nonce"),
        sa.CheckConstraint(
            "status IN ('ISSUED','CONSUMED','REVOKED','EXPIRED')",
            name="ck_ori_checkin_token_status",
        ),
        sa.CheckConstraint(
            "batch_id > 0 AND orientation_student_id > 0",
            name="ck_ori_checkin_token_subject",
        ),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_ori_checkin_token_student_status",
        TOKEN,
        ["tenant_id", "orientation_student_id", "status", "expires_at", "is_deleted"],
    )

    op.create_table(
        RECORD,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("orientation_student_id", sa.BigInteger(), nullable=False),
        sa.Column("checkin_point_id", sa.BigInteger(), nullable=False),
        sa.Column("token_id", sa.BigInteger(), nullable=False),
        sa.Column("nonce_hash", sa.String(64), nullable=False),
        sa.Column("checked_in_at", sa.DateTime(), nullable=False),
        sa.Column("checked_in_by", sa.BigInteger(), nullable=False),
        sa.Column("checkin_method", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "orientation_student_id", name="uk_ori_checkin_record_student"
        ),
        sa.UniqueConstraint("tenant_id", "token_id", name="uk_ori_checkin_record_token"),
        sa.UniqueConstraint("tenant_id", "nonce_hash", name="uk_ori_checkin_record_nonce"),
        sa.CheckConstraint("checkin_method = 'SIGNED_TOKEN'", name="ck_ori_checkin_method"),
        sa.CheckConstraint("status = 'CONFIRMED'", name="ck_ori_checkin_record_status"),
        sa.CheckConstraint(
            "batch_id > 0 AND orientation_student_id > 0 AND checkin_point_id > 0 "
            "AND token_id > 0 AND checked_in_by > 0",
            name="ck_ori_checkin_record_refs",
        ),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_ori_checkin_record_point_time",
        RECORD,
        ["tenant_id", "checkin_point_id", "checked_in_at", "is_deleted"],
    )
    op.create_index(
        "ix_ori_checkin_record_operator_time",
        RECORD,
        ["tenant_id", "checked_in_by", "checked_in_at", "is_deleted"],
    )

    op.create_table(
        FINALIZE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("orientation_student_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("student_no_snapshot", sa.String(50), nullable=False),
        sa.Column("from_stage", sa.String(50), nullable=True),
        sa.Column("to_stage", sa.String(50), nullable=False),
        sa.Column("finalized_at", sa.DateTime(), nullable=False),
        sa.Column("finalized_by", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "orientation_student_id", name="uk_ori_finalize_student"
        ),
        sa.UniqueConstraint("tenant_id", "request_id", name="uk_ori_finalize_request"),
        sa.CheckConstraint("to_stage = 'ENROLLED'", name="ck_ori_finalize_stage"),
        sa.CheckConstraint("status = 'FINALIZED'", name="ck_ori_finalize_status"),
        sa.CheckConstraint(
            "batch_id > 0 AND orientation_student_id > 0 AND student_id > 0 AND finalized_by > 0",
            name="ck_ori_finalize_refs",
        ),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_ori_finalize_profile_time",
        FINALIZE,
        ["tenant_id", "student_id", "finalized_at", "is_deleted"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in (FINALIZE, RECORD, TOKEN):
        count = int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
        if count:
            raise RuntimeError(f"O5 downgrade blocked: {table} contains {count} business rows")
    op.drop_index("ix_ori_finalize_profile_time", table_name=FINALIZE)
    op.drop_table(FINALIZE)
    op.drop_index("ix_ori_checkin_record_operator_time", table_name=RECORD)
    op.drop_index("ix_ori_checkin_record_point_time", table_name=RECORD)
    op.drop_table(RECORD)
    op.drop_index("ix_ori_checkin_token_student_status", table_name=TOKEN)
    op.drop_table(TOKEN)
