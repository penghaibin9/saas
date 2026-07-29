"""Stop writing legacy campus-service student identity for new leave records.

Revision ID: 0144_affairs_leave_identity_cutover
Revises: 0143_merge_affairs_material_ops
"""
from alembic import op
import sqlalchemy as sa


revision = "0144_affairs_leave_identity_cutover"
down_revision = "0143_merge_affairs_material_ops"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "t_cs_leave",
        "cs_student_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade():
    # Historical rows retain their original value. New rows created after the cutover
    # intentionally have NULL here, so a safe downgrade must map only those rows to the
    # old sentinel before restoring NOT NULL.
    op.execute("UPDATE t_cs_leave SET cs_student_id = 0 WHERE cs_student_id IS NULL")
    op.alter_column(
        "t_cs_leave",
        "cs_student_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
