"""internship position rights facts and nullable tri-state flags

Revision ID: 0138_intern_position_facts
Revises: 0137_intern_role_closure

兼容说明：0001 历史迁移会导入运行时当前 metadata，空库升级时这些列可能已提前
创建，故先探测再加列（同 0103/0104/0105 约定）。
"""
from alembic import op
import sqlalchemy as sa

revision = "0138_intern_position_facts"
down_revision = "0137_intern_role_closure"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return set()
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def upgrade():
    existing = _column_names("t_internship_position")
    for name, col in (
        ("work_address", sa.String(300)),
        ("rest_days_per_week", sa.Float()),
        ("rights_status", sa.String(30)),
        ("rights_checked_at", sa.DateTime()),
        ("rights_rule_version", sa.String(64)),
    ):
        if name not in existing:
            op.add_column("t_internship_position", sa.Column(name, col, nullable=True))
    for name in (
        "night_shift", "overtime_allowed", "accommodation_provided",
        "meal_provided", "hazardous_flag",
    ):
        op.alter_column(
            "t_internship_position", name, existing_type=sa.Boolean(),
            nullable=True, server_default=None,
        )


def downgrade():
    # 不把历史 UNKNOWN 猜成 false；降级前若存在 NULL 应由运维显式处理。
    for name in (
        "rights_rule_version", "rights_checked_at", "rights_status",
        "rest_days_per_week", "work_address",
    ):
        op.drop_column("t_internship_position", name)
