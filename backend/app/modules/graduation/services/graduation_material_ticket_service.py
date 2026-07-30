"""毕业设计材料短时预览/下载票据；签发与消费都重新执行公共文件授权和安全门。"""
from __future__ import annotations

import time
import uuid

import jwt

from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found
from app.modules.graduation.services import graduation_material_center_service as center
from app.services.file_access_service import require_file_access
from app.services.message_identity import resolve_message_user_id

TICKET_TTL_SECONDS = 180


def _tenant() -> int:
    value = int(current_tenant_id() or 0)
    if not value:
        raise not_found("毕业设计材料不存在")
    return value


def _actor(user: dict) -> str:
    return str(resolve_message_user_id(user or {}) or (user or {}).get("userId") or (user or {}).get("sub") or "")


def issue_ticket(file_id: int, action: str, user: dict) -> dict:
    normalized = str(action or "").lower()
    if normalized not in {"preview", "download"}:
        raise AppException("VALIDATION_ERROR", "票据动作仅支持 preview/download")
    # 签发前执行 resolver + scan/file status；不信任页面 allowedActions。
    require_file_access(str(file_id), user=user, action=normalized)
    center.resolve_material_download(int(file_id), user, student_mode=False)
    now = int(time.time())
    token = jwt.encode({
        "typ": "gd-material-ticket", "jti": uuid.uuid4().hex,
        "tenantId": _tenant(), "fileId": int(file_id), "action": normalized,
        "actor": _actor(user), "iat": now, "exp": now + TICKET_TTL_SECONDS,
    }, settings.JWT_SECRET, algorithm=settings.JWT_ALG)
    return {
        "ticket": token, "action": normalized, "expiresIn": TICKET_TTL_SECONDS,
        "url": f"/api/v1/graduation/material-center/files/{int(file_id)}/{normalized}?ticket={token}",
    }


def consume_ticket(file_id: int, action: str, ticket: str, user: dict):
    try:
        payload = jwt.decode(str(ticket or ""), settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except Exception:
        raise not_found("毕业设计材料不存在")
    normalized = str(action or "").lower()
    if (
        payload.get("typ") != "gd-material-ticket"
        or int(payload.get("tenantId") or 0) != _tenant()
        or int(payload.get("fileId") or 0) != int(file_id)
        or payload.get("action") != normalized
        or str(payload.get("actor") or "") != _actor(user)
    ):
        raise not_found("毕业设计材料不存在")
    # 消费时重新核验：票据签发后文件被隔离、版本失效或业务范围变化均立即拒绝。
    require_file_access(str(file_id), user=user, action=normalized)
    return center.resolve_material_download(int(file_id), user, student_mode=False)
