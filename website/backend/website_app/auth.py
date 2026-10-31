"""Independent website identities and revocable sessions. No student tokens."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from uuid import uuid4
from fastapi import APIRouter, Request, Response, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, DateTime, Integer, Boolean, ForeignKey, select, delete
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Mapped, mapped_column
from website_app.db import Base, get_sessionmaker
from website_app.errors import AppException, success

COOKIE = os.environ.get('WEBSITE_SESSION_COOKIE', 'yueke_website_session')
if not COOKIE.replace('_', '').isalnum() or len(COOKIE) > 80:
    raise RuntimeError('官网会话名称不符合要求')
router = APIRouter(prefix='/auth', tags=['官网登录'])

class WebsiteUser(Base):
    __tablename__ = 'website_user'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class WebsiteSession(Base):
    __tablename__ = 'website_session'
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('website_user.id'), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

class LoginAttempt(Base):
    __tablename__ = 'website_login_attempt'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    reset_at: Mapped[datetime] = mapped_column(DateTime, index=True)

class AuthAudit(Base):
    __tablename__ = 'website_auth_audit'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

def origin():
    value = os.environ.get('WEBSITE_ORIGIN', 'http://127.0.0.1:5210').rstrip('/')
    parsed = urlsplit(value)
    if parsed.path or parsed.query or parsed.fragment or parsed.username or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost'))):
        raise RuntimeError('官网来源必须为正式 HTTPS 地址或本机开发地址')
    return value

def verify_origin(request):
    if request.headers.get('origin') != origin():
        raise AppException('FORBIDDEN', '请求来源不受信任，请从官网后台重新操作。', 403)

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def hash_password(password):
    if not 12 <= len(password) <= 256:
        raise ValueError('密码长度须为 12 至 256 个字符')
    salt = secrets.token_hex(16)
    hashed = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'scrypt${salt}${hashed}'

def verify_password(password, encoded):
    try:
        kind, salt, expected = encoded.split('$')
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return kind == 'scrypt' and hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def payload(user, token):
    return {'user': {'id': user.id, 'displayName': user.display_name, 'role': user.role}, 'csrfToken': digest('csrf:' + token)}

def require_editor(request: Request):
    token = request.cookies.get(COOKIE, '')
    if not token or len(token) > 100:
        raise AppException('UNAUTHORIZED', '请登录官网管理后台。', 401)
    with get_sessionmaker()() as db:
        session = db.get(WebsiteSession, digest(token))
        user = db.get(WebsiteUser, session.user_id) if session and session.expires_at > datetime.utcnow() else None
        if not user or not user.active:
            raise AppException('UNAUTHORIZED', '请登录官网管理后台。', 401)
        if user.role not in ('editor', 'publisher', 'superadmin'):
            raise AppException('FORBIDDEN', '当前账号没有官网内容管理权限。', 403)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            verify_origin(request)
            if not hmac.compare_digest(request.headers.get('x-website-csrf', ''), digest('csrf:' + token)):
                raise AppException('FORBIDDEN', '操作凭据已失效，请刷新后重试。', 403)
        return {'userId': user.id, **payload(user, token)}

def require_publisher(user=Depends(require_editor)):
    if user['user']['role'] not in ('publisher', 'superadmin'):
        raise AppException('FORBIDDEN', '当前账号可以编辑和审核内容，发布操作需要发布人员账号。', 403)
    return user

def require_superadmin(user=Depends(require_editor)):
    if user['user']['role'] != 'superadmin':
        raise AppException('FORBIDDEN', '咨询资料仅限官网超级管理员查看和处理。', 403)
    return user

class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_.@-]+$')
    password: str = Field(min_length=1, max_length=256)

@router.post('/login')
def login(body: Login, request: Request, response: Response):
    verify_origin(request)
    now = datetime.utcnow()
    with get_sessionmaker()() as db:
        # Lock in fixed order; limits are shared by all website worker processes.
        keys = sorted([digest('user:' + body.username.lower()), digest('ip:' + (request.client.host if request.client else 'unknown'))])
        buckets = []
        for key in keys:
            db.execute(insert(LoginAttempt).values(key=key, attempts=0, reset_at=now + timedelta(minutes=15)).on_duplicate_key_update(key=key))
            bucket = db.scalar(select(LoginAttempt).where(LoginAttempt.key == key).with_for_update())
            if bucket.reset_at <= now:
                bucket.attempts, bucket.reset_at = 0, now + timedelta(minutes=15)
            buckets.append(bucket)
        if any(b.attempts >= 10 for b in buckets):
            raise AppException('RATE_LIMITED', '登录尝试过多，请 15 分钟后再试。', 429)
        for bucket in buckets:
            bucket.attempts += 1
        user = db.scalar(select(WebsiteUser).where(WebsiteUser.username == body.username.lower()).with_for_update())
        # Perform the same expensive hash for unknown users, without creating an account.
        encoded = user.password_hash if user else 'scrypt$' + '00' * 16 + '$' + '00' * 64
        valid = verify_password(body.password, encoded)
        if not user or not user.active or not valid:
            db.add(AuthAudit(id=uuid4().hex, user_id=user.id if user else None, action='LOGIN_REJECTED'))
            db.commit()
            raise AppException('UNAUTHORIZED', '账号或密码不正确，或账号已停用。', 401)
        for bucket in buckets:
            bucket.attempts = 0
        old = request.cookies.get(COOKIE)
        if old:
            db.execute(delete(WebsiteSession).where(WebsiteSession.digest == digest(old)))
        db.execute(delete(WebsiteSession).where(WebsiteSession.expires_at < now))
        token = secrets.token_urlsafe(32)
        db.add(WebsiteSession(digest=digest(token), user_id=user.id, expires_at=now + timedelta(hours=8)))
        db.add(AuthAudit(id=uuid4().hex, user_id=user.id, action='LOGIN'))
        db.commit()
        response.set_cookie(COOKIE, token, max_age=8*3600, httponly=True, secure=origin().startswith('https://'), samesite='strict', path='/api')
        response.headers['Cache-Control'] = 'no-store'
        return success(payload(user, token))

@router.get('/session')
def session(response: Response, user=Depends(require_editor)):
    response.headers['Cache-Control'] = 'no-store'
    return success({'user': user['user'], 'csrfToken': user['csrfToken']})

@router.post('/logout')
def logout(request: Request, response: Response, user=Depends(require_editor)):
    with get_sessionmaker()() as db:
        db.execute(delete(WebsiteSession).where(WebsiteSession.digest == digest(request.cookies[COOKIE])))
        db.add(AuthAudit(id=uuid4().hex, user_id=user['userId'], action='LOGOUT'))
        db.commit()
    response.delete_cookie(COOKIE, path='/api', secure=origin().startswith('https://'), httponly=True, samesite='strict')
    return success(message='已退出官网后台')
