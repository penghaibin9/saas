"""Register implementation-center permission points for custom roles.

Revision ID: 0109_implementation_permissions
Revises: 0108_shared_import_batches
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "0109_implementation_permissions"
down_revision = "0108_shared_import_batches"
branch_labels = None
depends_on = None


PERMISSION_CODES = (
    "systemAdmin.implementation.view",
    "systemAdmin.implementation.create",
    "systemAdmin.implementation.configure",
    "systemAdmin.implementation.preset.view",
    "systemAdmin.implementation.preview",
    "systemAdmin.implementation.apply",
    "systemAdmin.implementation.mapping.manage",
    "systemAdmin.implementation.mapping.apply",
    "systemAdmin.implementation.relation.manage",
    "systemAdmin.implementation.relation.apply",
    "systemAdmin.implementation.relation.rollback",
    "systemAdmin.implementation.installed.view",
    "systemAdmin.implementation.change.manage",
    "systemAdmin.implementation.check.run",
    "systemAdmin.implementation.accept",
)


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.utcnow()
    for code in PERMISSION_CODES:
        action = code.rsplit(".", 1)[-1]
        bind.execute(sa.text(
            "INSERT INTO t_permission (permission_code, permission_name, module_code, action, created_at) "
            "SELECT :code, :code, :module, :action, :created_at "
            "WHERE NOT EXISTS (SELECT 1 FROM t_permission WHERE permission_code = :code)"
        ), {"code": code, "module": "systemAdmin.implementation", "action": action, "created_at": now})


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "DELETE FROM t_permission WHERE permission_code IN :codes"
    ).bindparams(sa.bindparam("codes", expanding=True)), {"codes": list(PERMISSION_CODES)})
