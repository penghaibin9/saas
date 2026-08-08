"""P0-D06：免修材料证据链冻结。

免修终审直接生成正式及格成绩，材料就是这门学分的唯一依据。此前只校验"文件ID属于本租户"：
学生 B 知道学生 A 的 fileId 就能拿来当自己的免修依据；审批期间文件被撤换、隔离也无人察觉。
本迁移给免修申请加证据清单与其哈希，申请时冻结、终审前重新比对。

存量行不回填（历史申请没有绑定关系可冻结），服务层对空清单按"无材料"处理，不假装已核验。

Revision ID: 20260807_aa_exempt_ev
Revises: 20260807_aa_sched_head
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260807_aa_exempt_ev"
down_revision = "20260807_aa_sched_head"
branch_labels = None
depends_on = None

assert len(revision) <= 32

_TABLE = "t_aa_exemption"


def _has_column(bind, table: str, column: str) -> bool:
    insp = inspect(bind)
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, _TABLE, "evidence_manifest_json"):
        op.add_column(_TABLE, sa.Column(
            "evidence_manifest_json", sa.String(4000), nullable=True,
            comment="申请时冻结的材料证据清单：bindingId/fileId/version/sha256/owner/boundAt"))
    if not _has_column(bind, _TABLE, "evidence_manifest_hash"):
        op.add_column(_TABLE, sa.Column(
            "evidence_manifest_hash", sa.String(64), nullable=True,
            comment="证据清单 sha256；终审前重算比对，不一致即判证据失效"))


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, _TABLE, "evidence_manifest_hash"):
        op.drop_column(_TABLE, "evidence_manifest_hash")
    if _has_column(bind, _TABLE, "evidence_manifest_json"):
        op.drop_column(_TABLE, "evidence_manifest_json")
