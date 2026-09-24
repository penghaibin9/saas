"""X1 production XLSX permission closure.

Revision ID: 20260901_school_xlsx_x1
Revises: 20260901_orientation_checkin_o5
"""
from __future__ import annotations

import hashlib
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260901_school_xlsx_x1"
down_revision = "20260901_orientation_checkin_o5"
branch_labels = None
depends_on = None

PERMISSION = "studentAffairs.dorm.export"
ROLES = (
    "SCHOOL_ADMIN", "SYS_ADMIN", "STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN", "DORM_MANAGER",
)
TEMPLATE_ROLES = ("SCHOOL_ADMIN", "STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN", "DORM_MANAGER")


def _sync_published_templates(bind, *, add: bool) -> None:
    """Release-time evolution of immutable-at-runtime SYSTEM role snapshots."""
    tables = set(inspect(bind).get_table_names())
    if not {"t_role_template", "t_role_template_permission"}.issubset(tables):
        return
    for role_code in TEMPLATE_ROLES:
        template = bind.execute(sa.text(
            "SELECT id, permission_ceiling_json FROM t_role_template "
            "WHERE tenant_id=0 AND template_code=:role "
            "AND template_plane='TENANT' AND template_category='SYSTEM_ROLE' "
            "AND publish_status='PUBLISHED' AND status='ACTIVE' AND is_deleted=0 "
            "ORDER BY template_version DESC, id DESC LIMIT 1"
        ), {"role": role_code}).mappings().first()
        if template is None:
            continue
        template_id = int(template["id"])
        if add:
            bind.execute(sa.text(
                "INSERT INTO t_role_template_permission "
                "(tenant_id, role_template_id, permission_code, effect, created_at, updated_at, is_deleted, version) "
                "SELECT 0, :template_id, :permission, 'ALLOW', NOW(), NOW(), 0, 0 "
                "WHERE NOT EXISTS (SELECT 1 FROM t_role_template_permission "
                "WHERE role_template_id=:template_id AND permission_code=:permission "
                "AND effect='ALLOW' AND is_deleted=0)"
            ), {"template_id": template_id, "permission": PERMISSION})
        else:
            bind.execute(sa.text(
                "DELETE FROM t_role_template_permission "
                "WHERE role_template_id=:template_id AND permission_code=:permission AND effect='ALLOW'"
            ), {"template_id": template_id, "permission": PERMISSION})

        codes = sorted(set(bind.execute(sa.text(
            "SELECT permission_code FROM t_role_template_permission "
            "WHERE role_template_id=:template_id AND effect='ALLOW' AND is_deleted=0"
        ), {"template_id": template_id}).scalars().all()))
        digest = hashlib.sha256(json.dumps(
            codes, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        raw_ceiling = template["permission_ceiling_json"]
        if isinstance(raw_ceiling, str):
            try:
                ceiling = json.loads(raw_ceiling)
            except (TypeError, ValueError):
                ceiling = {}
        elif isinstance(raw_ceiling, dict):
            ceiling = dict(raw_ceiling)
        else:
            ceiling = {}
        ceiling.update({"items": codes, "permissionDigest": digest, "compatibilityOnly": True})
        bind.execute(sa.text(
            "UPDATE t_role_template SET permission_digest=:digest, "
            "permission_ceiling_json=:ceiling, updated_at=NOW() WHERE id=:template_id"
        ), {
            "digest": digest,
            "ceiling": json.dumps(ceiling, ensure_ascii=False, separators=(",", ":")),
            "template_id": template_id,
        })


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
    _sync_published_templates(bind, add=True)


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    _sync_published_templates(bind, add=False)
    if {"t_role_permission", "t_permission"}.issubset(tables):
        bind.execute(sa.text(
            "DELETE rp FROM t_role_permission rp JOIN t_permission p ON p.id=rp.permission_id "
            "WHERE p.permission_code=:code"
        ), {"code": PERMISSION})
        bind.execute(sa.text(
            "DELETE FROM t_permission WHERE permission_code=:code"
        ), {"code": PERMISSION})
