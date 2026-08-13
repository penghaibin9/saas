"""Enforce tenant-scoped uniqueness on internship incident idempotency keys.

``report_incident`` guards duplicates with an application-level
SELECT-then-INSERT, which two concurrent requests can both pass. The column
only carried a plain index, so nothing stopped the second writer. A duplicate
incident is not a harmless extra row: HIGH/CRITICAL severity derives a
``RiskRecord`` and every report writes an audit entry, so one slipped race
produces a duplicate incident, a duplicate risk and a duplicate audit trail.

Every other idempotent writer in this codebase already carries the same
constraint (``uk_aa_status_change_idem``, ``uk_campaign_tenant_idem``,
``uk_affairs_job_idem``); internship incidents were the outlier.

Pre-existing duplicates are preserved, never deleted — safety incident rows are
real business facts. The earliest row of each duplicate group keeps the key; the
later ones get their key suffixed with ``#dup<id>`` so the original value stays
readable and the row stays traceable, while the constraint can be created.

The suffix is appended to a *pre-truncated* key rather than truncating the
concatenation: a key already near the 80-char column limit would otherwise lose
the very suffix that makes it unique, and the constraint would still fail.

Revision ID: 20260813_ix_incident_idem
Revises: 20260810_grad_audit_text
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260813_ix_incident_idem"
down_revision = "20260810_grad_audit_text"
branch_labels = None
depends_on = None


TABLE = "t_internship_incident"
CONSTRAINT = "uk_ix_incident_idem"


def _has_constraint(bind) -> bool:
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return False
    names = {uc.get("name") for uc in inspector.get_unique_constraints(TABLE)}
    names.update(ix.get("name") for ix in inspector.get_indexes(TABLE) if ix.get("unique"))
    return CONSTRAINT in names


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    if _has_constraint(bind):
        return

    # 保留全部事故行：只把重复组里较晚的那些幂等键改写为可追溯的 #dup 变体。
    # 先按后缀长度截断原串再拼接，保证 #dup<id> 一定保留下来且总长不超过 VARCHAR(80)；
    # 若反过来对拼接结果做 LEFT()，接近上限的长键会被截掉后缀，改写后依旧重复。
    bind.execute(sa.text(
        """
        UPDATE t_internship_incident AS target
        JOIN (
            SELECT i.id AS id
            FROM t_internship_incident AS i
            JOIN (
                SELECT tenant_id, idempotency_key, MIN(id) AS keep_id
                FROM t_internship_incident
                WHERE idempotency_key IS NOT NULL AND idempotency_key <> ''
                GROUP BY tenant_id, idempotency_key
                HAVING COUNT(*) > 1
            ) AS dup
              ON dup.tenant_id = i.tenant_id
             AND dup.idempotency_key = i.idempotency_key
            WHERE i.id <> dup.keep_id
        ) AS losers ON losers.id = target.id
        SET target.idempotency_key = CONCAT(
            LEFT(target.idempotency_key,
                 80 - CHAR_LENGTH(CONCAT('#dup', target.id))),
            '#dup', target.id)
        """
    ))

    # 兜底核验：改写后仍存在重复说明数据形态超出预期（例如历史键本身就长得像 #dup 变体）。
    # 此时必须显式报错，而不是让 ALTER TABLE 抛出难以定位的 1062。
    leftover = bind.execute(sa.text(
        """
        SELECT COUNT(*) FROM (
            SELECT 1
            FROM t_internship_incident
            WHERE idempotency_key IS NOT NULL AND idempotency_key <> ''
            GROUP BY tenant_id, idempotency_key
            HAVING COUNT(*) > 1
        ) AS remaining
        """
    )).scalar()
    if leftover:
        raise RuntimeError(
            f"t_internship_incident 仍有 {leftover} 组重复 idempotency_key 无法自动消歧，"
            "请先人工核对这些事故行再重跑本迁移"
        )

    op.create_unique_constraint(
        CONSTRAINT, TABLE, ["tenant_id", "idempotency_key"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_constraint(bind):
        return
    op.drop_constraint(CONSTRAINT, TABLE, type_="unique")
