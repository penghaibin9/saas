"""Add evidence, geofence and appeal fields for trusted internship check-ins.

Revision ID: 0050_internship_trusted_checkin
Revises: 0049_internship_rule_score_snapshots
Create Date: 2026-07-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0050_internship_trusted_checkin"
down_revision = "0049_internship_rule_score_snapshots"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    inspector = inspect(bind)
    return ({x["name"] for x in inspector.get_columns(table)}
            if table in inspector.get_table_names() else set())


def _add(table: str, column: sa.Column) -> None:
    cols = _columns(op.get_bind(), table)
    # 表已存在才补列；缺失表（全新库）交由 0053 基线迁移建全量结构，避免对缺失表 add_column 崩溃。
    if cols and column.name not in cols:
        op.add_column(table, column)


def upgrade() -> None:
    _add("t_internship_position", sa.Column("geofence_lat", sa.Float(), nullable=True))
    _add("t_internship_position", sa.Column("geofence_lng", sa.Float(), nullable=True))
    _add("t_internship_position", sa.Column("geofence_radius_m", sa.Integer(), nullable=True))
    _add("t_internship_checkin", sa.Column("gps_accuracy", sa.Float(), nullable=True))
    _add("t_internship_checkin", sa.Column("device_risk_flag", sa.String(length=30), nullable=True))
    _add("t_internship_checkin", sa.Column("distance_m", sa.Float(), nullable=True))
    _add("t_internship_checkin", sa.Column("evidence_file_id", sa.String(length=64), nullable=True))
    _add("t_internship_checkin", sa.Column("idempotency_key", sa.String(length=100), nullable=True))
    _add("t_attendance_exception", sa.Column("appeal_status", sa.String(length=30), nullable=True))
    _add("t_attendance_exception", sa.Column("appeal_note", sa.String(length=1000), nullable=True))
    _add("t_attendance_exception", sa.Column("appeal_file_id", sa.String(length=64), nullable=True))
    _add("t_attendance_exception", sa.Column("appealed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for table, column in (
        ("t_attendance_exception", "appealed_at"), ("t_attendance_exception", "appeal_file_id"),
        ("t_attendance_exception", "appeal_note"), ("t_attendance_exception", "appeal_status"),
        ("t_internship_checkin", "idempotency_key"), ("t_internship_checkin", "evidence_file_id"),
        ("t_internship_checkin", "distance_m"), ("t_internship_checkin", "device_risk_flag"),
        ("t_internship_checkin", "gps_accuracy"), ("t_internship_position", "geofence_radius_m"),
        ("t_internship_position", "geofence_lng"), ("t_internship_position", "geofence_lat"),
    ):
        if column in _columns(op.get_bind(), table):
            op.drop_column(table, column)
