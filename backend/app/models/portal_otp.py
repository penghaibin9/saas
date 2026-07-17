"""学生 PC 门户 · 登录一次性验证码（OTP）。

用于家长（proxy）手机号验证码登录：请求时按手机号 hash 落一条 OTP（code 只存 hash），
校验成功即置 consumed；限次 attempts。非 append-only（consumed/attempts 可变），故不继承 CommonMixin。
生产 SMS 开启时验证码只经短信下发；SMS 未开启（dev/test）由服务层回带 devCode 供联调。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TenantMixin


class PortalLoginOtp(PKMixin, TenantMixin, Base):
    """t_portal_login_otp：门户登录验证码（行级隔离 tenant_id）。"""
    __tablename__ = "t_portal_login_otp"

    phone_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="手机号 hash")
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False, comment="验证码 hash（不存明文）")
    purpose: Mapped[str] = mapped_column(String(30), nullable=False, default="GUARDIAN_LOGIN",
                                         comment="用途：GUARDIAN_LOGIN")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="过期时间")
    consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否已使用")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="错误尝试次数")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
