"""公共文件冻结中心阶段 6：毕业设计材料中心业务语义表。

Revision ID: 0150_graduation_material_center
Revises: 0149_affairs_material_center
Create Date: 2026-07-30

说明：本迁移只创建/扩展 schema，不在 Alembic 事务中执行历史附件回填；
回填由可分页、可断点、可 dry-run 的应用服务独立执行，避免锁死生产业务表。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0150_graduation_material_center"
down_revision = "0149_affairs_material_center"
branch_labels = None
depends_on = None


def _bind():
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("0150_graduation_material_center requires MySQL")
    return bind


def _tables() -> set[str]:
    return set(inspect(_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {item["name"] for item in inspect(_bind()).get_columns(table)} if table in _tables() else set()


def _indexes(table: str) -> set[str]:
    return {item["name"] for item in inspect(_bind()).get_indexes(table)} if table in _tables() else set()


def _uniques(table: str) -> set[str]:
    return {
        item.get("name") for item in inspect(_bind()).get_unique_constraints(table)
        if item.get("name")
    } if table in _tables() else set()


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def _add_index(name: str, table: str, columns: list[str], *, unique: bool = False) -> None:
    if name not in _indexes(table):
        op.create_index(name, table, columns, unique=unique)


def _add_unique(name: str, table: str, columns: list[str]) -> None:
    if name not in _uniques(table):
        op.create_unique_constraint(name, table, columns)


def upgrade() -> None:
    _bind()
    tables = _tables()
    if "t_gd_material_rule" not in tables:
        op.create_table(
            "t_gd_material_rule",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger()),
            sa.Column("rule_code", sa.String(80), nullable=False),
            sa.Column("rule_name", sa.String(200), nullable=False),
            sa.Column("rule_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("default_owner_role", sa.String(40), nullable=False, server_default="STUDENT"),
            sa.Column("version_policy", sa.String(40), nullable=False, server_default="IMMUTABLE_APPEND"),
            sa.Column("archive_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sensitivity_level", sa.String(30), nullable=False, server_default="SENSITIVE"),
            sa.Column("applicable_scope_json", sa.JSON()),
            sa.Column("applicable_major_id", sa.String(64)),
            sa.Column("applicable_topic_type", sa.String(64)),
            sa.Column("effective_at", sa.DateTime()),
            sa.Column("required_items_json", sa.JSON()),
            sa.Column("allowed_ext_json", sa.JSON()),
            sa.Column("max_files", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("max_size_bytes", sa.BigInteger(), nullable=False, server_default=str(50 * 1024 * 1024)),
            sa.Column("remark", sa.String(500)),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.UniqueConstraint(
                "tenant_id", "batch_id", "rule_code", "rule_version",
                name="uk_gd_material_rule_version",
            ),
        )
    else:
        for column in (
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("default_owner_role", sa.String(40), nullable=False, server_default="STUDENT"),
            sa.Column("version_policy", sa.String(40), nullable=False, server_default="IMMUTABLE_APPEND"),
            sa.Column("archive_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sensitivity_level", sa.String(30), nullable=False, server_default="SENSITIVE"),
            sa.Column("applicable_major_id", sa.String(64)),
            sa.Column("applicable_topic_type", sa.String(64)),
            sa.Column("effective_at", sa.DateTime()),
        ):
            _add_column("t_gd_material_rule", column)
    _add_index("ix_t_gd_material_rule_tenant_id", "t_gd_material_rule", ["tenant_id"])
    _add_index("ix_t_gd_material_rule_batch_id", "t_gd_material_rule", ["batch_id"])
    _add_index(
        "ix_gd_material_rule_active", "t_gd_material_rule",
        ["tenant_id", "batch_id", "status", "enabled", "is_deleted"],
    )
    _add_index("ix_gd_material_rule_major", "t_gd_material_rule", ["tenant_id", "applicable_major_id"])

    tables = _tables()
    if "t_gd_material_item" not in tables:
        op.create_table(
            "t_gd_material_item",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("rule_id", sa.BigInteger(), nullable=False),
            sa.Column("biz_stage", sa.String(40), nullable=False),
            sa.Column("material_code", sa.String(100), nullable=False),
            sa.Column("material_name", sa.String(200), nullable=False),
            sa.Column("owner_role", sa.String(40), nullable=False, server_default="STUDENT"),
            sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("allowed_ext_json", sa.JSON()),
            sa.Column("max_files", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("max_size_bytes", sa.BigInteger(), nullable=False, server_default=str(50 * 1024 * 1024)),
            sa.Column("version_policy", sa.String(40), nullable=False, server_default="IMMUTABLE_APPEND"),
            sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("archive_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sensitivity_level", sa.String(30), nullable=False, server_default="SENSITIVE"),
            sa.Column("applicable_major_id", sa.String(64)),
            sa.Column("applicable_topic_type", sa.String(64)),
            sa.Column("sort_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("description", sa.String(500)),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.UniqueConstraint("tenant_id", "rule_id", "material_code", name="uk_gd_material_item_code"),
        )
    else:
        for column in (
            sa.Column("owner_role", sa.String(40), nullable=False, server_default="STUDENT"),
            sa.Column("version_policy", sa.String(40), nullable=False, server_default="IMMUTABLE_APPEND"),
            sa.Column("archive_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sensitivity_level", sa.String(30), nullable=False, server_default="SENSITIVE"),
            sa.Column("applicable_major_id", sa.String(64)),
            sa.Column("applicable_topic_type", sa.String(64)),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        ):
            _add_column("t_gd_material_item", column)
    _add_index("ix_t_gd_material_item_tenant_id", "t_gd_material_item", ["tenant_id"])
    _add_index("ix_t_gd_material_item_rule_id", "t_gd_material_item", ["rule_id"])
    _add_index(
        "ix_gd_material_item_stage", "t_gd_material_item",
        ["tenant_id", "rule_id", "biz_stage", "enabled", "sort_no", "is_deleted"],
    )

    if "t_gd_student_material" not in _tables():
        op.create_table(
            "t_gd_student_material",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger()),
            sa.Column("topic_id", sa.BigInteger()),
            sa.Column("rule_id", sa.BigInteger()),
            sa.Column("rule_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("material_code", sa.String(100), nullable=False),
            sa.Column("material_name", sa.String(200), nullable=False),
            sa.Column("biz_stage", sa.String(40), nullable=False),
            sa.Column("owner_role", sa.String(40), nullable=False, server_default="STUDENT"),
            sa.Column("asset_id", sa.BigInteger()),
            sa.Column("current_version_id", sa.BigInteger()),
            sa.Column("last_reviewed_version_id", sa.BigInteger()),
            sa.Column("business_status", sa.String(30), nullable=False, server_default="MISSING"),
            sa.Column("review_status", sa.String(30), nullable=False, server_default="NOT_SUBMITTED"),
            sa.Column("required_status", sa.String(30), nullable=False, server_default="REQUIRED"),
            sa.Column("archive_status", sa.String(30), nullable=False, server_default="NOT_ARCHIVED"),
            sa.Column("sensitivity_level", sa.String(30), nullable=False, server_default="SENSITIVE"),
            sa.Column("reject_reason", sa.String(1000)),
            sa.Column("reviewer_user_id", sa.BigInteger()),
            sa.Column("reviewer_name", sa.String(100)),
            sa.Column("reviewed_at", sa.DateTime()),
            sa.Column("submitted_at", sa.DateTime()),
            sa.Column("archived_revision", sa.Integer()),
            sa.Column("source_record_type", sa.String(50)),
            sa.Column("source_record_id", sa.String(80)),
            sa.Column("migration_status", sa.String(30), nullable=False, server_default="NATIVE"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.UniqueConstraint(
                "tenant_id", "batch_id", "gd_student_id", "material_code",
                name="uk_gd_student_material_code",
            ),
        )
    _add_index("ix_gd_student_material_batch", "t_gd_student_material", ["tenant_id", "batch_id"])
    _add_index("ix_gd_student_material_student", "t_gd_student_material", ["tenant_id", "gd_student_id"])
    _add_index("ix_gd_student_material_profile", "t_gd_student_material", ["tenant_id", "student_id"])
    _add_index("ix_gd_student_material_topic", "t_gd_student_material", ["tenant_id", "topic_id"])
    _add_index("ix_gd_student_material_rule", "t_gd_student_material", ["tenant_id", "rule_id"])
    _add_index("ix_gd_student_material_asset", "t_gd_student_material", ["tenant_id", "asset_id"])
    _add_index("ix_gd_student_material_version", "t_gd_student_material", ["tenant_id", "current_version_id"])
    _add_index(
        "ix_gd_student_material_library", "t_gd_student_material",
        ["tenant_id", "batch_id", "gd_student_id", "biz_stage", "is_deleted"],
    )
    _add_index(
        "ix_gd_student_material_status", "t_gd_student_material",
        ["tenant_id", "batch_id", "business_status", "review_status", "archive_status"],
    )
    _add_index(
        "ix_gd_student_material_current", "t_gd_student_material",
        ["tenant_id", "asset_id", "current_version_id"],
    )
    _add_index(
        "ix_gd_student_material_source", "t_gd_student_material",
        ["tenant_id", "source_record_type", "source_record_id"],
    )

    if "t_gd_material_backfill_checkpoint" not in _tables():
        op.create_table(
            "t_gd_material_backfill_checkpoint",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("migration_key", sa.String(100), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
            sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("cursor_model", sa.String(50)),
            sa.Column("cursor_id", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("page_size", sa.Integer(), nullable=False, server_default="200"),
            sa.Column("scanned_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("converted_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("diff_report_json", sa.JSON()),
            sa.Column("last_error", sa.Text()),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("finished_at", sa.DateTime()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.UniqueConstraint("tenant_id", "migration_key", name="uk_gd_material_backfill_key"),
        )
    _add_index(
        "ix_gd_material_backfill_status", "t_gd_material_backfill_checkpoint",
        ["tenant_id", "status", "updated_at"],
    )

    if "t_gd_template_asset_policy" not in _tables():
        op.create_table(
            "t_gd_template_asset_policy",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("template_id", sa.BigInteger(), nullable=False),
            sa.Column("template_code", sa.String(100), nullable=False),
            sa.Column("batch_id", sa.BigInteger()),
            sa.Column("college_id", sa.String(64)),
            sa.Column("major_id", sa.String(64)),
            sa.Column("asset_id", sa.BigInteger()),
            sa.Column("current_version_id", sa.BigInteger()),
            sa.Column("variable_schema_json", sa.JSON()),
            sa.Column("scope_json", sa.JSON()),
            sa.Column("effective_at", sa.DateTime()),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.UniqueConstraint("tenant_id", "template_id", name="uk_gd_template_asset_policy_template"),
            sa.UniqueConstraint("tenant_id", "template_code", name="uk_gd_template_asset_policy_code"),
        )
    _add_index("ix_gd_template_asset_template", "t_gd_template_asset_policy", ["tenant_id", "template_id"])
    _add_index("ix_gd_template_asset_batch", "t_gd_template_asset_policy", ["tenant_id", "batch_id"])
    _add_index("ix_gd_template_asset_asset", "t_gd_template_asset_policy", ["tenant_id", "asset_id"])
    _add_index("ix_gd_template_asset_version", "t_gd_template_asset_policy", ["tenant_id", "current_version_id"])
    _add_index(
        "ix_gd_template_asset_scope", "t_gd_template_asset_policy",
        ["tenant_id", "batch_id", "college_id", "major_id", "status", "is_deleted"],
    )


def downgrade() -> None:
    _bind()
    for table in (
        "t_gd_template_asset_policy",
        "t_gd_material_backfill_checkpoint",
        "t_gd_student_material",
    ):
        if table in _tables():
            op.drop_table(table)

    if "t_gd_material_item" in _tables():
        for name in (
            "enabled", "applicable_topic_type", "applicable_major_id", "sensitivity_level",
            "archive_required", "version_policy", "owner_role",
        ):
            if name in _columns("t_gd_material_item"):
                op.drop_column("t_gd_material_item", name)
    if "t_gd_material_rule" in _tables():
        for name in (
            "effective_at", "applicable_topic_type", "applicable_major_id", "sensitivity_level",
            "archive_required", "version_policy", "default_owner_role", "enabled",
        ):
            if name in _columns("t_gd_material_rule"):
                op.drop_column("t_gd_material_rule", name)

    # 规则与规则项是 0150 首次创建的核心表，降级最终删除。
    if "t_gd_material_item" in _tables():
        op.drop_table("t_gd_material_item")
    if "t_gd_material_rule" in _tables():
        op.drop_table("t_gd_material_rule")
