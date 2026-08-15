"""A-C1 当前学期写入的轻量 Authority 原语。

本模块不注册路由、不创建新表，只提供可由模型事件和正式 service 共用的底层能力：

- ``lock_term_authority``：所有会改变“全校当前学期”的 writer 锁同一个租户锚点；
- ``active_governance_term_id``：读取 SYS-12 已给出的 ACTIVE 统一结论；
- ``guard_current_term_target``：在 ``AaTerm.is_current=True`` 真正落库前串行、对齐治理
  Authority，并清掉同租户其它 current。

优先锁真实 ``Tenant``；历史迁移/SYS-12 fixture 缺 Tenant 父行时，退到该租户最早的
持久化 ``AaTerm``。函数内部延迟 import ORM，避免模型初始化循环。
"""
from __future__ import annotations

from sqlalchemy import select, update

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


def guard_current_term_target(db, target) -> None:
    """Serialize and validate one formal ``AaTerm.is_current=True`` target.

    The caller may be a Web service, migration import, script or isolated test.  The guard is
    intentionally independent from those entrypoints and therefore suitable for a model-level
    SQLAlchemy event.  A first transient Term with no persisted anchor is compatible because no
    previous current fact exists yet; once any Term is persisted every subsequent writer must
    lock a deterministic anchor.
    """
    from app.models import AaTerm

    tid = normalize_tenant_id(getattr(target, "tenant_id", None))
    locked = lock_term_authority(db, tid)
    if not locked:
        if target in db.new:
            return
        raise AppException(
            "TENANT_CONTEXT_REQUIRED",
            "当前学期写入未命中可证明的租户或学期协调行，拒绝继续",
            details={"tenantId": str(tid)},
            http_status=409,
        )

    target_id = int(getattr(target, "id", 0) or 0)
    active_term_id = active_governance_term_id(db, tid)
    if active_term_id is not None and target_id != active_term_id:
        raise AppException(
            "TERM_CONTEXT_CONFLICT",
            "全校已激活另一学期，禁止教务旁路切换当前学期；请通过学年学期治理完成统一切换",
            details={
                "tenantId": str(tid),
                "activeTermId": str(active_term_id),
                "requestedTermId": str(target_id or "NEW"),
            },
            http_status=409,
        )

    conds = [
        AaTerm.tenant_id == tid,
        AaTerm.is_current.is_(True),
        AaTerm.is_deleted.is_(False),
    ]
    if target_id:
        conds.append(AaTerm.id != target_id)
    db.execute(
        update(AaTerm).where(*conds).values(is_current=False),
        execution_options={"synchronize_session": False},
    )
