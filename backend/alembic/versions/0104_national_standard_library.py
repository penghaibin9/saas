"""National vocational education standards library.

Revision ID: 0104_national_standards
Revises: 0103_system_implementation

兼容说明：0001 历史迁移会导入运行时当前 metadata，空库升级时这些表可能已被
提前创建。本 revision 逐表检查后再执行原始 DDL，避免 MySQL 重复建表。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0104_national_standards"
down_revision = "0103_system_implementation"
branch_labels = None
depends_on = None


def _global_common():
    return [sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False), sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0")]


def _tenant_common():
    return [*_global_common(), sa.Column("tenant_id", sa.BigInteger(), nullable=False)]


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("t_national_standard_source"):
        op.create_table("t_national_standard_source", *_global_common(),
            sa.Column("source_key", sa.String(80), nullable=False), sa.Column("source_type", sa.String(40), nullable=False),
            sa.Column("title", sa.String(300), nullable=False), sa.Column("publisher", sa.String(100), nullable=False),
            sa.Column("version_label", sa.String(40), nullable=False), sa.Column("source_url", sa.String(1000), nullable=False),
            sa.Column("published_date", sa.Date()), sa.Column("is_official", sa.Boolean(), nullable=False),
            sa.Column("copyright_policy", sa.String(40), nullable=False),
            sa.Column("retrieval_status", sa.String(30), nullable=False), sa.Column("last_crawled_at", sa.DateTime()),
            sa.Column("manifest_sha256", sa.String(64)), sa.Column("item_count", sa.Integer(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.UniqueConstraint("source_key", "version_label", name="uk_nat_std_source_version"))

    if not _has_table("t_national_major_catalog"):
        op.create_table("t_national_major_catalog", *_global_common(),
            sa.Column("source_id", sa.BigInteger()), sa.Column("catalog_version", sa.String(40), nullable=False),
            sa.Column("education_level", sa.String(40), nullable=False), sa.Column("category_code", sa.String(20)),
            sa.Column("category_name", sa.String(100)), sa.Column("major_class_code", sa.String(20)),
            sa.Column("major_class_name", sa.String(100)), sa.Column("major_code", sa.String(30), nullable=False),
            sa.Column("major_name", sa.String(200), nullable=False),
            sa.Column("directory_status", sa.String(30), nullable=False), sa.Column("effective_date", sa.Date()),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.UniqueConstraint("catalog_version", "education_level", "major_code",
                                name="uk_nat_major_version_level_code"))
        op.create_index("ix_nat_major_level_code", "t_national_major_catalog", ["education_level", "major_code"])
        op.create_index("ix_nat_major_class", "t_national_major_catalog", ["major_class_code"])

    if not _has_table("t_national_standard_document"):
        op.create_table("t_national_standard_document", *_global_common(),
            sa.Column("source_id", sa.BigInteger(), nullable=False), sa.Column("major_catalog_id", sa.BigInteger()),
            sa.Column("standard_code", sa.String(100), nullable=False),
            sa.Column("document_type", sa.String(40), nullable=False), sa.Column("title", sa.String(500), nullable=False),
            sa.Column("education_level", sa.String(40), nullable=False), sa.Column("major_code", sa.String(30), nullable=False),
            sa.Column("major_name", sa.String(200), nullable=False), sa.Column("version_label", sa.String(40), nullable=False),
            sa.Column("published_date", sa.Date()), sa.Column("source_url", sa.String(1000), nullable=False),
            sa.Column("source_file_name", sa.String(300)), sa.Column("source_sha256", sa.String(64)),
            sa.Column("page_count", sa.Integer()), sa.Column("text_status", sa.String(30), nullable=False),
            sa.Column("full_text", sa.Text().with_variant(mysql.LONGTEXT(), "mysql")),
            sa.Column("structured_json", sa.JSON(), nullable=False), sa.Column("char_count", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False), sa.Column("extraction_error", sa.String(1000)),
            sa.UniqueConstraint("standard_code", "version_label", name="uk_nat_std_document_version"))
        op.create_index("ix_nat_std_document_level_major", "t_national_standard_document",
                        ["education_level", "major_code"])
        op.create_index("ix_nat_std_document_text_status", "t_national_standard_document", ["text_status"])
        op.create_index("ix_nat_std_document_sha", "t_national_standard_document", ["source_sha256"])

    if not _has_table("t_national_standard_section"):
        op.create_table("t_national_standard_section", *_global_common(),
            sa.Column("document_id", sa.BigInteger(), nullable=False), sa.Column("section_code", sa.String(50), nullable=False),
            sa.Column("section_no", sa.Integer(), nullable=False), sa.Column("section_title", sa.String(200), nullable=False),
            sa.Column("content_text", sa.Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=False),
            sa.Column("content_sha256", sa.String(64), nullable=False),
            sa.Column("page_from", sa.Integer()), sa.Column("page_to", sa.Integer()),
            sa.UniqueConstraint("document_id", "section_code", name="uk_nat_std_section"))
        op.create_index("ix_nat_std_section_document", "t_national_standard_section", ["document_id", "section_no"])

    if not _has_table("t_school_major_standard_binding"):
        op.create_table("t_school_major_standard_binding", *_tenant_common(),
            sa.Column("school_major_id", sa.BigInteger(), nullable=False),
            sa.Column("document_id", sa.BigInteger(), nullable=False),
            sa.Column("binding_status", sa.String(30), nullable=False), sa.Column("is_primary", sa.Boolean(), nullable=False),
            sa.Column("selected_at", sa.DateTime(), nullable=False), sa.Column("selected_by", sa.BigInteger()),
            sa.Column("note", sa.String(500)),
            sa.UniqueConstraint("tenant_id", "school_major_id", "document_id",
                                name="uk_school_major_standard_binding"))
        op.create_index("ix_school_major_std_binding", "t_school_major_standard_binding",
                        ["tenant_id", "school_major_id", "binding_status"])


def downgrade() -> None:
    for table_name in (
        "t_school_major_standard_binding",
        "t_national_standard_section",
        "t_national_standard_document",
        "t_national_major_catalog",
        "t_national_standard_source",
    ):
        if _has_table(table_name):
            op.drop_table(table_name)
