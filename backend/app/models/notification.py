"""通知中心模型（P13-B）：通知任务 / 发送日志 / 模板。
短信/微信下发的可交付底座；当前默认 mock provider，不真实发送。
手机号一律脱敏展示，日志不落明文手机号（只存脱敏串 + hash 可选）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditTimeMixin, Base, CommonMixin, PKMixin, TenantMixin


class NotificationTemplate(Base, PKMixin, TenantMixin, CommonMixin):
    """通知模板：template_code + 渠道 + 内容（含 {var} 变量）。"""
    __tablename__ = "t_notification_template"

    template_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True,
                                               comment="业务模板键：TODO/REJECTED/WARNING...")
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="SMS", comment="SMS/WECHAT")
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(String(1000), nullable=False,
                                         comment="模板正文，变量占位如 {name}{title}")
    provider_template_id: Mapped[str | None] = mapped_column(String(100), comment="第三方模板ID（阿里/腾讯）")
    enabled: Mapped[bool] = mapped_column(default=True)


class NotificationTask(Base, PKMixin, TenantMixin, CommonMixin):
    """一条待发/已发通知任务。"""
    __tablename__ = "t_notification_task"

    biz_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True,
                                          comment="TODO/REJECTED/WARNING...")
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="SMS")
    template_code: Mapped[str | None] = mapped_column(String(64))
    receiver_name: Mapped[str | None] = mapped_column(String(100))
    receiver_phone_masked: Mapped[str | None] = mapped_column(String(32), comment="脱敏手机号，不落明文")
    payload_json: Mapped[dict | None] = mapped_column(JSON, comment="模板变量")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING",
                                        comment="PENDING/SENT/FAILED/SKIPPED")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500))


class NotificationLog(Base, PKMixin, TenantMixin, AuditTimeMixin):
    """发送日志（append-only）。"""
    __tablename__ = "t_notification_log"

    task_id: Mapped[int | None] = mapped_column(Integer, index=True)
    biz_type: Mapped[str | None] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="SMS")
    provider: Mapped[str | None] = mapped_column(String(20), comment="mock/aliyun/tencent")
    phone_masked: Mapped[str | None] = mapped_column(String(32))
    result: Mapped[str] = mapped_column(String(20), nullable=False, comment="SUCCESS/FAIL/SKIPPED")
    reason: Mapped[str | None] = mapped_column(String(500), comment="跳过/失败原因")
    request_id: Mapped[str | None] = mapped_column(String(100))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
