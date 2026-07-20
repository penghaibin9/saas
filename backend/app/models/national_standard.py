"""职业教育国家标准库：官方来源、专业目录、标准正文、章节和学校专业绑定。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Boolean, Date, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CommonMixin, PKMixin, TenantMixin

LongText = Text().with_variant(LONGTEXT(), "mysql")


class NationalStandardSource(PKMixin, CommonMixin, Base):
    __tablename__ = "t_national_standard_source"
    __table_args__ = (UniqueConstraint("source_key", "version_label", name="uk_nat_std_source_version"),)

    source_key: Mapped[str] = mapped_column(String(80), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    publisher: Mapped[str] = mapped_column(String(100), nullable=False, default="中华人民共和国教育部")
    version_label: Mapped[str] = mapped_column(String(40), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    published_date: Mapped[date | None] = mapped_column(Date)
    is_official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    copyright_policy: Mapped[str] = mapped_column(String(40), nullable=False, default="INTERNAL_SEARCH_LINK_SOURCE")
    retrieval_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class NationalMajorCatalog(PKMixin, CommonMixin, Base):
    __tablename__ = "t_national_major_catalog"
    __table_args__ = (
        UniqueConstraint("catalog_version", "education_level", "major_code",
                         name="uk_nat_major_version_level_code"),
        Index("ix_nat_major_level_code", "education_level", "major_code"),
        Index("ix_nat_major_class", "major_class_code"),
    )

    source_id: Mapped[int | None] = mapped_column(BigInteger)
    catalog_version: Mapped[str] = mapped_column(String(40), nullable=False, default="2021")
    education_level: Mapped[str] = mapped_column(String(40), nullable=False)
    category_code: Mapped[str | None] = mapped_column(String(20))
    category_name: Mapped[str | None] = mapped_column(String(100))
    major_class_code: Mapped[str | None] = mapped_column(String(20))
    major_class_name: Mapped[str | None] = mapped_column(String(100))
    major_code: Mapped[str] = mapped_column(String(30), nullable=False)
    major_name: Mapped[str] = mapped_column(String(200), nullable=False)
    directory_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    effective_date: Mapped[date | None] = mapped_column(Date)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class NationalStandardDocument(PKMixin, CommonMixin, Base):
    __tablename__ = "t_national_standard_document"
    __table_args__ = (
        UniqueConstraint("standard_code", "version_label", name="uk_nat_std_document_version"),
        Index("ix_nat_std_document_level_major", "education_level", "major_code"),
        Index("ix_nat_std_document_text_status", "text_status"),
        Index("ix_nat_std_document_sha", "source_sha256"),
    )

    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    major_catalog_id: Mapped[int | None] = mapped_column(BigInteger)
    standard_code: Mapped[str] = mapped_column(String(100), nullable=False)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, default="PROFESSIONAL_TEACHING_STANDARD")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    education_level: Mapped[str] = mapped_column(String(40), nullable=False)
    major_code: Mapped[str] = mapped_column(String(30), nullable=False)
    major_name: Mapped[str] = mapped_column(String(200), nullable=False)
    version_label: Mapped[str] = mapped_column(String(40), nullable=False)
    published_date: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_file_name: Mapped[str | None] = mapped_column(String(300))
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    page_count: Mapped[int | None] = mapped_column(Integer)
    text_status: Mapped[str] = mapped_column(String(30), nullable=False, default="METADATA_ONLY")
    full_text: Mapped[str | None] = mapped_column(LongText)
    structured_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PUBLISHED")
    extraction_error: Mapped[str | None] = mapped_column(String(1000))


class NationalStandardSection(PKMixin, CommonMixin, Base):
    __tablename__ = "t_national_standard_section"
    __table_args__ = (
        UniqueConstraint("document_id", "section_code", name="uk_nat_std_section"),
        Index("ix_nat_std_section_document", "document_id", "section_no"),
    )

    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    section_code: Mapped[str] = mapped_column(String(50), nullable=False)
    section_no: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_text: Mapped[str] = mapped_column(LongText, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_from: Mapped[int | None] = mapped_column(Integer)
    page_to: Mapped[int | None] = mapped_column(Integer)


class SchoolMajorStandardBinding(PKMixin, TenantMixin, CommonMixin, Base):
    __tablename__ = "t_school_major_standard_binding"
    __table_args__ = (
        UniqueConstraint("tenant_id", "school_major_id", "document_id",
                         name="uk_school_major_standard_binding"),
        Index("ix_school_major_std_binding", "tenant_id", "school_major_id", "binding_status"),
    )

    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    school_major_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    binding_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    selected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    selected_by: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(String(500))
