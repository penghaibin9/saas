"""毕设风险：生命周期字段 + 批次扫描摘要（不拆 uk_gd_risk_case）。

Revision ID: 0130_gd_risk_reopen_lifecycle
Revises: 0129_gd_stable_mentor_ids
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0130_gd_risk_reopen_lifecycle"
down_revision = "0129_gd_stable_mentor_ids"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, col: str) -> bool:
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == col for c in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "t_gd_risk_case" in insp.get_table_names():
        cols = [
            ("first_detected_at", sa.Column("first_detected_at", sa.DateTime(), nullable=True, comment="首次触发")),
            ("last_detected_at", sa.Column("last_detected_at", sa.DateTime(), nullable=True, comment="最近仍命中")),
            ("reopen_count", sa.Column("reopen_count", sa.Integer(), nullable=False, server_default="0", comment="重开次数")),
            ("last_reopened_at", sa.Column("last_reopened_at", sa.DateTime(), nullable=True, comment="最近重开")),
            ("condition_active", sa.Column("condition_active", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="最近扫描是否仍命中")),
            ("condition_summary", sa.Column("condition_summary", sa.String(500), nullable=True, comment="条件摘要")),
            ("condition_hash", sa.Column("condition_hash", sa.String(64), nullable=True, comment="条件指纹")),
        ]
        for name, col in cols:
            if not _has_column(insp, "t_gd_risk_case", name):
                op.add_column("t_gd_risk_case", col)
                insp = inspect(bind)
        # 回填：首次/最近检测 ← detected_at
        bind.execute(text(
            "UPDATE t_gd_risk_case SET first_detected_at = COALESCE(first_detected_at, detected_at, created_at), "
            "last_detected_at = COALESCE(last_detected_at, detected_at, created_at) "
            "WHERE is_deleted = 0"
        ))

    if "t_gd_batch" in insp.get_table_names():
        if not _has_column(insp, "t_gd_batch", "last_risk_scan_at"):
            op.add_column("t_gd_batch", sa.Column("last_risk_scan_at", sa.DateTime(), nullable=True))
        if not _has_column(insp, "t_gd_batch", "last_risk_scan_stats_json"):
            op.add_column("t_gd_batch", sa.Column("last_risk_scan_stats_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    for table, cols in (
        ("t_gd_batch", ["last_risk_scan_stats_json", "last_risk_scan_at"]),
        ("t_gd_risk_case", [
            "condition_hash", "condition_summary", "condition_active",
            "last_reopened_at", "reopen_count", "last_detected_at", "first_detected_at",
        ]),
    ):
        if table not in insp.get_table_names():
            continue
        for c in cols:
            if _has_column(insp, table, c):
                op.drop_column(table, c)
            insp = inspect(bind)
