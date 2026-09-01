"""X1 production XLSX permission closure.

Revision ID: 20260901_school_xlsx_x1
Revises: 20260901_orientation_checkin_o5
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260901_school_xlsx_x1"
down_revision = "20260901_orientation_checkin_o5"
branch_labels = None
depends_on = None

PERMISSION = "studentAffairs.dorm.export"
ROLES = ("SCHOOL_ADMIN", "SYS_ADMIN", "STUDENT_AFFAIRS_ADMIN", "DORM_MANAGER")


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "t_permission" in tables:
        bind.execute(sa.text(
            "INSERT INTO t_permission (permission_code, permission_name, module_code, action, created_at) "
            "SELECT :code, :name, :module, 'export', NOW() "
            "WHERE NOT EXISTS (SELECT 1 FROM t_permission WHERE permission_code=:code)"
        ), {"code": PERMISSION, "name": "导出宿舍台账", "module": "studentAffairs.dorm"})
    if {"t_role", "t_role_permission", "t_permission"}.issubset(tables):
        for role_code in ROLES:
            bind.execute(sa.text(
                "INSERT INTO t_role_permission "
                "(tenant_id, role_id, permission_id, status, created_at, updated_at, is_deleted, version) "
                "SELECT r.tenant_id, r.id, p.id, 'ACTIVE', NOW(), NOW(), 0, 0 "
                "FROM t_role r JOIN t_permission p ON p.permission_code=:permission "
                "WHERE r.role_code=:role AND r.is_deleted=0 "
                "AND NOT EXISTS (SELECT 1 FROM t_role_permission rp "
                "WHERE rp.tenant_id=r.tenant_id AND rp.role_id=r.id "
                "AND rp.permission_id=p.id AND rp.is_deleted=0)"
            ), {"role": role_code, "permission": PERMISSION})


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if {"t_role_permission", "t_permission"}.issubset(tables):
        bind.execute(sa.text(
            "DELETE rp FROM t_role_permission rp JOIN t_permission p ON p.id=rp.permission_id "
            "WHERE p.permission_code=:code"
        ), {"code": PERMISSION})
        bind.execute(sa.text(
            "DELETE FROM t_permission WHERE permission_code=:code"
        ), {"code": PERMISSION})
