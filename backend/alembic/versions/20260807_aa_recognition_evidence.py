"""P0-D06 扩面：成绩认定佐证也进入正式学分证据链。

成绩认定终审和免修终审一样，会直接生成一条计学分的正式及格成绩，佐证就是这门学分的唯一依据。
原来两边都只校验"fileId 属于本租户"，同样敞着归属和时间差两个洞。本迁移给认定申请补上与免修
同构的证据清单列，服务层共用同一套守卫。

存量行不回填（历史申请没有绑定关系可冻结），服务层对空清单按"无佐证"处理，不假装已核验。

Revision ID: 20260807_aa_recog_ev
Revises: 20260807_aa_grade_head
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260807_aa_recog_ev"
down_revision = "20260807_aa_grade_head"
branch_labels = None
depends_on = None

assert len(revision) <= 32

_TABLE = "t_aa_grade_recognition"


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
            comment="申请时冻结的佐证证据清单：bindingId/fileId/version/sha256/owner/boundAt"))
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
