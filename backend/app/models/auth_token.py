"""认证令牌持久化（多 worker / 重启存活）。
────────────────────────────────────────────────────────────
- t_auth_refresh_token：refreshToken 只存 sha256 哈希（库泄露不可用），
  轮换=删除旧行；多 worker 共享同一份状态。
- t_auth_blocked_jti：登出后的 accessToken jti 黑名单，到期行可被惰性清理。
DB_ENABLED=false 时 token_store 回落内存实现（演示/单机模式，行为不变）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin


class AuthRefreshToken(Base, PKMixin):
    __tablename__ = "t_auth_refresh_token"

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    claims_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class AuthBlockedJti(Base, PKMixin):
    __tablename__ = "t_auth_blocked_jti"

    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
