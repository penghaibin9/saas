"""Control Plane B1/B5: canonical CUSTOM role binding + RoleTemplate normalized schema.

Revision ID: 20260815_ctrl_role_gov
Revises: 20260814_merge_ix_v93_main

This is the Control Plane branch-local Alembic lineage. E-A01's already-published
E-M1..M5 lineage currently lives on the E Authority branch; E×IAM joint
integration must converge both histories to one final head before merge.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260815_ctrl_role_gov"
down_revision = "20260814_merge_ix_v93_main"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260815_ctrl_role_gov requires MySQL")


def _json(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _digest(items) -> str:
    payload = json.dumps(sorted({str(x) for x in (items or []) if str(x)}), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _preaudit_custom_role_sources(bind) -> list[tuple[int, int]]:
    """Return (source_id, role_id) only for unambiguous CUSTOM 1:1 mappings.

    The migration must never guess an orphan/mismatch. It fails before DDL so
    operators get a deterministic repair list instead of a half-bound IAM graph.
    """
    insp = inspect(bind)
    if not insp.has_table("t_custom_role_source") or not insp.has_table("t_role"):
        return []
    sources = list(bind.execute(sa.text(
        "SELECT id, tenant_id, role_code FROM t_custom_role_source WHERE is_deleted=0"
    )).mappings())
    mappings: list[tuple[int, int]] = []
    failures: list[str] = []
    for source in sources:
        roles = list(bind.execute(sa.text(
            "SELECT id, role_type, is_deleted FROM t_role "
            "WHERE tenant_id=:tenant_id AND role_code=:role_code"
        ), {"tenant_id": int(source["tenant_id"]), "role_code": source["role_code"]}).mappings())
        active = [row for row in roles if not bool(row["is_deleted"])]
        custom = [row for row in active if str(row["role_type"] or "").upper() == "CUSTOM"]
        if len(custom) == 1 and len(active) == 1:
            mappings.append((int(source["id"]), int(custom[0]["id"])))
            continue
        if not active:
            kind = "orphan-source"
        elif len(active) > 1:
            kind = "duplicate"
        else:
            kind = "system/custom-mismatch"
        failures.append(f"{kind}:tenant={source['tenant_id']}:roleCode={source['role_code']}:sourceId={source['id']}")
    if failures:
        preview = "; ".join(failures[:20])
        raise RuntimeError(
            f"B1 CustomRoleSource preaudit failed ({len(failures)} rows). Repair explicitly before retry: {preview}"
        )
    return mappings


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)
    role_bindings = _preaudit_custom_role_sources(bind)

    if insp.has_table("t_custom_role_source"):
        cols = {c["name"] for c in insp.get_columns("t_custom_role_source")}
        if "role_id" not in cols:
            op.add_column("t_custom_role_source", sa.Column("role_id", sa.BigInteger(), nullable=True))
            for source_id, role_id in role_bindings:
                bind.execute(sa.text(
                    "UPDATE t_custom_role_source SET role_id=:role_id WHERE id=:source_id"
                ), {"role_id": role_id, "source_id": source_id})
            # Expand-only for N-1 rolling deploys: previous-release writers do not know role_id.
            # Backfill existing rows now; tighten to NOT NULL only after old writers are retired.
            op.create_index("ix_t_custom_role_source_role_id", "t_custom_role_source", ["role_id"])
            op.create_unique_constraint(
                "uk_custom_role_source_role", "t_custom_role_source", ["tenant_id", "role_id"]
            )

    insp = inspect(bind)
    if insp.has_table("t_role_template"):
        cols = {c["name"] for c in insp.get_columns("t_role_template")}
        additions = [
            ("template_plane", sa.Column("template_plane", sa.String(32), nullable=False, server_default="TENANT")),
            ("template_category", sa.Column("template_category", sa.String(32), nullable=False, server_default="SYSTEM_ROLE")),
            ("publish_status", sa.Column("publish_status", sa.String(24), nullable=False, server_default="PUBLISHED")),
            ("permission_digest", sa.Column("permission_digest", sa.String(64), nullable=True)),
            ("previous_template_id", sa.Column("previous_template_id", sa.BigInteger(), nullable=True)),
            ("change_reason", sa.Column("change_reason", sa.String(1000), nullable=True)),
            ("source_commit_sha", sa.Column("source_commit_sha", sa.String(64), nullable=True)),
            ("effective_at", sa.Column("effective_at", sa.DateTime(), nullable=True)),
            ("published_at", sa.Column("published_at", sa.DateTime(), nullable=True)),
            ("published_by", sa.Column("published_by", sa.BigInteger(), nullable=True)),
        ]
        for name, column in additions:
            if name not in cols:
                op.add_column("t_role_template", column)

        rows = list(bind.execute(sa.text(
            "SELECT id, tenant_id, template_code, template_version, status, permission_ceiling_json "
            "FROM t_role_template WHERE is_deleted=0 ORDER BY tenant_id, template_code, template_version"
        )).mappings())
        by_version = {
            (int(row["tenant_id"]), str(row["template_code"]), int(row["template_version"] or 0)): int(row["id"])
            for row in rows
        }
        for row in rows:
            ceiling = _json(row["permission_ceiling_json"])
            items = ceiling.get("items") or []
            stored_status = str(row["status"] or "").upper()
            publish_status = "DRAFT" if stored_status == "DRAFT" else "PUBLISHED"
            prev_version = ceiling.get("previousTemplateVersion")
            previous_id = None
            try:
                if prev_version not in (None, ""):
                    previous_id = by_version.get((int(row["tenant_id"]), str(row["template_code"]), int(prev_version)))
            except (TypeError, ValueError):
                previous_id = None
            bind.execute(sa.text(
                "UPDATE t_role_template SET template_plane=:plane, template_category=:category, "
                "publish_status=:publish_status, permission_digest=:digest, previous_template_id=:previous_id, "
                "change_reason=:reason, source_commit_sha=:source_sha, effective_at=:effective_at, "
                "published_at=:published_at, published_by=:published_by, "
                "status=CASE WHEN status IN ('DRAFT','PUBLISHED') THEN 'ACTIVE' ELSE status END "
                "WHERE id=:id"
            ), {
                "plane": str(ceiling.get("templatePlane") or "TENANT"),
                "category": str(ceiling.get("templateCategory") or "SYSTEM_ROLE"),
                "publish_status": publish_status,
                "digest": str(ceiling.get("permissionDigest") or _digest(items)),
                "previous_id": previous_id,
                "reason": str(ceiling.get("changeReason") or "") or None,
                "source_sha": str(ceiling.get("sourceCommitSha") or "") or None,
                "effective_at": _dt(ceiling.get("effectiveAt")),
                "published_at": _dt(ceiling.get("publishedAt")),
                "published_by": ceiling.get("publishedBy"),
                "id": int(row["id"]),
            })
        indexes = {idx["name"] for idx in inspect(bind).get_indexes("t_role_template")}
        if "ix_t_role_template_previous_template_id" not in indexes:
            op.create_index("ix_t_role_template_previous_template_id", "t_role_template", ["previous_template_id"])
        if "idx_role_template_publish" not in indexes:
            op.create_index(
                "idx_role_template_publish", "t_role_template",
                ["tenant_id", "template_plane", "template_code", "publish_status"],
            )

    insp = inspect(bind)
    if not insp.has_table("t_role_template_permission"):
        op.create_table(
            "t_role_template_permission",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("role_template_id", sa.BigInteger(), nullable=False),
            sa.Column("permission_code", sa.String(160), nullable=False),
            sa.Column("effect", sa.String(8), nullable=False, server_default="ALLOW"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("role_template_id", "permission_code", "effect", name="uk_role_template_permission"),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_role_template_permission_tenant_id", "t_role_template_permission", ["tenant_id"])
        op.create_index("ix_t_role_template_permission_role_template_id", "t_role_template_permission", ["role_template_id"])
        op.create_index(
            "idx_role_template_permission_code", "t_role_template_permission",
            ["tenant_id", "permission_code", "effect"],
        )

        if inspect(bind).has_table("t_role_template"):
            now = datetime.utcnow()
            rows = list(bind.execute(sa.text(
                "SELECT id, tenant_id, permission_ceiling_json FROM t_role_template WHERE is_deleted=0"
            )).mappings())
            for row in rows:
                items = sorted({str(code) for code in (_json(row["permission_ceiling_json"]).get("items") or []) if str(code)})
                for code in items:
                    bind.execute(sa.text(
                        "INSERT INTO t_role_template_permission "
                        "(tenant_id, role_template_id, permission_code, effect, created_at, updated_at, is_deleted, version) "
                        "VALUES (:tenant_id, :template_id, :code, 'ALLOW', :now, :now, 0, 0)"
                    ), {
                        "tenant_id": int(row["tenant_id"]),
                        "template_id": int(row["id"]),
                        "code": code,
                        "now": now,
                    })


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("t_role_template_permission"):
        op.drop_table("t_role_template_permission")

    insp = inspect(bind)
    if insp.has_table("t_role_template"):
        indexes = {idx["name"] for idx in insp.get_indexes("t_role_template")}
        for name in ("idx_role_template_publish", "ix_t_role_template_previous_template_id"):
            if name in indexes:
                op.drop_index(name, table_name="t_role_template")
        cols = {c["name"] for c in insp.get_columns("t_role_template")}
        for name in (
            "published_by", "published_at", "effective_at", "source_commit_sha", "change_reason",
            "previous_template_id", "permission_digest", "publish_status", "template_category", "template_plane",
        ):
            if name in cols:
                op.drop_column("t_role_template", name)

    insp = inspect(bind)
    if insp.has_table("t_custom_role_source"):
        uniques = {u["name"] for u in insp.get_unique_constraints("t_custom_role_source") if u.get("name")}
        indexes = {idx["name"] for idx in insp.get_indexes("t_custom_role_source")}
        if "uk_custom_role_source_role" in uniques:
            op.drop_constraint("uk_custom_role_source_role", "t_custom_role_source", type_="unique")
        if "ix_t_custom_role_source_role_id" in indexes:
            op.drop_index("ix_t_custom_role_source_role_id", table_name="t_custom_role_source")
        if "role_id" in {c["name"] for c in insp.get_columns("t_custom_role_source")}:
            op.drop_column("t_custom_role_source", "role_id")
