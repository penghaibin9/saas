"""internship position rights facts and nullable tri-state flags

Revision ID: 0138_intern_position_facts
Revises: 0137_intern_role_closure
"""
from alembic import op
import sqlalchemy as sa

revision = "0138_intern_position_facts"
down_revision = "0137_intern_role_closure"
branch_labels = None
depends_on = None


def upgrade():
    for name, col in (
        ("work_address", sa.String(300)),
        ("rest_days_per_week", sa.Float()),
        ("rights_status", sa.String(30)),
        ("rights_checked_at", sa.DateTime()),
        ("rights_rule_version", sa.String(64)),
    ):
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
