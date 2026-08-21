"""SP-E08: real generated-document pointer on EmpStudent (destination agreement/registration PDF).

Mirrors the internship application snapshot pattern (generated_profile_pdf_file_id) rather than
inventing a second file-tracking mechanism: a single pointer column + a source-version stamp lets
the document service reuse the last generated file while EmpStudent facts are unchanged, and
regenerate once they move.

Revision ID: 20260821_emp_dest_doc
Revises: 20260821_todo_completed_at
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260821_emp_dest_doc"
down_revision = "20260821_todo_completed_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("t_emp_student",
                  sa.Column("destination_document_file_id", sa.BigInteger(), nullable=True))
    op.add_column("t_emp_student",
                  sa.Column("destination_document_source_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("t_emp_student", "destination_document_source_version")
    op.drop_column("t_emp_student", "destination_document_file_id")
