"""包 10 收口：项目标准金额、双人调整复核与最终原子占用。

Revision ID: 20260806_funding_pkg10_close
Revises: 20260806_aa_pkg1_change
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260806_funding_pkg10_close"
down_revision = "20260806_aa_pkg1_change"
branch_labels = None
depends_on = None

assert len(revision) <= 32

_ADJUST = "t_affairs_funding_amount_adjustment"
_APP_BI = "trg_funding_app_bi_pkg10"
_APP_BU = "trg_funding_app_bu_pkg10"
_ADJ_BI = "trg_funding_adjust_bi_pkg10"
_ADJ_BU = "trg_funding_adjust_bu_pkg10"
_TRIGGERS = (_APP_BI, _APP_BU, _ADJ_BI, _ADJ_BU)


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260806_funding_pkg10_close requires MySQL")


def _has_table(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def _drop_trigger(name: str) -> None:
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS `{name}`"))


def _create_adjustment_table() -> None:
    if _has_table(_ADJUST):
        return
    op.create_table(
        _ADJUST,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=False),
        sa.Column("requested_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("requester_id", sa.BigInteger(), nullable=False),
        sa.Column("requester_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewer_name", sa.String(100), nullable=True),
        sa.Column("review_reason", sa.String(500), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "pending_application_id", sa.BigInteger(),
            sa.Computed(
                "CASE WHEN status = 'PENDING' AND is_deleted = 0 THEN application_id ELSE NULL END",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["t_affairs_funding_application.id"],
            name="fk_funding_amount_adjust_app", ondelete="RESTRICT",
        ),
        sa.Index("ix_funding_amount_adjust_app", "tenant_id", "application_id", "status"),
        sa.UniqueConstraint(
            "tenant_id", "pending_application_id",
            name="uk_funding_amount_adjust_one_pending",
        ),
        mysql_engine="InnoDB",
        comment="资助批准金额人工调整双人复核台账",
    )


def _create_triggers() -> None:
    for name in _TRIGGERS:
        _drop_trigger(name)

    op.execute(sa.text("""
        CREATE TRIGGER trg_funding_adjust_bi_pkg10
        BEFORE INSERT ON t_affairs_funding_amount_adjustment
        FOR EACH ROW
        BEGIN
            DECLARE v_pending INT DEFAULT 0;
            DECLARE v_app_status VARCHAR(32);
            DECLARE v_reserved TINYINT DEFAULT 0;
            IF NEW.requested_amount IS NULL OR NEW.requested_amount <= 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_ADJUST_AMOUNT_INVALID';
            END IF;
            IF CHAR_LENGTH(TRIM(COALESCE(NEW.reason, ''))) < 5 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_ADJUST_REASON_REQUIRED';
            END IF;
            IF COALESCE(NEW.requester_id, 0) <= 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_ADJUST_REQUESTER_REQUIRED';
            END IF;
            SELECT a.status, a.quota_reserved
              INTO v_app_status, v_reserved
              FROM t_affairs_funding_application a
             WHERE a.id = NEW.application_id
               AND a.tenant_id = NEW.tenant_id
               AND a.is_deleted = 0
             LIMIT 1;
            IF v_app_status IS NULL
               OR v_app_status NOT IN ('SCHOOL_REVIEW', 'PUBLICITY')
               OR COALESCE(v_reserved, 0) = 1 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_ADJUST_STAGE_INVALID';
            END IF;
            SELECT COUNT(*)
              INTO v_pending
              FROM t_affairs_funding_amount_adjustment x
             WHERE x.tenant_id = NEW.tenant_id
               AND x.application_id = NEW.application_id
               AND x.status = 'PENDING'
               AND x.is_deleted = 0;
            IF v_pending > 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_ADJUST_PENDING_EXISTS';
            END IF;
            SET NEW.status = 'PENDING';
            SET NEW.reviewer_id = NULL;
            SET NEW.reviewer_name = NULL;
            SET NEW.review_reason = NULL;
            SET NEW.reviewed_at = NULL;
        END
    """))

    op.execute(sa.text("""
        CREATE TRIGGER trg_funding_adjust_bu_pkg10
        BEFORE UPDATE ON t_affairs_funding_amount_adjustment
        FOR EACH ROW
        BEGIN
            IF OLD.status <> 'PENDING' THEN
                IF NOT (NEW.status <=> OLD.status)
                   OR NOT (NEW.requested_amount <=> OLD.requested_amount)
                   OR NOT (NEW.reason <=> OLD.reason)
                   OR NOT (NEW.requester_id <=> OLD.requester_id)
                   OR NOT (NEW.reviewer_id <=> OLD.reviewer_id)
                   OR NOT (NEW.review_reason <=> OLD.review_reason) THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'FUNDING_ADJUST_REVIEW_IMMUTABLE';
                END IF;
            ELSEIF NEW.status IN ('APPROVED', 'REJECTED') THEN
                IF COALESCE(NEW.reviewer_id, 0) <= 0
                   OR NEW.reviewer_id = OLD.requester_id THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'FUNDING_ADJUST_SOD_REQUIRED';
                END IF;
                IF CHAR_LENGTH(TRIM(COALESCE(NEW.review_reason, ''))) < 5 THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'FUNDING_ADJUST_REVIEW_REASON_REQUIRED';
                END IF;
                SET NEW.reviewed_at = COALESCE(NEW.reviewed_at, CURRENT_TIMESTAMP);
            ELSEIF NEW.status <> 'PENDING' THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_ADJUST_STATUS_INVALID';
            END IF;
            SET NEW.requested_amount = OLD.requested_amount;
            SET NEW.reason = OLD.reason;
            SET NEW.requester_id = OLD.requester_id;
            SET NEW.requester_name = OLD.requester_name;
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
            IF v_project_amount IS NULL OR v_project_amount <= 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_RULE_AMOUNT_MISSING';
            END IF;
            SET NEW.amount = v_project_amount;
            SET NEW.requested_amount = v_project_amount;
            SET NEW.approved_amount = NULL;
            SET NEW.approved_at = NULL;
            SET NEW.quota_reserved = 0;
            IF NEW.status = 'GRANTED' THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_DIRECT_GRANTED_FORBIDDEN';
            END IF;
        END
    """))

    op.execute(sa.text("""
        CREATE TRIGGER trg_funding_app_bu_pkg10
        BEFORE UPDATE ON t_affairs_funding_application
        FOR EACH ROW
        BEGIN
            DECLARE v_project_amount DECIMAL(16,2);
            DECLARE v_adjust_amount DECIMAL(16,2);
            DECLARE v_adjust_requester BIGINT;
            DECLARE v_adjust_reviewer BIGINT;

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
            IF v_project_amount IS NULL OR v_project_amount <= 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'FUNDING_RULE_AMOUNT_MISSING';
            END IF;

            SET NEW.amount = OLD.amount;
            SET NEW.requested_amount = OLD.requested_amount;

            IF OLD.quota_reserved = 1 THEN
                IF NOT (NEW.approved_amount <=> OLD.approved_amount)
                   OR NOT (NEW.approved_at <=> OLD.approved_at)
                   OR NEW.status <> OLD.status THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'FUNDING_APPROVAL_FACT_IMMUTABLE';
                END IF;
                SET NEW.quota_reserved = 1;
            ELSEIF NEW.status = 'GRANTED' AND OLD.status <> 'GRANTED' THEN
                SELECT x.requested_amount, x.requester_id, x.reviewer_id
                  INTO v_adjust_amount, v_adjust_requester, v_adjust_reviewer
                  FROM t_affairs_funding_amount_adjustment x
                 WHERE x.tenant_id = NEW.tenant_id
                   AND x.application_id = NEW.id
                   AND x.status = 'APPROVED'
                   AND x.is_deleted = 0
                 ORDER BY x.id DESC
                 LIMIT 1;

                IF v_adjust_amount IS NOT NULL THEN
                    IF COALESCE(v_adjust_requester, 0) <= 0
                       OR COALESCE(v_adjust_reviewer, 0) <= 0
                       OR v_adjust_requester = v_adjust_reviewer THEN
                        SIGNAL SQLSTATE '45000'
                            SET MESSAGE_TEXT = 'FUNDING_ADJUST_SOD_REQUIRED';
                    END IF;
                    SET NEW.approved_amount = v_adjust_amount;
                ELSE
                    SET NEW.approved_amount = v_project_amount;
                END IF;

                IF NEW.approved_amount IS NULL OR NEW.approved_amount <= 0 THEN
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
            ELSE
                SET NEW.approved_amount = OLD.approved_amount;
                SET NEW.approved_at = OLD.approved_at;
                SET NEW.quota_reserved = OLD.quota_reserved;
            END IF;
        END
    """))


def upgrade() -> None:
    _require_mysql()
    _create_adjustment_table()

    # 上一版包 10 的应用触发器会把 amount/requested_amount 强制回写为旧值；
    # 必须先卸载，再做存量真值清洗，最后安装新的权威触发器。
    for name in _TRIGGERS:
        _drop_trigger(name)

    # 存量未批准申请的 legacy amount 统一回填为项目标准金额，客户端历史输入不再作为正式事实。
    op.execute(sa.text("""
        UPDATE t_affairs_funding_application a
        JOIN t_affairs_funding_batch b
          ON b.id = a.batch_id
         AND b.tenant_id = a.tenant_id
         AND b.is_deleted = 0
        JOIN t_affairs_funding_project p
          ON p.id = b.project_id
         AND p.tenant_id = b.tenant_id
         AND p.is_deleted = 0
           SET a.amount = p.amount,
               a.requested_amount = p.amount,
               a.approved_amount = CASE
                   WHEN a.quota_reserved = 1 THEN a.approved_amount
                   ELSE NULL
               END,
               a.approved_at = CASE
                   WHEN a.quota_reserved = 1 THEN a.approved_at
                   ELSE NULL
               END
         WHERE a.is_deleted = 0
           AND p.amount IS NOT NULL
           AND p.amount > 0
    """))

    _create_triggers()


def downgrade() -> None:
    _require_mysql()
    for name in _TRIGGERS:
        _drop_trigger(name)
    if _has_table(_ADJUST):
        op.drop_table(_ADJUST)

    # 恢复上一个迁移的触发器，保证降级后仍保留包 10 首批硬边界。
    import importlib.util
    from pathlib import Path

    path = Path(__file__).with_name("20260806_funding_package10_truth.py")
    spec = importlib.util.spec_from_file_location("funding_package10_truth", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load package 10 base migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = op
    module._create_triggers()
