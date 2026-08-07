"""包 10：资助金额真值、批准快照与并发额度原子占用。

Revision ID: 20260806_funding_pkg10
Revises: 20260806_gd_pkg9_archive_ver
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260806_funding_pkg10"
down_revision = "20260806_gd_pkg9_archive_ver"
branch_labels = None
depends_on = None

assert len(revision) <= 32

_BATCH = "t_affairs_funding_batch"
_APP = "t_affairs_funding_application"
_DISB = "t_affairs_funding_disbursement"
_PROJECT = "t_affairs_funding_project"

_TRIGGERS = (
    "trg_funding_batch_bi_pkg10",
    "trg_funding_batch_bu_pkg10",
    "trg_funding_app_bi_pkg10",
    "trg_funding_app_bu_pkg10",
    "trg_funding_disb_bi_pkg10",
    "trg_funding_disb_bu_pkg10",
)


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260806_funding_pkg10 requires MySQL")


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def _drop_trigger(name: str) -> None:
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS `{name}`"))


def _create_triggers() -> None:
    for trigger in _TRIGGERS:
        _drop_trigger(trigger)

    op.execute(sa.text("""
        CREATE TRIGGER trg_funding_batch_bi_pkg10
        BEFORE INSERT ON t_affairs_funding_batch
        FOR EACH ROW
        BEGIN
            DECLARE v_project_amount DECIMAL(16,2);
            SET NEW.reserved_quota = COALESCE(NEW.reserved_quota, 0);
            SET NEW.reserved_amount = COALESCE(NEW.reserved_amount, 0.00);
            IF NEW.amount_budget IS NULL AND NEW.quota IS NOT NULL THEN
                SET v_project_amount = (
                    SELECT p.amount
                    FROM t_affairs_funding_project p
                    WHERE p.id = NEW.project_id
                      AND p.tenant_id = NEW.tenant_id
                      AND p.is_deleted = 0
                    LIMIT 1
                );
                IF v_project_amount IS NOT NULL THEN
                    SET NEW.amount_budget = NEW.quota * v_project_amount;
                END IF;
            END IF;
        END
    """))

    op.execute(sa.text("""
        CREATE TRIGGER trg_funding_batch_bu_pkg10
        BEFORE UPDATE ON t_affairs_funding_batch
        FOR EACH ROW
        BEGIN
            DECLARE v_project_amount DECIMAL(16,2);
            SET NEW.reserved_quota = COALESCE(NEW.reserved_quota, 0);
            SET NEW.reserved_amount = COALESCE(NEW.reserved_amount, 0.00);
            IF NEW.amount_budget IS NULL AND NEW.quota IS NOT NULL THEN
                SET v_project_amount = (
                    SELECT p.amount
                    FROM t_affairs_funding_project p
                    WHERE p.id = NEW.project_id
                      AND p.tenant_id = NEW.tenant_id
                      AND p.is_deleted = 0
                    LIMIT 1
                );
                IF v_project_amount IS NOT NULL THEN
                    SET NEW.amount_budget = NEW.quota * v_project_amount;
                END IF;
            END IF;
            IF NEW.reserved_quota < 0 OR NEW.reserved_amount < 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_RESERVED_VALUE_INVALID';
            END IF;
            IF NEW.quota IS NOT NULL AND NEW.reserved_quota > NEW.quota THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_QUOTA_EXCEEDED';
            END IF;
            IF NEW.amount_budget IS NOT NULL AND NEW.reserved_amount > NEW.amount_budget THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_AMOUNT_BUDGET_EXCEEDED';
            END IF;
        END
    """))

    op.execute(sa.text("""
        CREATE TRIGGER trg_funding_app_bi_pkg10
        BEFORE INSERT ON t_affairs_funding_application
        FOR EACH ROW
        BEGIN
            DECLARE v_project_amount DECIMAL(16,2);
            SET v_project_amount = (
                SELECT p.amount
                FROM t_affairs_funding_batch b
                JOIN t_affairs_funding_project p
                  ON p.id = b.project_id
                 AND p.tenant_id = b.tenant_id
                 AND p.is_deleted = 0
                WHERE b.id = NEW.batch_id
                  AND b.tenant_id = NEW.tenant_id
                  AND b.is_deleted = 0
                LIMIT 1
            );
            SET NEW.requested_amount = COALESCE(NEW.requested_amount, NEW.amount, v_project_amount);
            SET NEW.quota_reserved = COALESCE(NEW.quota_reserved, 0);
            IF NEW.requested_amount IS NULL OR NEW.requested_amount <= 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_REQUESTED_AMOUNT_INVALID';
            END IF;
            IF NEW.status = 'GRANTED' THEN
                SET NEW.approved_amount = COALESCE(NEW.approved_amount, NEW.amount, NEW.requested_amount);
                IF NEW.approved_amount IS NULL OR NEW.approved_amount <= 0
                   OR NEW.approved_amount > NEW.requested_amount THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'FUNDING_APPROVED_AMOUNT_INVALID';
                END IF;
                UPDATE t_affairs_funding_batch
                   SET reserved_quota = COALESCE(reserved_quota, 0) + 1,
                       reserved_amount = COALESCE(reserved_amount, 0.00) + NEW.approved_amount
                 WHERE id = NEW.batch_id
                   AND tenant_id = NEW.tenant_id
                   AND is_deleted = 0
                   AND (quota IS NULL OR COALESCE(reserved_quota, 0) + 1 <= quota)
                   AND (amount_budget IS NULL
                        OR COALESCE(reserved_amount, 0.00) + NEW.approved_amount <= amount_budget);
                IF ROW_COUNT() <> 1 THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'FUNDING_QUOTA_OR_BUDGET_EXCEEDED';
                END IF;
                SET NEW.quota_reserved = 1;
                SET NEW.approved_at = COALESCE(NEW.approved_at, CURRENT_TIMESTAMP);
            END IF;
        END
    """))

    op.execute(sa.text("""
        CREATE TRIGGER trg_funding_app_bu_pkg10
        BEFORE UPDATE ON t_affairs_funding_application
        FOR EACH ROW
        BEGIN
            SET NEW.requested_amount = COALESCE(NEW.requested_amount, OLD.requested_amount, NEW.amount);
            IF NEW.requested_amount IS NULL OR NEW.requested_amount <= 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_REQUESTED_AMOUNT_INVALID';
            END IF;
            IF OLD.quota_reserved = 1 THEN
                IF NOT (NEW.approved_amount <=> OLD.approved_amount)
                   OR NOT (NEW.approved_at <=> OLD.approved_at) THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'FUNDING_APPROVAL_FACT_IMMUTABLE';
                END IF;
                SET NEW.quota_reserved = 1;
            ELSEIF NEW.status = 'GRANTED' AND OLD.status <> 'GRANTED' THEN
                SET NEW.approved_amount = COALESCE(NEW.approved_amount, NEW.amount, NEW.requested_amount);
                IF NEW.approved_amount IS NULL OR NEW.approved_amount <= 0
                   OR NEW.approved_amount > NEW.requested_amount THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'FUNDING_APPROVED_AMOUNT_INVALID';
                END IF;
                UPDATE t_affairs_funding_batch
                   SET reserved_quota = COALESCE(reserved_quota, 0) + 1,
                       reserved_amount = COALESCE(reserved_amount, 0.00) + NEW.approved_amount
                 WHERE id = NEW.batch_id
                   AND tenant_id = NEW.tenant_id
                   AND is_deleted = 0
                   AND (quota IS NULL OR COALESCE(reserved_quota, 0) + 1 <= quota)
                   AND (amount_budget IS NULL
                        OR COALESCE(reserved_amount, 0.00) + NEW.approved_amount <= amount_budget);
                IF ROW_COUNT() <> 1 THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'FUNDING_QUOTA_OR_BUDGET_EXCEEDED';
                END IF;
                SET NEW.quota_reserved = 1;
                SET NEW.approved_at = COALESCE(NEW.approved_at, CURRENT_TIMESTAMP);
            END IF;
        END
    """))

    op.execute(sa.text("""
        CREATE TRIGGER trg_funding_disb_bi_pkg10
        BEFORE INSERT ON t_affairs_funding_disbursement
        FOR EACH ROW
        BEGIN
            DECLARE v_approved_amount DECIMAL(16,2);
            DECLARE v_approved_at DATETIME;
            DECLARE v_approval_version INT;
            SELECT a.approved_amount, a.approved_at, a.version
              INTO v_approved_amount, v_approved_at, v_approval_version
              FROM t_affairs_funding_application a
             WHERE a.id = NEW.application_id
               AND a.tenant_id = NEW.tenant_id
               AND a.is_deleted = 0
               AND a.quota_reserved = 1
             LIMIT 1;
            IF v_approved_amount IS NULL THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_APPROVAL_SNAPSHOT_MISSING';
            END IF;
            SET NEW.approved_amount_snapshot = v_approved_amount;
            SET NEW.approved_at_snapshot = v_approved_at;
            SET NEW.approval_version_snapshot = v_approval_version;
            SET NEW.amount = v_approved_amount;
        END
    """))

    op.execute(sa.text("""
        CREATE TRIGGER trg_funding_disb_bu_pkg10
        BEFORE UPDATE ON t_affairs_funding_disbursement
        FOR EACH ROW
        BEGIN
            IF NOT (NEW.approved_amount_snapshot <=> OLD.approved_amount_snapshot)
               OR NOT (NEW.approved_at_snapshot <=> OLD.approved_at_snapshot)
               OR NOT (NEW.approval_version_snapshot <=> OLD.approval_version_snapshot) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_DISBURSEMENT_SNAPSHOT_IMMUTABLE';
            END IF;
            SET NEW.amount = OLD.approved_amount_snapshot;
        END
    """))


def upgrade() -> None:
    _require_mysql()

    _add_column(_BATCH, sa.Column("amount_budget", sa.Numeric(16, 2), nullable=True,
                                  comment="批次金额额度；默认按名额×项目标准金额生成"))
    _add_column(_BATCH, sa.Column("reserved_quota", sa.Integer(), nullable=False,
                                  server_default=sa.text("0"), comment="已原子占用名额"))
    _add_column(_BATCH, sa.Column("reserved_amount", sa.Numeric(16, 2), nullable=False,
                                  server_default=sa.text("0.00"), comment="已原子占用金额"))

    _add_column(_APP, sa.Column("requested_amount", sa.Numeric(14, 2), nullable=True,
                                comment="申请金额真值；与批准金额分离"))
    _add_column(_APP, sa.Column("approved_amount", sa.Numeric(14, 2), nullable=True,
                                comment="最终批准金额真值；占用额度后不可修改"))
    _add_column(_APP, sa.Column("approved_at", sa.DateTime(), nullable=True,
                                comment="最终批准事实时间"))
    _add_column(_APP, sa.Column("quota_reserved", sa.Boolean(), nullable=False,
                                server_default=sa.text("0"), comment="名额与金额额度是否已占用"))

    _add_column(_DISB, sa.Column("approved_amount_snapshot", sa.Numeric(14, 2), nullable=True,
                                 comment="发放时冻结的批准金额"))
    _add_column(_DISB, sa.Column("approved_at_snapshot", sa.DateTime(), nullable=True,
                                 comment="发放时冻结的批准时间"))
    _add_column(_DISB, sa.Column("approval_version_snapshot", sa.Integer(), nullable=True,
                                 comment="发放时冻结的申请版本"))

    op.execute(sa.text("""
        UPDATE t_affairs_funding_batch b
        JOIN t_affairs_funding_project p
          ON p.id = b.project_id
         AND p.tenant_id = b.tenant_id
         AND p.is_deleted = 0
           SET b.amount_budget = COALESCE(b.amount_budget,
                                         CASE WHEN b.quota IS NULL OR p.amount IS NULL
                                              THEN NULL ELSE b.quota * p.amount END),
               b.reserved_quota = COALESCE(b.reserved_quota, 0),
               b.reserved_amount = COALESCE(b.reserved_amount, 0.00)
         WHERE b.is_deleted = 0
    """))

    op.execute(sa.text("""
        UPDATE t_affairs_funding_application a
        JOIN t_affairs_funding_batch b
          ON b.id = a.batch_id
         AND b.tenant_id = a.tenant_id
         AND b.is_deleted = 0
        LEFT JOIN t_affairs_funding_project p
          ON p.id = b.project_id
         AND p.tenant_id = b.tenant_id
         AND p.is_deleted = 0
           SET a.requested_amount = COALESCE(a.requested_amount, a.amount, p.amount),
               a.approved_amount = CASE
                   WHEN a.status = 'GRANTED'
                   THEN COALESCE(a.approved_amount, a.amount, p.amount)
                   ELSE a.approved_amount
               END,
               a.approved_at = CASE
                   WHEN a.status = 'GRANTED'
                   THEN COALESCE(a.approved_at, a.result_at, a.updated_at, a.created_at)
                   ELSE a.approved_at
               END,
               a.quota_reserved = CASE WHEN a.status = 'GRANTED' THEN 1 ELSE 0 END
         WHERE a.is_deleted = 0
    """))

    op.execute(sa.text("""
        UPDATE t_affairs_funding_batch b
        LEFT JOIN (
            SELECT tenant_id, batch_id,
                   COUNT(*) AS used_quota,
                   COALESCE(SUM(approved_amount), 0.00) AS used_amount
              FROM t_affairs_funding_application
             WHERE is_deleted = 0 AND quota_reserved = 1
             GROUP BY tenant_id, batch_id
        ) r ON r.tenant_id = b.tenant_id AND r.batch_id = b.id
           SET b.reserved_quota = COALESCE(r.used_quota, 0),
               b.reserved_amount = COALESCE(r.used_amount, 0.00)
         WHERE b.is_deleted = 0
    """))

    op.execute(sa.text("""
        UPDATE t_affairs_funding_disbursement d
        JOIN t_affairs_funding_application a
          ON a.id = d.application_id
         AND a.tenant_id = d.tenant_id
         AND a.is_deleted = 0
           SET d.approved_amount_snapshot = COALESCE(d.approved_amount_snapshot,
                                                     a.approved_amount, a.amount, d.amount),
               d.approved_at_snapshot = COALESCE(d.approved_at_snapshot,
                                                 a.approved_at, a.result_at),
               d.approval_version_snapshot = COALESCE(d.approval_version_snapshot, a.version),
               d.amount = COALESCE(a.approved_amount, a.amount, d.amount)
         WHERE d.is_deleted = 0
    """))

    _create_triggers()


def downgrade() -> None:
    _require_mysql()
    for trigger in _TRIGGERS:
        _drop_trigger(trigger)

    for table, columns in (
        (_DISB, ("approval_version_snapshot", "approved_at_snapshot", "approved_amount_snapshot")),
        (_APP, ("quota_reserved", "approved_at", "approved_amount", "requested_amount")),
        (_BATCH, ("reserved_amount", "reserved_quota", "amount_budget")),
    ):
        existing = _columns(table)
        for column in columns:
            if column in existing:
                op.drop_column(table, column)
