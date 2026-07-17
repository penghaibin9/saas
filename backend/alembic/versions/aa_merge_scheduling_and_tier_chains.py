"""合并教务中心两条并行 Alembic 链（P0 审计发现，2026-07-17）。

`0098_aa_workload_declaration` 所在的数字链（0009→…→0098）与 `aa_correction_material_r3`
所在的 Tier1/R2/R3 命名链，自 `aa_jxrw_tier1_r1` 起分叉后从未合并——两条链各自继续编号，
导致仓库同时存在两个不连通的 head。对全新库或已升级到任一条链头部的库执行
`alembic upgrade head` 会直接报 `CommandError: Multiple head revisions are present`。

本迁移只是把两个 head 声明为同一个合并点的两个 down_revision，不做任何表结构变更
（`upgrade`/`downgrade` 均为空操作），纯粹修复迁移图的连通性。

Revision ID: aa_merge_scheduling_and_tier_chains
Revises: 0098_aa_workload_declaration, aa_correction_material_r3
"""
from __future__ import annotations

revision = "aa_merge_scheduling_and_tier_chains"
down_revision = ("0098_aa_workload_declaration", "aa_correction_material_r3")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
