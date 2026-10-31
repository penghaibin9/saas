import hashlib
import os
import re
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import String, Integer, DateTime, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Mapped, mapped_column
from website_app.db import Base, get_sessionmaker
from website_app.auth import verify_origin
from website_app.errors import AppException, success
from website_app import consultations
from website_app.integrations.wechat import official_wechat_enabled, build_js_sdk_signature, OfficialWechatUpstreamError

router = APIRouter(prefix='/notification', tags=['官网咨询与分享'])
UNAVAILABLE = '在线咨询暂时不可用，请直接电话联系 135 4966 6867。已填写内容会保留。'

class WebsiteRate(Base):
    __tablename__ = 'website_public_rate'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    reset_at: Mapped[datetime] = mapped_column(DateTime, index=True)

class WebsiteLeadRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    school_name: str = Field(min_length=2, max_length=80)
    contact_name: str = Field(default='', max_length=40)
    phone: str = Field(pattern=r'^1[3-9][0-9]{9}$')
    interest: str = Field(min_length=2, max_length=40)
    message: str = Field(default='', max_length=200)
    website: str = Field(default='', max_length=120)
    source_path: str = Field(default='/contact', max_length=120)
    source_article: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    request_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    consent: bool = Field(default=False, strict=True)

    @field_validator('school_name','contact_name','interest','message','website','source_path', mode='before')
    @classmethod
    def clean(cls, value):
        return ' '.join(str(value or '').split())

def allow_lead(client_ip):
    salt = os.getenv('WEBSITE_LEAD_RATE_SALT', '')
    if len(salt) < 32: raise AppException('UNAVAILABLE', UNAVAILABLE, 503)
    key = hashlib.sha256((salt + '|' + client_ip).encode()).hexdigest()
    now = datetime.utcnow()
    with get_sessionmaker()() as db:
        db.execute(insert(WebsiteRate).values(key=key, attempts=0, reset_at=now+timedelta(hours=1)).on_duplicate_key_update(key=key))
        bucket = db.scalar(select(WebsiteRate).where(WebsiteRate.key == key).with_for_update())
        if bucket.reset_at <= now: bucket.attempts, bucket.reset_at = 0, now+timedelta(hours=1)
        if bucket.attempts >= 6: raise AppException('RATE_LIMITED', '提交过于频繁，请稍后再试或直接电话联系。', 429)
        bucket.attempts += 1
        db.commit()

def send_lead(body):
    provider = os.getenv('WEBSITE_SMS_PROVIDER', '')
    if provider == 'tencent':
        from website_app.integrations.tencent_sms_provider import TencentSmsProvider
        sender = TencentSmsProvider()
    elif provider == 'aliyun':
        from website_app.integrations.aliyun_sms_provider import AliyunSmsProvider
        sender = AliyunSmsProvider()
    else:
        return False
    recipient, template = os.getenv('WEBSITE_LEAD_NOTIFY_PHONE', ''), os.getenv('WEBSITE_SMS_TEMPLATE_LEAD', '')
    if not re.fullmatch(r'1[3-9][0-9]{9}', recipient) or not template: return False
    params = {'school':body.school_name[:30], 'contact':(body.contact_name or '未填写')[:12], 'phone':body.phone,
              'interest':body.interest[:16], 'message':(body.message or '希望进一步沟通')[:36]}
    # No automatic retry on an ambiguous network response, and no form body in logs or storage.
    return sender.send(recipient,template,params).success

@router.post('/website-lead')
def website_lead(body: WebsiteLeadRequest, request: Request):
    verify_origin(request)
    if body.website: raise AppException('INVALID', '提交内容不符合要求。', 400)
    if consultations.enabled():
        allow_lead(request.client.host if request.client else 'unknown')
        with get_sessionmaker()() as db:
            result = consultations.register(db, body)
            db.commit()
            return success(result, message='预约已登记')
    if os.getenv('WEBSITE_SMS_ENABLED', 'false').lower() != 'true': raise AppException('UNAVAILABLE',UNAVAILABLE,503)
    allow_lead(request.client.host if request.client else 'unknown')
    if not send_lead(body): raise AppException('UNAVAILABLE',UNAVAILABLE,503)
    return success({'accepted':True, 'mode':'sms'})

@router.get('/website-lead-capabilities')
def lead_capabilities(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    if consultations.enabled():
        with get_sessionmaker()() as db:
            try: consultations.ready(db)
            except AppException: return success({'mode':'unavailable'})
        return success({'mode':'registered', 'retentionDays': consultations.RETENTION_DAYS})
    # SMS capability is independent; this does not claim a supplier delivery.
    configured = (os.getenv('WEBSITE_SMS_ENABLED', 'false').lower() == 'true'
        and os.getenv('WEBSITE_SMS_PROVIDER') in ('aliyun', 'tencent')
        and bool(os.getenv('WEBSITE_SMS_TEMPLATE_LEAD'))
        and bool(re.fullmatch(r'1[3-9][0-9]{9}', os.getenv('WEBSITE_LEAD_NOTIFY_PHONE', ''))))
    return success({'mode':'sms' if configured else 'unavailable'})

@router.get('/website-wechat-signature')
def wechat_signature(url: str):
    if not official_wechat_enabled(): return success({'enabled':False})
    try: signed = build_js_sdk_signature(url)
    except ValueError as exc: raise AppException('INVALID','微信分享地址不符合官网范围。',422) from exc
    except OfficialWechatUpstreamError as exc: raise AppException('UNAVAILABLE','微信分享暂时不可用，请稍后重试。',503) from exc
    return success({'enabled':True, **signed})
