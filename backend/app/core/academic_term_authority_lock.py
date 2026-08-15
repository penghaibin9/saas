"""A-C1 当前学期写入的轻量租户协调锁。

这个模块不注册路由、不解释业务状态，只提供两个底层原语：

- ``lock_term_authority``：所有会改变“全校当前学期”的 writer 锁同一个租户锚点；
- ``active_governance_term_id``：判断 SYS-12 是否已经给出 ACTIVE 统一结论。

优先锁真实 ``Tenant``；历史迁移/SYS-12 fixture 缺 Tenant 父行时，退到该租户最早的
持久化 ``AaTerm``。函数内部延迟 import ORM，避免模型初始化循环。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException


def normalize_tenant_id(value) -> int:
    try:
        tenant_id = int(value or 0)
    except (TypeError, ValueError):
        tenant_id = 0
    if tenant_id <= 0:
        raise AppException(
            "TENANT_CONTEXT_REQUIRED",
            "当前学期写入缺少租户标识，拒绝猜测 Authority 范围",
            http_status=409,
        )
    return tenant_id


def lock_term_authority(db, tenant_id: int) -> bool:
    """Acquire one deterministic ``FOR UPDATE`` row for a tenant's current-term writers."""
    from app.models import AaTerm, Tenant

    tid = normalize_tenant_id(tenant_id)
    with db.no_autoflush:
        tenant_anchor = db.scalar(
            select(Tenant.id).where(Tenant.id == tid).with_for_update()
        )
        if tenant_anchor is not None:
            return True
        term_anchor = db.scalar(
            select(AaTerm.id)
            .where(
                AaTerm.tenant_id == tid,
                AaTerm.is_deleted.is_(False),
            )
            .order_by(AaTerm.id.asc())
            .limit(1)
            .with_for_update()
        )
    return term_anchor is not None


def active_governance_term_id(db, tenant_id: int) -> int | None:
    """Return the SYS-12 ACTIVE term, if any; uniqueness remains DB-enforced."""
    from app.models.academic_calendar import (
        ACTIVE_SENTINEL,
        CALENDAR_TYPE_ACADEMIC,
        AcademicCalendarGovernance,
    )

    tid = normalize_tenant_id(tenant_id)
    with db.no_autoflush:
        value = db.scalar(
            select(AcademicCalendarGovernance.term_id).where(
                AcademicCalendarGovernance.tenant_id == tid,
                AcademicCalendarGovernance.calendar_type == CALENDAR_TYPE_ACADEMIC,
                AcademicCalendarGovernance.active_key == ACTIVE_SENTINEL,
                AcademicCalendarGovernance.is_deleted.is_(False),
            )
        )
    return int(value) if value is not None else None
