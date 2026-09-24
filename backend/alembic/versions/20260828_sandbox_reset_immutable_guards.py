"""Allow the explicit 007 rebuild through immutable-evidence delete guards.

Revision ID: 20260828_sandbox_reset_guards
Revises: 20260825_repair_recovery_run
"""
from __future__ import annotations

from alembic import op

revision = "20260828_sandbox_reset_guards"
down_revision = "20260825_repair_recovery_run"
branch_labels = None
depends_on = None

SANDBOX_TID = 1000000000000000007


def _mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260828_sandbox_reset_guards requires MySQL")


def upgrade() -> None:
    _mysql()
    op.execute("DROP TRIGGER IF EXISTS trg_intern_placement_snapshot_no_delete")
    op.execute(f"""
        CREATE TRIGGER trg_intern_placement_snapshot_no_delete
        BEFORE DELETE ON t_internship_placement_snapshot FOR EACH ROW
        BEGIN
          IF COALESCE(@sandbox_reset_tenant_id, 0) <> OLD.tenant_id
             OR OLD.tenant_id <> {SANDBOX_TID} THEN
            SIGNAL SQLSTATE '45000'
              SET MESSAGE_TEXT='INTERNSHIP_PLACEMENT_SNAPSHOT_IMMUTABLE';
          END IF;
        END
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_intern_material_snapshot_no_delete")
    op.execute(f"""
        CREATE TRIGGER trg_intern_material_snapshot_no_delete
        BEFORE DELETE ON t_internship_application_material_snapshot FOR EACH ROW
        BEGIN
          IF COALESCE(@sandbox_reset_tenant_id, 0) <> OLD.tenant_id
             OR OLD.tenant_id <> {SANDBOX_TID} THEN
            SIGNAL SQLSTATE '45000'
              SET MESSAGE_TEXT='INTERNSHIP_MATERIAL_SNAPSHOT_IMMUTABLE';
          END IF;
        END
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_disc_decision_bd_pkg11")
    op.execute(f"""
        CREATE TRIGGER trg_disc_decision_bd_pkg11
        BEFORE DELETE ON t_affairs_discipline_decision_version FOR EACH ROW
        BEGIN
          IF COALESCE(@sandbox_reset_tenant_id, 0) <> OLD.tenant_id
             OR OLD.tenant_id <> {SANDBOX_TID} THEN
            SIGNAL SQLSTATE '45000'
              SET MESSAGE_TEXT='DISCIPLINE_DECISION_IMMUTABLE';
          END IF;
        END
    """)


def downgrade() -> None:
    _mysql()
    op.execute("DROP TRIGGER IF EXISTS trg_intern_placement_snapshot_no_delete")
    op.execute("""CREATE TRIGGER trg_intern_placement_snapshot_no_delete
        BEFORE DELETE ON t_internship_placement_snapshot FOR EACH ROW
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INTERNSHIP_PLACEMENT_SNAPSHOT_IMMUTABLE'""")
    op.execute("DROP TRIGGER IF EXISTS trg_intern_material_snapshot_no_delete")
    op.execute("""CREATE TRIGGER trg_intern_material_snapshot_no_delete
        BEFORE DELETE ON t_internship_application_material_snapshot FOR EACH ROW
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INTERNSHIP_MATERIAL_SNAPSHOT_IMMUTABLE'""")
    op.execute("DROP TRIGGER IF EXISTS trg_disc_decision_bd_pkg11")
    op.execute("""CREATE TRIGGER trg_disc_decision_bd_pkg11
        BEFORE DELETE ON t_affairs_discipline_decision_version FOR EACH ROW
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='DISCIPLINE_DECISION_IMMUTABLE'""")
