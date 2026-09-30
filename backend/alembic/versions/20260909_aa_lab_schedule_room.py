"""Explicit lab room mapping and approved-booking physical room snapshot."""
from alembic import op
import sqlalchemy as sa

revision = "20260909_aa_lab_schedule_room"
down_revision = "20260909_aa_change_authority"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("t_aa_lab_resource", "t_aa_lab_booking"):
        op.add_column(table, sa.Column("classroom_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_" + table + "_classroom_id", table, ["classroom_id"])


def downgrade():
    for table in ("t_aa_lab_booking", "t_aa_lab_resource"):
        op.drop_index("ix_" + table + "_classroom_id", table_name=table)
        op.drop_column(table, "classroom_id")
