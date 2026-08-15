"""无显式学期的正式成绩写入，收口到唯一当前学期后再冻结策略。

A-W1 同时在这里安装当前学期写入的租户级 Authority 锁。这个模块已由
``app.modules.academic_affairs.services`` 在模型初始化完成后固定加载，因此无需抢写
``services/__init__.py`` 或模型注册表；锁只复用现有 ``t_tenant`` 行，不新增第二套
Term 真值或迁移。
"""
from __future__ import annotations

from sqlalchemy import event, select, update
from sqlalchemy.orm import Session, object_session

from app.core.exceptions import AppException
from app.models.academic import AcademicGrade
from app.models import AaTerm, Tenant
from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_compat as _compat


def _lock_current_term_authority(db: Session, target: AaTerm) -> None:
    """Serialize current-term mutation per tenant and clear fresh competing current rows.

    Writers historically all follow ``read current -> clear -> set target current``. Two
    transactions can therefore both read the same old current row before either commits.
    Merely locking at flush time is insufficient: the second writer would still flush a stale
    decision and leave two current terms.  The attribute listener below acquires the tenant
    coordination row *before* ``is_current=True`` is accepted, then clears any freshly committed
    competing current rows while holding that lock.  A second writer waits, observes the first
    commit through this SQL update, clears it, and becomes the single winner.
    """
    try:
        tenant_id = int(getattr(target, "tenant_id", 0) or 0)
    except (TypeError, ValueError):
        tenant_id = 0
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
        if locked is None:
            raise AppException(
                "TENANT_CONTEXT_REQUIRED",
                "当前学期写入未命中真实租户，拒绝继续",
                details={"tenantId": str(tenant_id)},
                http_status=409,
            )

        conds = [
            AaTerm.tenant_id == tenant_id,
            AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False),
        ]
        if getattr(target, "id", None) is not None:
            conds.append(AaTerm.id != int(target.id))
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


def _current_term_authority_before_flush(db: Session, flush_context, instances) -> None:
    """Fail-closed fallback for callers that constructed ``AaTerm(is_current=True)`` detached.

    Canonical writers hit the earlier attribute listener.  This fallback protects scripts/tests
    that attach an already-current transient row.  More than one current target for the same
    tenant in one transaction is ambiguous and is rejected rather than selecting a winner.
    """
    by_tenant: dict[int, list[AaTerm]] = {}
    for obj in set(db.new).union(db.dirty):
        if not isinstance(obj, AaTerm) or obj.is_current is not True:
            continue
        try:
            tenant_id = int(obj.tenant_id or 0)
        except (TypeError, ValueError):
            tenant_id = 0
        if tenant_id > 0:
            by_tenant.setdefault(tenant_id, []).append(obj)

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
if not event.contains(Session, "before_flush", _current_term_authority_before_flush):
    event.listen(Session, "before_flush", _current_term_authority_before_flush)
