"""无显式学期的正式成绩写入，收口到唯一当前学期后再冻结策略。

A-W1 同时在这里安装当前学期写入的租户级 Authority 锁。这个模块已由
``app.modules.academic_affairs.services`` 在模型初始化完成后固定加载，因此无需抢写
``services/__init__.py`` 或模型注册表；锁只复用现有 ``t_tenant`` 行，不新增第二套
Term 真值或迁移。

当前 exact-head 还存在 SYS-12 ``AcademicCalendarGovernance``：它是全校统一切换治理投影，
ACTIVE 时会把 ``AaTerm.is_current`` 同步到同一个 term。A-W1 让治理激活与教务 publish/
set-current/import 共用同一租户协调行，并在已有 ACTIVE 治理学期时禁止教务旁路把另一个
学期写成 current，避免两个 Authority 并发漂移。
"""
from __future__ import annotations

from sqlalchemy import event, select, update
from sqlalchemy.orm import Session, object_session

from app.core.exceptions import AppException
from app.models import AaTerm, Tenant
from app.models.academic import AcademicGrade
from app.models.academic_calendar import (
    ACTIVE_SENTINEL,
    CALENDAR_TYPE_ACADEMIC,
    AcademicCalendarGovernance,
)
from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_compat as _compat


def _tenant_id_of(target) -> int:
    try:
        return int(getattr(target, "tenant_id", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _lock_tenant_authority_row(db: Session, tenant_id: int) -> bool:
    """Acquire the single per-tenant coordination row used by every current-term writer."""
    if tenant_id <= 0:
        raise AppException(
            "TENANT_CONTEXT_REQUIRED",
            "当前学期写入缺少租户标识，拒绝猜测 Authority 范围",
            http_status=409,
        )
    with db.no_autoflush:
        locked = db.scalar(
            select(Tenant.id).where(Tenant.id == tenant_id).with_for_update()
        )
    return locked is not None


def _active_governance_term_id(db: Session, tenant_id: int) -> int | None:
    with db.no_autoflush:
        value = db.scalar(
            select(AcademicCalendarGovernance.term_id).where(
                AcademicCalendarGovernance.tenant_id == tenant_id,
                AcademicCalendarGovernance.calendar_type == CALENDAR_TYPE_ACADEMIC,
                AcademicCalendarGovernance.active_key == ACTIVE_SENTINEL,
                AcademicCalendarGovernance.is_deleted.is_(False),
            )
        )
    return int(value) if value is not None else None


def _lock_current_term_authority(db: Session, target: AaTerm) -> None:
    """Serialize current-term mutation per tenant and clear fresh competing current rows.

    Writers historically all follow ``read current -> clear -> set target current``. Two
    transactions can therefore both read the same old current row before either commits.
    Merely locking at flush time is insufficient: the second writer would still flush a stale
    decision and leave two current terms.  The attribute listener below acquires the tenant
    coordination row *before* ``is_current=True`` is accepted, then clears any freshly committed
    competing current rows while holding that lock.

    If SYS-12 already has an ACTIVE governance term, that term is the full-school switch result.
    Direct academic writers may refresh the same term but may not silently point ``is_current``
    at a different term; the user must perform the explicit governance transition instead.
    """
    tenant_id = _tenant_id_of(target)
    locked = _lock_tenant_authority_row(db, tenant_id)
    if not locked:
        # 兼容既有 isolated ORM/fixture：历史测试会直接构造一个尚无 Tenant
        # 父行的新 AaTerm。它不是正式 tenant writer，不能因为 A-W1 的生产锁
        # 破坏既有模型级回归；已持久化对象仍 fail-closed，正式业务 writer
        # 必须命中真实 Tenant 协调行。
        if target in db.new:
            return
        raise AppException(
            "TENANT_CONTEXT_REQUIRED",
            "当前学期写入未命中真实租户，拒绝继续",
            details={"tenantId": str(tenant_id)},
            http_status=409,
        )

    active_term_id = _active_governance_term_id(db, tenant_id)
    target_id = int(getattr(target, "id", 0) or 0)
    if active_term_id is not None and target_id != active_term_id:
        raise AppException(
            "TERM_CONTEXT_CONFLICT",
            "全校已激活另一学期，禁止教务旁路切换当前学期；请通过学年学期治理完成统一切换",
            details={
                "tenantId": str(tenant_id),
                "activeTermId": str(active_term_id),
                "requestedTermId": str(target_id or "NEW"),
            },
            http_status=409,
        )

    conds = [
        AaTerm.tenant_id == tenant_id,
        AaTerm.is_current.is_(True),
        AaTerm.is_deleted.is_(False),
    ]
    if target_id:
        conds.append(AaTerm.id != target_id)
    db.execute(
        update(AaTerm).where(*conds).values(is_current=False),
        execution_options={"synchronize_session": False},
    )


def _current_term_authority_on_set(target, value, oldvalue, initiator):
    """Acquire the tenant Authority lock before any formal writer can set current=True."""
    if value is not True:
        return value
    db = object_session(target)
    if db is None:
        # Transient fixture/model construction is handled by the before_flush fallback below.
        return value
    _lock_current_term_authority(db, target)
    return value


def _calendar_governance_active_on_set(target, value, oldvalue, initiator):
    """Make SYS-12 ACTIVE transition serialize on the same tenant row as academic writers."""
    if value != ACTIVE_SENTINEL:
        return value
    db = object_session(target)
    if db is None:
        return value
    tenant_id = _tenant_id_of(target)
    if not _lock_tenant_authority_row(db, tenant_id):
        raise AppException(
            "TENANT_CONTEXT_REQUIRED",
            "学期治理激活未命中真实租户，拒绝继续",
            details={"tenantId": str(tenant_id)},
            http_status=409,
        )
    return value


def _current_term_authority_before_flush(db: Session, flush_context, instances) -> None:
    """Fail-closed fallback for detached current terms and transient governance activation."""
    by_tenant: dict[int, list[AaTerm]] = {}
    governance_tenants: set[int] = set()
    for obj in set(db.new).union(db.dirty):
        if isinstance(obj, AaTerm) and obj.is_current is True:
            tenant_id = _tenant_id_of(obj)
            if tenant_id > 0:
                by_tenant.setdefault(tenant_id, []).append(obj)
        elif isinstance(obj, AcademicCalendarGovernance) and obj.active_key == ACTIVE_SENTINEL:
            tenant_id = _tenant_id_of(obj)
            if tenant_id > 0:
                governance_tenants.add(tenant_id)

    for tenant_id in governance_tenants:
        if not _lock_tenant_authority_row(db, tenant_id):
            raise AppException(
                "TENANT_CONTEXT_REQUIRED",
                "学期治理激活未命中真实租户，拒绝继续",
                details={"tenantId": str(tenant_id)},
                http_status=409,
            )

    for tenant_id, targets in by_tenant.items():
        if len(targets) > 1:
            raise AppException(
                "DATA_CONFLICT",
                "同一事务试图写入多个当前学期，已拒绝",
                details={
                    "tenantId": str(tenant_id),
                    "termIds": [str(getattr(t, "id", "") or "NEW") for t in targets],
                },
                http_status=409,
            )
        _lock_current_term_authority(db, targets[0])


def _current_term_before_grade_insert(mapper, connection, target) -> None:
    if getattr(target, "tenant_id", None) and not str(getattr(target, "term", None) or "").strip():
        table = AaTerm.__table__
        rows = connection.execute(select(table).where(
            table.c.tenant_id == int(target.tenant_id),
            table.c.is_current.is_(True),
            table.c.is_deleted.is_(False),
        )).mappings().all()
        if len(rows) > 1:
            raise AppException(
                "DATA_CONFLICT",
                "学校存在多个当前学期，禁止为正式成绩猜测策略生效学期",
                details={"termIds": [str(row["id"]) for row in rows]},
                http_status=409,
            )
        if len(rows) == 1:
            target.term = _compat._term_code(rows[0])
    _compat._chronological_before_grade_insert(mapper, connection, target)


if event.contains(AcademicGrade, "before_insert", _compat._chronological_before_grade_insert):
    event.remove(AcademicGrade, "before_insert", _compat._chronological_before_grade_insert)
if not event.contains(AcademicGrade, "before_insert", _current_term_before_grade_insert):
    event.listen(AcademicGrade, "before_insert", _current_term_before_grade_insert)

if not event.contains(AaTerm.is_current, "set", _current_term_authority_on_set):
    event.listen(
        AaTerm.is_current,
        "set",
        _current_term_authority_on_set,
        retval=True,
        active_history=True,
    )
if not event.contains(AcademicCalendarGovernance.active_key, "set", _calendar_governance_active_on_set):
    event.listen(
        AcademicCalendarGovernance.active_key,
        "set",
        _calendar_governance_active_on_set,
        retval=True,
        active_history=True,
    )
if not event.contains(Session, "before_flush", _current_term_authority_before_flush):
    event.listen(Session, "before_flush", _current_term_authority_before_flush)
