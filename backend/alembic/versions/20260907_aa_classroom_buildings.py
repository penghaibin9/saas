"""Teaching buildings and explicit classroom floors; no inferred legacy location changes."""
from alembic import op
import sqlalchemy as sa

revision = "20260907_aa_classroom_buildings"
down_revision = "20260906_aa_org_adjust_snapshot"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("t_aa_teaching_building",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("building_code", sa.String(50), nullable=False),
        sa.Column("building_name", sa.String(100), nullable=False),
        sa.Column("campus_code", sa.String(50)),
        sa.Column("floor_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger()), sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "building_code", name="uk_aa_teaching_building"))
    op.create_index("ix_t_aa_teaching_building_tenant_id", "t_aa_teaching_building", ["tenant_id"])
    op.add_column("t_aa_classroom", sa.Column("building_id", sa.BigInteger(), nullable=True))
    op.add_column("t_aa_classroom", sa.Column("floor_no", sa.Integer(), nullable=True))
    op.create_index("ix_t_aa_classroom_building_id", "t_aa_classroom", ["building_id"])


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT COUNT(*) FROM t_aa_teaching_building")).scalar_one():
        raise RuntimeError("Teaching-building data exists; downgrade would lose locations.")
    op.drop_index("ix_t_aa_classroom_building_id", table_name="t_aa_classroom")
    op.drop_column("t_aa_classroom", "floor_no")
    op.drop_column("t_aa_classroom", "building_id")
    op.drop_table("t_aa_teaching_building")
