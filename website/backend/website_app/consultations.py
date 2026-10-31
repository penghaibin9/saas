"""Website-owned encrypted consultations. Fixed, owner-approved 90 day retention."""
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta
from uuid import uuid4
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, select, func, delete
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Mapped, mapped_column
from website_app.auth import WebsiteUser, require_superadmin
from website_app.db import Base, get_sessionmaker
from website_app.errors import AppException, success
from website_app.news.service import product_catalog, iso
from website_app.news.models import NewsArticle

RETENTION_DAYS = 90
UNAVAILABLE = '在线咨询暂时不可用，请直接电话联系 135 4966 6867。已填写内容会保留。'
router = APIRouter(prefix='/manage/consultations', tags=['官网咨询受理'])

class Consultation(Base):
    __tablename__ = 'website_consultation'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(32), unique=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    private_data: Mapped[str] = mapped_column(Text)
    phone_mask: Mapped[str] = mapped_column(String(20))
    source_path: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    version: Mapped[int] = mapped_column(Integer, default=0)

class ConsultationAudit(Base):
    __tablename__ = 'website_consultation_audit'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    consultation_id: Mapped[str] = mapped_column(ForeignKey('website_consultation.id', ondelete='CASCADE'), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime)

def enabled():
    return os.getenv('WEBSITE_CONSULTATION_ENABLED', 'false').lower() == 'true'

def cipher():
    # Same authenticated-encryption primitive as the school field helper, with an
    # independent key and no imports/configuration from the school application.
    try:
        key = os.environ['WEBSITE_CONSULTATION_KEY'].encode('ascii')
        return Fernet(key), key
    except (KeyError, ValueError, UnicodeError) as exc:
        raise AppException('UNAVAILABLE', UNAVAILABLE, 503) from exc

def seal(data):
    return 'w1:' + cipher()[0].encrypt(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).decode()

def unseal(value):
    try:
        if not value.startswith('w1:'): raise ValueError('Invalid envelope')
        return json.loads(cipher()[0].decrypt(value[3:].encode()))
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise AppException('UNAVAILABLE', '咨询资料暂时无法读取，请联系官网维护人员。', 503) from exc

def ready(db):
    if not enabled(): raise AppException('UNAVAILABLE', UNAVAILABLE, 503)
    cipher()
    if not db.scalar(select(WebsiteUser.id).where(WebsiteUser.role == 'superadmin', WebsiteUser.active.is_(True)).limit(1)):
        raise AppException('UNAVAILABLE', UNAVAILABLE, 503)

def interests():
    values = {p.get('interest') or p['name'] for p in product_catalog().values()}
    return values | {'教务系统', '学工中心', '毕业设计', '教务与微信小程序', '整体解决方案', '私有化部署与系统集成', '数字迎新'}

def register(db, body, at=None):
    ready(db)
    if not body.request_id or not body.consent:
        raise AppException('INVALID', '请确认咨询资料的用途与 90 天保存期限后再提交。', 400)
    if body.interest not in interests(): raise AppException('INVALID', '请选择官网现有的产品或方案。', 400)
    data = {'schoolName': body.school_name, 'contactName': body.contact_name,
            'phone': body.phone, 'interest': body.interest, 'message': body.message, 'note': ''}
    source = body.source_path if body.source_path in ('/contact', '/#showcase') else '/contact'
    if body.source_article:
        article = db.get(NewsArticle, body.source_article)
        if not article or article.state != 'PUBLISHED': raise AppException('INVALID', '来源文章暂不可用，请从预约页面重新提交。', 400)
        source = '/news/' + article.slug
    fingerprint = hmac.new(cipher()[1], json.dumps({**data, 'source': source}, ensure_ascii=False, sort_keys=True).encode(), hashlib.sha256).hexdigest()
    now = at or datetime.utcnow()
    candidate = uuid4().hex
    # The unique key and row lock make same-request retries atomic across workers.
    db.execute(insert(Consultation).values(id=candidate, request_id=body.request_id, fingerprint=fingerprint,
        private_data=seal(data), phone_mask=body.phone[:3]+'****'+body.phone[-4:], source_path=source,
        created_at=now, expires_at=now+timedelta(days=RETENTION_DAYS), version=0).on_duplicate_key_update(request_id=body.request_id))
    row = db.scalar(select(Consultation).where(Consultation.request_id == body.request_id).with_for_update())
    if row.fingerprint != fingerprint or row.expires_at <= now:
        raise AppException('CONFLICT', '本次预约内容已变化或登记已到期，请重新打开预约页核对后提交。', 409)
    if row.id == candidate:
        audit(db, row.id, None, 'REGISTER', now)
    return {'accepted': True, 'mode': 'registered', 'receipt': row.id, 'retentionDays': RETENTION_DAYS}

def audit(db, cid, actor, action, at=None):
    db.add(ConsultationAudit(id=uuid4().hex, consultation_id=cid, actor_id=actor, action=action, created_at=at or datetime.utcnow()))

def active(db, cid, lock=False):
    query = select(Consultation).where(Consultation.id == cid, Consultation.expires_at > datetime.utcnow())
    row = db.scalar(query.with_for_update() if lock else query)
    if not row: raise AppException('NOT_FOUND', '咨询记录不存在或已到期。', 404)
    return row

def serialize(row, full=False):
    data = unseal(row.private_data)
    result = {'id': row.id, 'schoolName': data['schoolName'], 'contactName': data['contactName'],
        'phone': data['phone'] if full else row.phone_mask, 'interest': data['interest'],
        'createdAt': iso(row.created_at), 'expiresAt': iso(row.expires_at), 'version': row.version}
    if full: result.update(message=data['message'], note=data['note'], sourcePath=row.source_path)
    return result

@router.get('')
def listing(page: int = Query(1, ge=1), user=Depends(require_superadmin)):
    with get_sessionmaker()() as db:
        ready(db)
        query = select(Consultation).where(Consultation.expires_at > datetime.utcnow())
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        rows = list(db.scalars(query.order_by(Consultation.created_at.desc(), Consultation.id).offset((page-1)*20).limit(20)))
        data = [serialize(row) for row in rows]
        for row in rows: audit(db, row.id, user['userId'], 'READ_LIST')
        db.commit()
        return success({'items': data, 'total': total, 'page': page, 'retentionDays': RETENTION_DAYS})

@router.get('/{cid}')
def detail(cid: str, user=Depends(require_superadmin)):
    with get_sessionmaker()() as db:
        ready(db)
        row = active(db, cid, lock=True)
        data = serialize(row, full=True)
        audit(db, row.id, user['userId'], 'READ_DETAIL')
        db.commit()
        return success(data)

class Note(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expectedVersion: int = Field(ge=0, strict=True)
    note: str = Field(max_length=1000)

@router.put('/{cid}/note')
def note(cid: str, body: Note, user=Depends(require_superadmin)):
    with get_sessionmaker()() as db:
        ready(db)
        row = active(db, cid, lock=True)
        if row.version != body.expectedVersion:
            raise AppException('CONFLICT', '咨询记录已被更新，输入已保留；请重新读取记录后核对再保存。', 409)
        data = unseal(row.private_data)
        data['note'] = body.note.strip()
        row.private_data = seal(data)
        row.version += 1
        audit(db, row.id, user['userId'], 'UPDATE_NOTE')
        db.commit()
        return success({'version': row.version}, message='跟进记录已保存')

def purge_expired(db, at=None, limit=100):
    """Delete only this feature's owned rows and cascaded audit, in bounded batches."""
    if not enabled(): return 0
    now = at or datetime.utcnow()
    rows = list(db.scalars(select(Consultation.id).where(Consultation.expires_at <= now)
        .order_by(Consultation.expires_at, Consultation.id).limit(limit).with_for_update(skip_locked=True)))
    if rows: db.execute(delete(Consultation).where(Consultation.id.in_(rows)))
    return len(rows)
