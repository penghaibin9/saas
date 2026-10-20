"""Public website editorial data. Platform-owned; never stores school tenant records."""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, JSON, ForeignKey, UniqueConstraint, Index, LargeBinary
from sqlalchemy.dialects.mysql import LONGBLOB, MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class NewsPackage(Base):
    __tablename__ = "t_website_news_package"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(24), default="REVIEW", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_signature: Mapped[str | None] = mapped_column(String(64))
    imported_by: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (Index("ix_news_package_created", "created_at", "id"),)

class NewsArticle(Base):
    __tablename__ = "t_website_news_article"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    package_id: Mapped[str] = mapped_column(ForeignKey("t_website_news_package.id"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(String(600), nullable=False)
    body: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    slug: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    issue: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    sources: Mapped[list] = mapped_column(JSON, nullable=False)
    media_map: Mapped[dict] = mapped_column(JSON, nullable=False)
    cover_id: Mapped[str | None] = mapped_column(String(64))
    ai_assisted: Mapped[bool] = mapped_column(default=True, nullable=False)
    content_kind: Mapped[str] = mapped_column(String(24), default="summary", nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (
        UniqueConstraint("package_id", "ordinal", name="uq_news_package_ordinal"),
        Index("ix_news_due", "state", "scheduled_at", "id"),
        Index("ix_news_public", "state", "category", "published_at", "id"),
    )

class NewsMedia(Base):
    __tablename__ = "t_website_news_media"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary().with_variant(LONGBLOB(), "mysql"), nullable=False)
    mime: Mapped[str] = mapped_column(String(40), nullable=False)

class NewsMediaLink(Base):
    __tablename__ = "t_website_news_media_link"
    article_id: Mapped[str] = mapped_column(ForeignKey("t_website_news_article.id"), primary_key=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("t_website_news_media.id"), primary_key=True)
    __table_args__ = (Index("ix_news_media_usage", "media_id", "article_id"),)

class NewsDispatch(Base):
    __tablename__ = "t_website_news_dispatch"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_slot: Mapped[datetime | None] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str] = mapped_column(String(600), default="", nullable=False)

class NewsAudit(Base):
    __tablename__ = "t_website_news_audit"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    event_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    package_id: Mapped[str] = mapped_column(String(32), nullable=False)
    article_id: Mapped[str | None] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (Index("ix_news_audit_package", "package_id", "created_at"),)
