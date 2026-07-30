"""公共文件冻结中心阶段 5：学工材料版本、强敏感与真实档案清单

Revision ID: 0149_affairs_material_center
Revises: 0148_internship_material_center
Create Date: 2026-07-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0149_affairs_material_center"
down_revision = "0148_internship_material_center"
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {item["name"] for item in _inspector().get_columns(table)}


def _indexes(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {item["name"] for item in _inspector().get_indexes(table)}


def _add_columns(table: str, additions: list[tuple[str, sa.Column]]) -> None:
    cols = _columns(table)
    for name, column in additions:
        if name not in cols:
            op.add_column(table, column)


def _add_indexes(table: str, additions: list[tuple[str, list[str]]]) -> None:
    indexes = _indexes(table)
    for name, columns in additions:
        if name not in indexes:
            op.create_index(name, table, columns)


def upgrade() -> None:
    if "t_affairs_material_requirement" in _tables():
        _add_columns("t_affairs_material_requirement", [
            ("asset_id", sa.Column("asset_id", sa.BigInteger())),
            ("sensitivity_level", sa.Column(
                "sensitivity_level", sa.String(30), nullable=False,
                server_default="SENSITIVE",
            )),
            ("material_scope", sa.Column(
                "material_scope", sa.String(30), nullable=False,
                server_default="STUDENT_SELF",
            )),
        ])
        _add_indexes("t_affairs_material_requirement", [
            ("ix_t_affairs_material_requirement_asset_id", ["asset_id"]),
            ("ix_affairs_material_requirement_sensitivity", [
                "tenant_id", "sensitivity_level", "status",
            ]),
        ])

    if "t_affairs_material_submission" in _tables():
        _add_columns("t_affairs_material_submission", [
            ("asset_id", sa.Column("asset_id", sa.BigInteger())),
            ("file_version_id", sa.Column("file_version_id", sa.BigInteger())),
            ("binding_id", sa.Column("binding_id", sa.BigInteger())),
            ("sensitivity_level", sa.Column(
                "sensitivity_level", sa.String(30), nullable=False,
                server_default="SENSITIVE",
            )),
        ])
        _add_indexes("t_affairs_material_submission", [
            ("ix_t_affairs_material_submission_asset_id", ["asset_id"]),
            ("ix_t_affairs_material_submission_file_version_id", ["file_version_id"]),
            ("ix_t_affairs_material_submission_binding_id", ["binding_id"]),
            ("ix_affairs_material_submission_public_version", [
                "tenant_id", "requirement_id", "file_version_id", "status",
            ]),
        ])

    if "t_affairs_attachment" in _tables():
        _add_columns("t_affairs_attachment", [
            ("asset_id", sa.Column("asset_id", sa.BigInteger())),
            ("file_version_id", sa.Column("file_version_id", sa.BigInteger())),
            ("binding_id", sa.Column("binding_id", sa.BigInteger())),
            ("sensitivity_level", sa.Column(
                "sensitivity_level", sa.String(30), nullable=False,
                server_default="SENSITIVE",
            )),
            ("source_channel", sa.Column(
                "source_channel", sa.String(40), nullable=False,
                server_default="LEGACY_ADAPTER",
            )),
        ])
        _add_indexes("t_affairs_attachment", [
            ("ix_t_affairs_attachment_asset_id", ["asset_id"]),
            ("ix_t_affairs_attachment_file_version_id", ["file_version_id"]),
            ("ix_t_affairs_attachment_binding_id", ["binding_id"]),
            ("ix_affairs_attachment_public_binding", [
                "tenant_id", "biz_type", "biz_id", "file_version_id",
            ]),
        ])

    if "t_affairs_archive_package" in _tables():
        _add_columns("t_affairs_archive_package", [
            ("package_asset_id", sa.Column("package_asset_id", sa.BigInteger())),
            ("package_version_id", sa.Column("package_version_id", sa.BigInteger())),
            ("manifest_id", sa.Column("manifest_id", sa.BigInteger())),
            ("manifest_revision", sa.Column("manifest_revision", sa.Integer())),
            ("manifest_sha256", sa.Column("manifest_sha256", sa.String(64))),
        ])
        _add_indexes("t_affairs_archive_package", [
            ("ix_t_affairs_archive_package_package_asset_id", ["package_asset_id"]),
            ("ix_t_affairs_archive_package_package_version_id", ["package_version_id"]),
            ("ix_t_affairs_archive_package_manifest_id", ["manifest_id"]),
            ("ix_affairs_archive_package_manifest", [
                "tenant_id", "batch_id", "student_id", "manifest_id",
            ]),
        ])


def downgrade() -> None:
    plans = {
        "t_affairs_archive_package": (
            [
                "ix_affairs_archive_package_manifest",
                "ix_t_affairs_archive_package_manifest_id",
                "ix_t_affairs_archive_package_package_version_id",
                "ix_t_affairs_archive_package_package_asset_id",
            ],
            [
                "manifest_sha256", "manifest_revision", "manifest_id",
                "package_version_id", "package_asset_id",
            ],
        ),
        "t_affairs_attachment": (
            [
                "ix_affairs_attachment_public_binding",
                "ix_t_affairs_attachment_binding_id",
                "ix_t_affairs_attachment_file_version_id",
                "ix_t_affairs_attachment_asset_id",
            ],
            [
                "source_channel", "sensitivity_level", "binding_id",
                "file_version_id", "asset_id",
            ],
        ),
        "t_affairs_material_submission": (
            [
                "ix_affairs_material_submission_public_version",
                "ix_t_affairs_material_submission_binding_id",
                "ix_t_affairs_material_submission_file_version_id",
                "ix_t_affairs_material_submission_asset_id",
            ],
            ["sensitivity_level", "binding_id", "file_version_id", "asset_id"],
        ),
        "t_affairs_material_requirement": (
            [
                "ix_affairs_material_requirement_sensitivity",
                "ix_t_affairs_material_requirement_asset_id",
            ],
            ["material_scope", "sensitivity_level", "asset_id"],
        ),
    }
    for table, (indexes, columns) in plans.items():
        if table not in _tables():
            continue
        existing_indexes = _indexes(table)
        for name in indexes:
            if name in existing_indexes:
                op.drop_index(name, table_name=table)
        existing_columns = _columns(table)
        for name in columns:
            if name in existing_columns:
                op.drop_column(table, name)
