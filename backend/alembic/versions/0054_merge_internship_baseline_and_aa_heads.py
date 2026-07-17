"""统一 alembic 多 head：岗位实习核心表基线(0053) × 教务调度/分层链(aa_merge_scheduling_and_tier_chains)。

背景：master 在本次实习修复并入前即已是双 alembic head（原 aa_sandbox_baseline 与
aa_merge_scheduling_and_tier_chains 两条并行链，教务多波并行工作遗留）。双 head 下
`alembic upgrade head` 会因 head 不唯一而报错、无法一键建/升库。本次实习修复的 0053 基线
接在 aa_sandbox_baseline 之后成为其一 head；此迁移把两条 head 合并为单一 head，使干净库
`alembic upgrade head` 可一次跑通。

纯链路合并，无任何 schema 变更（upgrade/downgrade 均为空），不影响任一域已建表结构。

Revision ID: 0054_merge_internship_aa_heads
Revises: 0053_internship_core_baseline, aa_merge_scheduling_and_tier_chains
Create Date: 2026-07-17
"""
from __future__ import annotations

revision = "0054_merge_internship_aa_heads"
down_revision = ("0053_internship_core_baseline", "aa_merge_scheduling_and_tier_chains")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 仅统一迁移历史的两条 head，无 DDL。
    pass


def downgrade() -> None:
    # 合并迁移的回退即回到两条独立 head，无 DDL。
    pass
