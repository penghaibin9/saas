"""P0-D05：课表唯一正式版本（范围头 + 顶替链）。

同一(学期,范围)在任一时刻只能有一份正式课表。此前同学期可以并存多个 PUBLISHED 批次，
「学生的正式课表是哪一份」没有答案；本迁移建 t_aa_schedule_scope_head 唯一回答这个问题，
并给批次表加 supersedes_batch_id 记录顶替链。

存量数据回填：对每个(学期,范围)取当前 id 最大的 PUBLISHED 批次作为 active，其余同范围
PUBLISHED 批次一律标 SUPERSEDED——不猜业务意图，只保留最新一份为正式，历史批次仍可查。

Revision ID: 20260807_aa_sched_head
Revises: 20260806_discipline_pkg11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260807_aa_sched_head"
down_revision = "20260806_discipline_pkg11"
branch_labels = None
depends_on = None

assert len(revision) <= 32

_HEAD = "t_aa_schedule_scope_head"
_BATCH = "t_aa_schedule_batch"


def _has_table(bind, name: str) -> bool:
    return inspect(bind).has_table(name)


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return False
    return any(col["name"] == column for col in inspect(bind).get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, _HEAD):
        op.create_table(
            _HEAD,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("term_id", sa.BigInteger(), nullable=False),
            sa.Column("scope_type", sa.String(20), nullable=False, server_default="SCHOOL"),
            sa.Column("scope_id", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("active_batch_id", sa.BigInteger(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.UniqueConstraint("tenant_id", "term_id", "scope_type", "scope_id",
                                name="uk_aa_schedule_scope_head"),
        )
        op.create_index("ix_aa_sched_head_term", _HEAD, ["term_id"])
        op.create_index("ix_aa_sched_head_active", _HEAD, ["active_batch_id"])

    if not _has_column(bind, _BATCH, "supersedes_batch_id"):
        op.add_column(_BATCH, sa.Column("supersedes_batch_id", sa.BigInteger(), nullable=True,
                                        comment="本批次发布时顶替掉的上一版正式课表批次"))
        op.create_index("ix_aa_sched_batch_supersedes", _BATCH, ["supersedes_batch_id"])

    # ── 存量回填：每个(租户,学期,范围)只留最新一份 PUBLISHED 作为 active ──
    scope_expr = "COALESCE(college_id, 0)"
    scope_type_expr = "CASE WHEN college_id IS NULL THEN 'SCHOOL' ELSE 'COLLEGE' END"
    rows = bind.execute(sa.text(
        f"SELECT tenant_id, term_id, {scope_type_expr} AS scope_type, {scope_expr} AS scope_id, "
        f"MAX(id) AS active_id, COUNT(*) AS total "
        f"FROM {_BATCH} WHERE status = 'PUBLISHED' AND is_deleted = 0 "
        f"GROUP BY tenant_id, term_id, {scope_type_expr}, {scope_expr}"
    )).mappings().all()
    for row in rows:
        bind.execute(sa.text(
            f"INSERT INTO {_HEAD} (tenant_id, term_id, scope_type, scope_id, active_batch_id, "
            f"version, is_deleted) VALUES (:tenant_id, :term_id, :scope_type, :scope_id, "
            f":active_id, 1, 0)"
        ), dict(row))
        if int(row["total"]) > 1:
            bind.execute(sa.text(
                f"UPDATE {_BATCH} SET status = 'SUPERSEDED' "
                f"WHERE tenant_id = :tenant_id AND term_id = :term_id AND status = 'PUBLISHED' "
                f"AND is_deleted = 0 AND {scope_expr} = :scope_id "
                f"AND {scope_type_expr} = :scope_type AND id <> :active_id"
            ), dict(row))


def downgrade() -> None:
    bind = op.get_bind()
    # 被顶替的批次还原成 PUBLISHED：回滚只撤销本迁移引入的状态，不删业务数据。
    if _has_table(bind, _BATCH):
        bind.execute(sa.text(
            f"UPDATE {_BATCH} SET status = 'PUBLISHED' WHERE status = 'SUPERSEDED' AND is_deleted = 0"
        ))
    if _has_column(bind, _BATCH, "supersedes_batch_id"):
        try:
            op.drop_index("ix_aa_sched_batch_supersedes", table_name=_BATCH)
        except Exception:  # noqa: BLE001  索引可能未建
            pass
        op.drop_column(_BATCH, "supersedes_batch_id")
    if _has_table(bind, _HEAD):
        op.drop_table(_HEAD)
