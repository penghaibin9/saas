"""Minimal student-PC shell endpoints owned by internship standalone.

Do not import the parent SaaS mobile aggregation router here. The standalone
student PC needs only its own brand/module projection; internship business truth
continues to come from /portal/internship/* and shared internship services.
"""
from __future__ import annotations

from sqlalchemy import select

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from app.config import settings
from app.core.exceptions import not_found, unauthorized
from app.core.response import success
from app.core.security import require_mobile_student
from app.db.session import get_sessionmaker
from app.models import Tenant
from app.models.tenant import TenantBrandConfig
from app.services import message_center_service, system_settings
from app.services.db_service import _tid
from app.services.module_access_service import assert_module_access

router = APIRouter(prefix="/mobile/me", tags=["Standalone student PC shell"])


@router.get("/portal-config", summary="Standalone 学生 PC 岗位实习门户配置")
def portal_config(user=Depends(require_mobile_student)):
    raw_tenant = str((user or {}).get("tenantId") or (user or {}).get("tenant_id") or "")
    if not raw_tenant.isdigit() or int(raw_tenant) <= 0:
        raise unauthorized("学生令牌缺少学校上下文")
    tenant_id = int(raw_tenant)

    db = get_sessionmaker()()
    try:
        tenant = db.scalar(select(Tenant).where(
            Tenant.id == tenant_id,
            Tenant.is_deleted.is_(False),
            Tenant.status == "ACTIVE",
        ))
        if not tenant:
            raise unauthorized("学校不存在或已停用")
        brand = db.scalar(select(TenantBrandConfig).where(
            TenantBrandConfig.tenant_id == tenant_id,
            TenantBrandConfig.is_deleted.is_(False),
        ))
        return success({
            **system_settings.school_service_config(user),
            "enabled": True,
            "modules": {"internship": True},
            "features": {},
            "brand": {
                **system_settings.brand(db,user),
                "schoolName": tenant.school_name,
                "platformName": (
                    getattr(brand, "platform_name", None)
                    or settings.APP_NAME
                    or "跃科岗位实习管理平台"
                ),
                "platformSubtitle": getattr(brand, "platform_subtitle", None) or "",
                "primaryColor": getattr(brand, "primary_color", None) or "#2f6bff",
            },
        })
    finally:
        db.close()


def _message_student(request: Request, user=Depends(require_mobile_student)):
    assert_module_access(_tid(), "internship", write=request.method == "POST")
    return user


@router.get("/messages", summary="学生本人岗位实习消息")
def student_messages(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100),
                     readStatus: Literal["UNREAD", "READ"] | None = Query(None),
                     user=Depends(_message_student)):
    items, total = message_center_service.list_messages(
        user, page=page, page_size=pageSize, read_status=readStatus, source_module="internship")
    return success({"items": items, "total": total, "page": page, "pageSize": pageSize,
                    "hasMore": page * pageSize < total})


@router.get("/messages/count", summary="学生本人岗位实习未读计数")
def student_message_count(user=Depends(_message_student)):
    return success(message_center_service.count_messages(user, source_module="internship"))


@router.get("/messages/{message_id}", summary="学生本人岗位实习消息正文")
def student_message_detail(message_id: str, user=Depends(_message_student)):
    result = message_center_service.get_message(user, message_id, source_module="internship")
    if result is None:
        raise not_found("消息不存在或不属于本人岗位实习收件箱")
    return success(result)


@router.post("/messages/{message_id}/read", summary="学生明确标记本人实习消息已读")
def student_message_read(message_id: str, user=Depends(_message_student)):
    result = message_center_service.read_message(user, message_id, source_module="internship")
    if result is None:
        raise not_found("消息不存在或不属于本人岗位实习收件箱")
    return success(result, message="已标记为已读")
