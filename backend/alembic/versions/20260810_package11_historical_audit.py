"""Package 11 historical shared-ledger impact audit.

Revision ID: 20260810_package11_historical_audit
Revises: 20260809_aa_stage_c3_fact_v2

The original Package 11 migration could soft-delete duplicate rows owned by the
shared service-student ledger. Rewriting that historical migration protects new
databases, but cannot repair databases that already executed it. This forward
audit stops upgrades when the old marker is present so operators can perform
tenant-specific data governance. It deliberately does not guess which duplicate
row should be restored.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260810_package11_historical_audit"
down_revision = "20260809_aa_stage_c3_fact_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("Package 11 historical audit requires MySQL")
    impacted = bind.execute(sa.text("""
        SELECT tenant_id, student_id, COUNT(*) AS impacted_count
          FROM t_cs_service_student
         WHERE void_reason = 'PACKAGE11_DUPLICATE_SERVICE_STUDENT'
         GROUP BY tenant_id, student_id
         ORDER BY tenant_id, student_id
         LIMIT 1
    """)).mappings().first()
    if impacted:
        raise RuntimeError(
            "package 11 historical impact detected; manual shared-ledger governance required; "
            f"tenant_id={impacted['tenant_id']}, "
            f"student_id={impacted['student_id']}, "
            f"impacted_count={impacted['impacted_count']}"
        )


def downgrade() -> None:
    # Audit-only revision: no schema or business data is mutated.
    pass
