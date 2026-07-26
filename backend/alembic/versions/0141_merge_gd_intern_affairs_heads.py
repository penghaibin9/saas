"""Merge graduation, internship participant and affairs decimal migration heads.

Revision ID: 0141_merge_gd_intern_affairs_heads
Revises: gd_r3_audit_context, 0140_intern_batch_participant, 0139_affairs_money_decimal

Graph-only merge: all branch DDL remains intact while `alembic upgrade head`
returns to one deterministic head.
"""

revision = "0141_merge_gd_intern_affairs_heads"
down_revision = (
    "gd_r3_audit_context",
    "0140_intern_batch_participant",
    "0139_affairs_money_decimal",
)
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
