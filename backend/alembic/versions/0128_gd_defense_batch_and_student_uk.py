"""毕设：答辩组 batch_id + 同批组名唯一；学生同批同生唯一。

回填原则：
- 组内学生同属一批 → 写入该 batch_id；
- 空组或跨批 → 挂到该租户最新非作废批次（无批次则保留 NULL）；
- 同批重名组追加后缀后再建唯一约束；
- 学生同批重复 ACTIVE 档：保留最小 id，其余软删（不物理删除）。

Revision ID: 0128_gd_defense_batch_student_uk
Revises: 0127_affairs_risk_list_indexes
"""
from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0128_gd_defense_batch_student_uk"
down_revision = "0127_affairs_risk_list_indexes"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.0128_gd_defense_batch")


def _has_column(insp, table: str, col: str) -> bool:
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == col for c in insp.get_columns(table))


def _has_uk(insp, table: str, name: str) -> bool:
    if table not in insp.get_table_names():
        return False
    return any(uk.get("name") == name for uk in insp.get_unique_constraints(table))


def _has_index(insp, table: str, name: str) -> bool:
    if table not in insp.get_table_names():
        return False
    return any(ix.get("name") == name for ix in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    dialect = bind.dialect.name

    # ── 1) 答辩组 batch_id ──
    if "t_gd_defense_group" in insp.get_table_names() and not _has_column(insp, "t_gd_defense_group", "batch_id"):
        op.add_column(
            "t_gd_defense_group",
            sa.Column("batch_id", sa.BigInteger(), nullable=True, comment="毕设批次 t_gd_batch.id"),
        )
        op.create_index("ix_gd_defense_group_batch_id", "t_gd_defense_group", ["batch_id"])

    insp = inspect(bind)
    if "t_gd_defense_group" in insp.get_table_names() and _has_column(insp, "t_gd_defense_group", "batch_id"):
        # 同批学生 → 回填
        bind.execute(text("""
            UPDATE t_gd_defense_group g
            INNER JOIN (
                SELECT defense_group_id AS gid, MIN(batch_id) AS bid, COUNT(DISTINCT batch_id) AS bc
                FROM t_gd_student
                WHERE is_deleted = 0 AND defense_group_id IS NOT NULL AND batch_id IS NOT NULL
                GROUP BY defense_group_id
                HAVING COUNT(DISTINCT batch_id) = 1
            ) x ON x.gid = g.id
            SET g.batch_id = x.bid
            WHERE g.batch_id IS NULL AND g.is_deleted = 0
        """) if dialect == "mysql" else text("""
            UPDATE t_gd_defense_group
            SET batch_id = (
                SELECT MIN(s.batch_id) FROM t_gd_student s
                WHERE s.defense_group_id = t_gd_defense_group.id
                  AND s.is_deleted = 0 AND s.batch_id IS NOT NULL
                GROUP BY s.defense_group_id
                HAVING COUNT(DISTINCT s.batch_id) = 1
            )
            WHERE batch_id IS NULL AND is_deleted = 0
              AND id IN (
                SELECT defense_group_id FROM t_gd_student
                WHERE is_deleted = 0 AND defense_group_id IS NOT NULL AND batch_id IS NOT NULL
                GROUP BY defense_group_id
                HAVING COUNT(DISTINCT batch_id) = 1
              )
        """))

        # 空组 / 跨批：挂租户最新非 VOIDED 批次
        if dialect == "mysql":
            bind.execute(text("""
                UPDATE t_gd_defense_group g
                INNER JOIN (
                    SELECT tenant_id, MAX(id) AS bid
                    FROM t_gd_batch
                    WHERE is_deleted = 0 AND status NOT IN ('VOIDED')
                    GROUP BY tenant_id
                ) b ON b.tenant_id = g.tenant_id
                SET g.batch_id = b.bid
                WHERE g.batch_id IS NULL AND g.is_deleted = 0
            """))
        else:
            bind.execute(text("""
                UPDATE t_gd_defense_group
                SET batch_id = (
                    SELECT MAX(b.id) FROM t_gd_batch b
                    WHERE b.tenant_id = t_gd_defense_group.tenant_id
                      AND b.is_deleted = 0 AND b.status NOT IN ('VOIDED')
                )
                WHERE batch_id IS NULL AND is_deleted = 0
            """))

        # 异常清单（仅日志，不阻断）
        anomalies = bind.execute(text("""
            SELECT g.id, g.tenant_id, g.group_name, COUNT(DISTINCT s.batch_id) AS batch_cnt
            FROM t_gd_defense_group g
            LEFT JOIN t_gd_student s
              ON s.defense_group_id = g.id AND s.is_deleted = 0 AND s.batch_id IS NOT NULL
            WHERE g.is_deleted = 0
            GROUP BY g.id, g.tenant_id, g.group_name
            HAVING COUNT(DISTINCT s.batch_id) > 1
        """)).fetchall()
        for row in anomalies:
            log.warning(
                "defense_group cross-batch anomaly id=%s tenant=%s name=%s distinct_batches=%s (kept default batch)",
                row[0], row[1], row[2], row[3],
            )

        # 同批重名：保留最小 id，其余改名
        dups = bind.execute(text("""
            SELECT tenant_id, batch_id, group_name, COUNT(*) AS c
            FROM t_gd_defense_group
            WHERE is_deleted = 0 AND batch_id IS NOT NULL
            GROUP BY tenant_id, batch_id, group_name
            HAVING COUNT(*) > 1
        """)).fetchall()
        for tenant_id, batch_id, group_name, _c in dups:
            ids = [r[0] for r in bind.execute(text("""
                SELECT id FROM t_gd_defense_group
                WHERE tenant_id = :tid AND batch_id = :bid AND group_name = :name
                  AND is_deleted = 0
                ORDER BY id ASC
            """), {"tid": tenant_id, "bid": batch_id, "name": group_name}).fetchall()]
            for extra_id in ids[1:]:
                new_name = f"{group_name}#{extra_id}"
                if len(new_name) > 50:
                    new_name = new_name[:50]
                bind.execute(text("""
                    UPDATE t_gd_defense_group SET group_name = :name WHERE id = :id
                """), {"name": new_name, "id": extra_id})
                log.warning("renamed duplicate defense group id=%s -> %s", extra_id, new_name)

        insp = inspect(bind)
        if not _has_index(insp, "t_gd_defense_group", "ix_gd_defense_tenant_batch"):
            op.create_index(
                "ix_gd_defense_tenant_batch", "t_gd_defense_group",
                ["tenant_id", "batch_id", "is_deleted"],
            )
        if not _has_uk(insp, "t_gd_defense_group", "uk_gd_defense_tenant_batch_name"):
            op.create_unique_constraint(
                "uk_gd_defense_tenant_batch_name", "t_gd_defense_group",
                ["tenant_id", "batch_id", "group_name"],
            )

    # ── 2) 学生同批同生唯一 ──
    if "t_gd_student" in insp.get_table_names():
        dups = bind.execute(text("""
            SELECT tenant_id, batch_id, student_id, COUNT(*) AS c
            FROM t_gd_student
            WHERE is_deleted = 0 AND batch_id IS NOT NULL AND student_id IS NOT NULL
              AND record_status = 'ACTIVE'
            GROUP BY tenant_id, batch_id, student_id
            HAVING COUNT(*) > 1
        """)).fetchall()
        soft_n = 0
        for tenant_id, batch_id, student_id, _c in dups:
            ids = [r[0] for r in bind.execute(text("""
                SELECT id FROM t_gd_student
                WHERE tenant_id = :tid AND batch_id = :bid AND student_id = :sid
                  AND is_deleted = 0 AND record_status = 'ACTIVE'
                ORDER BY id ASC
            """), {"tid": tenant_id, "bid": batch_id, "sid": student_id}).fetchall()]
            for extra_id in ids[1:]:
                bind.execute(text("""
                    UPDATE t_gd_student
                    SET is_deleted = 1, record_status = 'VOIDED',
                        void_reason = COALESCE(void_reason, '0128 duplicate tenant+batch+student soft-void')
                    WHERE id = :id
                """), {"id": extra_id})
                soft_n += 1
        if soft_n:
            log.warning("soft-voided %s duplicate gd_student ACTIVE rows before UK", soft_n)

        insp = inspect(bind)
        if not _has_uk(insp, "t_gd_student", "uk_gd_student_tenant_batch_sid"):
            op.create_unique_constraint(
                "uk_gd_student_tenant_batch_sid", "t_gd_student",
                ["tenant_id", "batch_id", "student_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if _has_uk(insp, "t_gd_student", "uk_gd_student_tenant_batch_sid"):
        op.drop_constraint("uk_gd_student_tenant_batch_sid", "t_gd_student", type_="unique")
    if _has_uk(insp, "t_gd_defense_group", "uk_gd_defense_tenant_batch_name"):
        op.drop_constraint("uk_gd_defense_tenant_batch_name", "t_gd_defense_group", type_="unique")
    if _has_index(insp, "t_gd_defense_group", "ix_gd_defense_tenant_batch"):
        op.drop_index("ix_gd_defense_tenant_batch", table_name="t_gd_defense_group")
    if _has_column(insp, "t_gd_defense_group", "batch_id"):
        if _has_index(insp, "t_gd_defense_group", "ix_gd_defense_group_batch_id"):
            op.drop_index("ix_gd_defense_group_batch_id", table_name="t_gd_defense_group")
        op.drop_column("t_gd_defense_group", "batch_id")
