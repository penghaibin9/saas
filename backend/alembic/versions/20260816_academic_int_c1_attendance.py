"""Academic INT C-C1 attendance source/occurrence expand schema.

Revision ID: 20260816_acad_int_c1_att
Revises: 20260816_acad_int_ac4

Expand only. All new columns remain nullable, no CHECK/UNIQUE and no backfill.
The later contract migration may tighten only after writer dual-write and repeatable
legacy inventory prove dirty data is reconciled or explicitly isolated.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260816_acad_int_c1_att"
down_revision = "20260816_acad_int_ac4"
branch_labels = None
depends_on = None

TABLE = "t_aa_attendance_session"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260816_acad_int_c1_att requires MySQL")


def upgrade() -> None:
    _require_mysql()
    op.add_column(
        TABLE,
        sa.Column(
            "teaching_task_id",
            sa.BigInteger(),
            nullable=True,
            comment="formal TeachingTask; ADMIN_SPECIAL / unresolved legacy may be NULL",
        ),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "occurrence_identity",
            sa.String(length=255),
            nullable=True,
            comment="canonical formal occurrence identity; unresolved legacy stays NULL",
        ),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "source_type",
            sa.String(length=30),
            nullable=True,
            comment="FORMAL_TEACHING / ADMIN_SPECIAL; unresolved legacy stays NULL",
        ),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "source_reason",
            sa.String(length=500),
            nullable=True,
            comment="ADMIN_SPECIAL reason; unresolved legacy stays NULL",
        ),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "source_evidence",
            sa.Text(),
            nullable=True,
            comment="auditable source evidence snapshot; unresolved legacy stays NULL",
        ),
    )
    op.create_index("ix_aa_attendance_task", TABLE, ["tenant_id", "teaching_task_id"], unique=False)
    op.create_index("ix_aa_attendance_source", TABLE, ["tenant_id", "source_type"], unique=False)
    op.create_index("ix_aa_attendance_occurrence", TABLE, ["tenant_id", "occurrence_identity"], unique=False)


def downgrade() -> None:
    _require_mysql()
    op.drop_index("ix_aa_attendance_occurrence", table_name=TABLE)
    op.drop_index("ix_aa_attendance_source", table_name=TABLE)
    op.drop_index("ix_aa_attendance_task", table_name=TABLE)
    op.drop_column(TABLE, "source_evidence")
    op.drop_column(TABLE, "source_reason")
    op.drop_column(TABLE, "source_type")
    op.drop_column(TABLE, "occurrence_identity")
    op.drop_column(TABLE, "teaching_task_id")
