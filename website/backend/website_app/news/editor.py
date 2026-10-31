"""Manual drafts reuse package validation, locking and the existing approval queue."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator
from sqlalchemy import select, delete
from website_app.news import service
from website_app.news.models import NewsPackage, NewsArticle, NewsRevision, NewsMediaLink, NewsMedia, NewsAudit
from website_app.news.package import validate_article, digest, canonical, public_url, PackageError

class Source(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(default='', max_length=240)
    url: str = Field(default='', max_length=1800)
    published_at: str | None = Field(default=None, max_length=40)

    @field_validator('url')
    @classmethod
    def source_url(cls, value):
        return public_url(value) if value else ''

    @field_validator('published_at')
    @classmethod
    def source_date(cls, value):
        if not value: return None
        return datetime.fromisoformat(value.replace('Z', '+00:00')).isoformat()

class Draft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(default='', max_length=600)
    body: str = Field(default='', max_length=50000)
    category: Literal['academic','affairs','internship','graduation','hr','policy','technology','company'] = 'company'
    contentKind: Literal['summary','original','product-update'] = 'original'
    aiAssisted: StrictBool = False
    sources: list[Source] = Field(default_factory=list, max_length=12)
    sourceType: Literal['original','licensed-repost','unverified'] = 'original'
    authorName: str = Field(default='', max_length=120)
    editorName: str = Field(default='', max_length=120)
    rightsBasis: str = Field(default='', max_length=1000)
    rightsScope: str = Field(default='', max_length=1000)
    rightsEvidence: str = Field(default='', max_length=12000)
    rightsValidUntil: datetime | None = None
    relatedProducts: list[str] = Field(default_factory=list, max_length=12)

    @field_validator('rightsValidUntil')
    @classmethod
    def utc_expiry(cls, value):
        from datetime import timezone
        if value and not value.tzinfo: raise ValueError('授权到期时间须包含时区')
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value else None

    @field_validator('relatedProducts')
    @classmethod
    def products(cls, value):
        if not set(value) <= set(service.product_catalog()): raise ValueError('只能关联已有公开资料的产品')
        return list(dict.fromkeys(value))

    @field_validator('title', 'summary', 'body', mode='before')
    @classmethod
    def clean_text(cls, value):
        if not isinstance(value, str): return value
        if '\x00' in value: raise ValueError('正文不能包含空字符')
        return value.strip()

class CreateDraft(Draft):
    requestId: str = Field(pattern=r'^[A-Za-z0-9-]{16,64}$')

class UpdateDraft(Draft):
    expectedVersion: StrictInt = Field(ge=0)
    revisionId: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')

def normalized(body, article=None, available_media=None):
    sources = [item.model_dump(exclude_none=True) for item in body.sources]
    meta = {'title': body.title, 'summary': body.summary, 'category': body.category,
            'content_kind': body.contentKind, 'ai_assisted': body.aiAssisted, 'sources': sources,
            'file': 'articles/draft.md'}
    media = article.media_map if article else {}
    if article and article.cover_id:
        meta['cover'] = next((name for name, mid in media.items() if mid == article.cover_id), None)
    row = validate_article(meta, getattr(article,'ordinal',1) if article else 1,
                           lambda _: body.body.encode('utf-8'),
                           {name: {'id': mid} for name, mid in media.items() if available_media is None or mid in available_media}, {})
    # Incomplete drafts must retain the text entered. Validation controls readiness.
    row.update(title=body.title, summary=body.summary, body=body.body, sources=sources,
               category=body.category, content_kind=body.contentKind, ai_assisted=body.aiAssisted)
    if row['state'] != 'READY':
        row.update(media_map=media, cover_id=article.cover_id if article else None)
    return row

def create(db, body, actor):
    service.dispatch(db)
    identity = digest('manual-draft:' + body.requestId)
    content_digest = digest(canonical(body.model_dump(mode='json',exclude={'requestId'})))
    previous = db.scalar(select(NewsPackage).where(NewsPackage.sha256 == identity))
    if previous:
        event = db.scalar(select(NewsAudit).where(NewsAudit.package_id == previous.id, NewsAudit.action == 'CREATE_DRAFT'))
        if not event or event.detail.get('contentDigest') != content_digest:
            raise service.NewsError('本次保存编号已用于其他内容，请重新打开撰写入口。')
        return previous, db.scalar(select(NewsArticle).where(NewsArticle.package_id == previous.id))
    row = normalized(body)
    parsed = {'sha256': identity, 'title': body.title[:200], 'articles': [row], 'assets': {},
              'review_digest': digest(canonical([row]))}
    package, _ = service.import_package(db, parsed, '网页撰写草稿', actor)
    article = db.scalar(select(NewsArticle).where(NewsArticle.package_id == package.id))
    apply_metadata(article, body)
    article.editorial_state = 'DRAFT'
    service.redigest(db, package)
    service.audit(db, package, actor, 'CREATE_DRAFT', {'contentDigest': content_digest}, article=article.id)
    return package, article

def apply_metadata(article, body):
    for key, field in service.METADATA_FIELDS.items(): setattr(article, field, getattr(body,key))

def update(db, aid, body, actor):
    service.dispatch(db)
    article = db.get(NewsArticle, aid)
    if not article: raise service.NewsError('文章不存在', 404)
    package = service.package(db, article.package_id, True)
    if package.version != body.expectedVersion:
        raise service.NewsError('新闻已被其他人员修改。你的输入已保留，请先核对最新版本。')
    article = service.editable_target(db, article, body.revisionId)
    if article.editorial_state not in ('DRAFT','RETURNED','APPROVED','LEGACY') or article.state == 'SCHEDULED':
        raise service.NewsError('当前内容已提交审核或排期，请先撤回对应流程。')
    # Invalid imported rows may mention images that were never persisted.
    # Revalidate against stored media, so editing cannot publish broken images
    # or insert links to missing foreign keys.
    available = set(db.scalars(select(NewsMedia.id).where(NewsMedia.id.in_(set(article.media_map.values())))))
    row = normalized(body, article, available)
    if row['dedupe_key'] and db.scalar(select(NewsArticle.id).where(NewsArticle.dedupe_key == row['dedupe_key'], NewsArticle.id != aid).limit(1)):
        row.update(state='DUPLICATE', issue='与已有新闻正文重复，不能重复发布', dedupe_key=None)
    for key, value in row.items():
        if hasattr(article,key): setattr(article, key, value)
    apply_metadata(article, body)
    article.editorial_state, article.approved_digest = 'DRAFT', None
    article.updated_at = service.now()
    if not isinstance(article, NewsRevision): service.sync_media_links(db,article)
    package.version += 1
    if package.filename == '网页撰写草稿' and not isinstance(article,NewsRevision): package.title = body.title[:200]
    service.redigest(db, package)
    service.audit(db, package, actor, 'EDIT_DRAFT', {'version': package.version}, article=aid)
    db.flush()
    return package, article
