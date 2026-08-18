"""E-A01 M6: expand-compatible volunteer release/unlock contract.

Revision ID: 20260815_internship_e_m6
Revises: 20260815_internship_e_m5

M4 shipped temporary ``last_released_*`` names while V3 freezes ``released_*``.  N and N-1
application versions may overlap during a rolling deploy, therefore upgrade keeps both column
families, backfills them in both directions, and installs compatibility triggers.  A later
contract migration may remove the legacy names after the rollback window closes.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260815_internship_e_m6"
down_revision = "20260815_internship_e_m5"
branch_labels = None
depends_on = None

_TABLE = "t_internship_volunteer_group"
_INSERT_TRIGGER = "trg_intern_volunteer_release_compat_insert"
_UPDATE_TRIGGER = "trg_intern_volunteer_release_compat_update"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260815_internship_e_m6 requires MySQL")


def _columns() -> set[str]:
    insp = inspect(op.get_bind())
    return {column["name"] for column in insp.get_columns(_TABLE)} if insp.has_table(_TABLE) else set()


def _trigger_exists(name: str) -> bool:
    bind = op.get_bind()
    return bool(bind.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.TRIGGERS "
        "WHERE TRIGGER_SCHEMA = DATABASE() AND TRIGGER_NAME = :name"
    ), {"name": name}).scalar())


def _ensure_release_columns() -> None:
    columns = _columns()
    if "released_at" not in columns:
        op.add_column(_TABLE, sa.Column("released_at", sa.DateTime()))
    if "last_released_at" not in columns:
        op.add_column(_TABLE, sa.Column("last_released_at", sa.DateTime()))
    columns = _columns()
    if "release_reason" not in columns:
        op.add_column(_TABLE, sa.Column("release_reason", sa.String(500)))
    if "last_release_reason" not in columns:
        op.add_column(_TABLE, sa.Column("last_release_reason", sa.String(500)))

    op.execute(sa.text(
        f"UPDATE {_TABLE} SET "
        "released_at = COALESCE(released_at, last_released_at), "
        "last_released_at = COALESCE(last_released_at, released_at), "
        "release_reason = COALESCE(release_reason, last_release_reason), "
        "last_release_reason = COALESCE(last_release_reason, release_reason)"
    ))


def _ensure_compat_triggers() -> None:
    if not _trigger_exists(_INSERT_TRIGGER):
        op.execute(
            f"""
            CREATE TRIGGER {_INSERT_TRIGGER}
            BEFORE INSERT ON {_TABLE}
            FOR EACH ROW
            BEGIN
                IF NEW.released_at IS NULL AND NEW.last_released_at IS NOT NULL THEN
                    SET NEW.released_at = NEW.last_released_at;
                ELSEIF NEW.last_released_at IS NULL AND NEW.released_at IS NOT NULL THEN
                    SET NEW.last_released_at = NEW.released_at;
                END IF;
                IF NEW.release_reason IS NULL AND NEW.last_release_reason IS NOT NULL THEN
                    SET NEW.release_reason = NEW.last_release_reason;
                ELSEIF NEW.last_release_reason IS NULL AND NEW.release_reason IS NOT NULL THEN
                    SET NEW.last_release_reason = NEW.release_reason;
                END IF;
            END
            """
        )
    if not _trigger_exists(_UPDATE_TRIGGER):
        op.execute(
            f"""
            CREATE TRIGGER {_UPDATE_TRIGGER}
            BEFORE UPDATE ON {_TABLE}
            FOR EACH ROW
            BEGIN
                IF NOT (NEW.released_at <=> OLD.released_at)
                   AND (NEW.last_released_at <=> OLD.last_released_at) THEN
                    SET NEW.last_released_at = NEW.released_at;
                ELSEIF NOT (NEW.last_released_at <=> OLD.last_released_at)
                   AND (NEW.released_at <=> OLD.released_at) THEN
                    SET NEW.released_at = NEW.last_released_at;
                ELSEIF NOT (NEW.released_at <=> OLD.released_at)
                   AND NOT (NEW.last_released_at <=> OLD.last_released_at) THEN
                    SET NEW.last_released_at = NEW.released_at;
                END IF;
                IF NOT (NEW.release_reason <=> OLD.release_reason)
                   AND (NEW.last_release_reason <=> OLD.last_release_reason) THEN
                    SET NEW.last_release_reason = NEW.release_reason;
                ELSEIF NOT (NEW.last_release_reason <=> OLD.last_release_reason)
                   AND (NEW.release_reason <=> OLD.release_reason) THEN
                    SET NEW.release_reason = NEW.last_release_reason;
                ELSEIF NOT (NEW.release_reason <=> OLD.release_reason)
                   AND NOT (NEW.last_release_reason <=> OLD.last_release_reason) THEN
                    SET NEW.last_release_reason = NEW.release_reason;
                END IF;
            END
            """
        )


def upgrade() -> None:
    _require_mysql()
    columns = _columns()
    if not columns:
        raise RuntimeError("t_internship_volunteer_group must exist before M6")

    _ensure_release_columns()

    columns = _columns()
    if "unlock_requested_at" not in columns:
        op.add_column(_TABLE, sa.Column("unlock_requested_at", sa.DateTime()))
    if "unlock_request_reason" not in columns:
        op.add_column(_TABLE, sa.Column("unlock_request_reason", sa.String(500)))

    _ensure_compat_triggers()


def downgrade() -> None:
    _require_mysql()
    # Downgrade intentionally collapses to the M4 legacy schema after copying canonical data.
    op.execute(f"DROP TRIGGER IF EXISTS {_UPDATE_TRIGGER}")
    op.execute(f"DROP TRIGGER IF EXISTS {_INSERT_TRIGGER}")
    columns = _columns()
    if "last_released_at" in columns and "released_at" in columns:
        op.execute(sa.text(
            f"UPDATE {_TABLE} SET last_released_at=COALESCE(released_at,last_released_at)"
        ))
    if "last_release_reason" in columns and "release_reason" in columns:
        op.execute(sa.text(
            f"UPDATE {_TABLE} SET last_release_reason=COALESCE(release_reason,last_release_reason)"
        ))

    columns = _columns()
    if "unlock_request_reason" in columns:
        op.drop_column(_TABLE, "unlock_request_reason")
    if "unlock_requested_at" in columns:
        op.drop_column(_TABLE, "unlock_requested_at")
    columns = _columns()
    if "release_reason" in columns:
        op.drop_column(_TABLE, "release_reason")
    if "released_at" in columns:
        op.drop_column(_TABLE, "released_at")
