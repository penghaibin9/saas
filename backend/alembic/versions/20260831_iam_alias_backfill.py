"""Canonicalize persisted RoleTemplate ``system.*`` permission aliases.

Revision ID: 20260831_iam_alias_backfill
Revises: 20260830_pr239_240_merge

The compatibility alias map remains a read-only bridge.  Persisted normalized
RoleTemplate permissions and their JSON snapshots are moved to canonical
``systemAdmin.*`` codes.  Two small audit tables retain the exact pre-migration
state so downgrade is deterministic even when multiple legacy codes collapse
onto one canonical code.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260831_iam_alias_backfill"
down_revision = "20260830_pr239_240_merge"
branch_labels = None
depends_on = None

assert len(revision) <= 32


ALIASES = {
    "system.audit.login.view": "systemAdmin.audit.view",
    "system.audit.operation.view": "systemAdmin.audit.view",
    "system.audit.sensitive.view": "systemAdmin.audit.sensitive.view",
    "system.config.brand.manage": "systemAdmin.config.manage",
    "system.config.feature.view": "systemAdmin.config.feature.view",
    "system.config.view": "systemAdmin.config.view",
    "system.dashboard.view": "systemAdmin.dashboard.view",
    "system.delegation.manage": "systemAdmin.delegation.manage",
    "system.integration.manage": "systemAdmin.integration.manage",
    "system.integration.sync.view": "systemAdmin.integration.sync.view",
    "system.migration.view": "systemAdmin.migration.view",
    "system.org.affiliation.manage": "systemAdmin.org.affiliation.manage",
    "system.org.class.manage": "systemAdmin.org.class.manage",
    "system.org.major.manage": "systemAdmin.org.major.manage",
    "system.org.view": "systemAdmin.org.view",
    "system.role.permission.manage": "systemAdmin.role.config",
    "system.role.template.view": "systemAdmin.role.view",
    "system.role.view": "systemAdmin.role.view",
    "system.scope.view": "systemAdmin.scope.view",
    "system.security.policy.manage": "systemAdmin.security.policy.manage",
    "system.user.exception.view": "systemAdmin.user.exception.view",
    "system.user.import": "systemAdmin.user.import",
    "system.user.view": "systemAdmin.user.view",
}


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260831_iam_alias_backfill requires MySQL")


def _object(value) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _digest(codes) -> str:
    payload = json.dumps(sorted(set(codes or [])), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _create_audit_tables() -> None:
    op.create_table(
        "t_iam_alias_backfill_template_audit",
        sa.Column("role_template_id", sa.BigInteger(), primary_key=True),
        sa.Column("old_permission_digest", sa.String(64), nullable=True),
        sa.Column("old_permission_ceiling_json", sa.Text(), nullable=False),
        sa.Column("migrated_at", sa.DateTime(), nullable=False),
        mysql_engine="InnoDB",
    )
    op.create_table(
        "t_iam_alias_backfill_row_audit",
        sa.Column("role_template_permission_id", sa.BigInteger(), primary_key=True),
        sa.Column("legacy_code", sa.String(160), nullable=False),
        sa.Column("canonical_code", sa.String(160), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("canonical_row_id", sa.BigInteger(), nullable=True),
        sa.Column("canonical_was_deleted", sa.Boolean(), nullable=True),
        sa.Column("migrated_at", sa.DateTime(), nullable=False),
        mysql_engine="InnoDB",
    )


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("t_role_template") or not insp.has_table("t_role_template_permission"):
        raise RuntimeError("RoleTemplate governance tables are required before alias backfill")

    _create_audit_tables()
    now = datetime.utcnow()

    legacy_rows = list(bind.execute(sa.text(
        "SELECT id, role_template_id, permission_code, effect "
        "FROM t_role_template_permission "
        "WHERE is_deleted=0 AND permission_code LIKE 'system.%' "
        "ORDER BY role_template_id, id"
    )).mappings())

    unknown = sorted({str(row["permission_code"]) for row in legacy_rows if str(row["permission_code"]) not in ALIASES})
    if unknown:
        raise RuntimeError("Unmapped persisted system.* RoleTemplate permissions: " + ",".join(unknown))

    for row in legacy_rows:
        row_id = int(row["id"])
        template_id = int(row["role_template_id"])
        legacy = str(row["permission_code"])
        canonical = ALIASES[legacy]
        existing = bind.execute(sa.text(
            "SELECT id, is_deleted FROM t_role_template_permission "
            "WHERE role_template_id=:template_id AND permission_code=:canonical AND effect=:effect "
            "ORDER BY id LIMIT 1"
        ), {"template_id": template_id, "canonical": canonical, "effect": row["effect"]}).mappings().first()

        action = "UPDATE_CODE"
        canonical_row_id = None
        canonical_was_deleted = None
        if existing is None:
            bind.execute(sa.text(
                "UPDATE t_role_template_permission SET permission_code=:canonical WHERE id=:row_id"
            ), {"canonical": canonical, "row_id": row_id})
        else:
            canonical_row_id = int(existing["id"])
            canonical_was_deleted = bool(existing["is_deleted"])
            action = "COLLAPSE_REACTIVATE" if canonical_was_deleted else "COLLAPSE_EXISTING"
            if canonical_was_deleted:
                bind.execute(sa.text(
                    "UPDATE t_role_template_permission SET is_deleted=0 WHERE id=:canonical_row_id"
                ), {"canonical_row_id": canonical_row_id})
            bind.execute(sa.text(
                "UPDATE t_role_template_permission SET is_deleted=1 WHERE id=:row_id"
            ), {"row_id": row_id})

        bind.execute(sa.text(
            "INSERT INTO t_iam_alias_backfill_row_audit "
            "(role_template_permission_id, legacy_code, canonical_code, action, canonical_row_id, "
            "canonical_was_deleted, migrated_at) "
            "VALUES (:row_id, :legacy, :canonical, :action, :canonical_row_id, "
            ":canonical_was_deleted, :migrated_at)"
        ), {
            "row_id": row_id,
            "legacy": legacy,
            "canonical": canonical,
            "action": action,
            "canonical_row_id": canonical_row_id,
            "canonical_was_deleted": canonical_was_deleted,
            "migrated_at": now,
        })

    templates = list(bind.execute(sa.text(
        "SELECT id, permission_digest, permission_ceiling_json FROM t_role_template ORDER BY id"
    )).mappings())
    for template in templates:
        snapshot = _object(template["permission_ceiling_json"])
        old_items = [str(code) for code in (snapshot.get("items") or []) if str(code)]
        new_items = sorted({ALIASES.get(code, code) for code in old_items})
        if new_items == sorted(set(old_items)):
            continue
        unknown_snapshot = sorted({code for code in old_items if code.startswith("system.") and code not in ALIASES})
        if unknown_snapshot:
            raise RuntimeError(
                f"Unmapped system.* snapshot permissions for template {template['id']}: "
                + ",".join(unknown_snapshot)
            )
        bind.execute(sa.text(
            "INSERT INTO t_iam_alias_backfill_template_audit "
            "(role_template_id, old_permission_digest, old_permission_ceiling_json, migrated_at) "
            "VALUES (:template_id, :old_digest, :old_snapshot, :migrated_at)"
        ), {
            "template_id": int(template["id"]),
            "old_digest": template["permission_digest"],
            "old_snapshot": _json(snapshot),
            "migrated_at": now,
        })
        digest = _digest(new_items)
        snapshot["items"] = new_items
        snapshot["permissionDigest"] = digest
        bind.execute(sa.text(
            "UPDATE t_role_template SET permission_digest=:digest, permission_ceiling_json=:snapshot "
            "WHERE id=:template_id"
        ), {"digest": digest, "snapshot": _json(snapshot), "template_id": int(template["id"])})


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("t_iam_alias_backfill_row_audit"):
        return

    template_audits = list(bind.execute(sa.text(
        "SELECT role_template_id, old_permission_digest, old_permission_ceiling_json "
        "FROM t_iam_alias_backfill_template_audit ORDER BY role_template_id DESC"
    )).mappings())
    for audit in template_audits:
        bind.execute(sa.text(
            "UPDATE t_role_template SET permission_digest=:digest, permission_ceiling_json=:snapshot "
            "WHERE id=:template_id"
        ), {
            "digest": audit["old_permission_digest"],
            "snapshot": audit["old_permission_ceiling_json"],
            "template_id": int(audit["role_template_id"]),
        })

    row_audits = list(bind.execute(sa.text(
        "SELECT role_template_permission_id, legacy_code, action, canonical_row_id, canonical_was_deleted "
        "FROM t_iam_alias_backfill_row_audit ORDER BY role_template_permission_id DESC"
    )).mappings())
    for audit in row_audits:
        row_id = int(audit["role_template_permission_id"])
        action = str(audit["action"])
        if action == "UPDATE_CODE":
            bind.execute(sa.text(
                "UPDATE t_role_template_permission SET permission_code=:legacy WHERE id=:row_id"
            ), {"legacy": audit["legacy_code"], "row_id": row_id})
            continue
        if action == "COLLAPSE_REACTIVATE" and audit["canonical_row_id"] is not None:
            bind.execute(sa.text(
                "UPDATE t_role_template_permission SET is_deleted=1 WHERE id=:canonical_row_id"
            ), {"canonical_row_id": int(audit["canonical_row_id"])})
        bind.execute(sa.text(
            "UPDATE t_role_template_permission SET is_deleted=0 WHERE id=:row_id"
        ), {"row_id": row_id})

    op.drop_table("t_iam_alias_backfill_row_audit")
    op.drop_table("t_iam_alias_backfill_template_audit")
