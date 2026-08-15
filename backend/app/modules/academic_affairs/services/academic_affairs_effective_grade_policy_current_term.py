"""无显式学期的正式成绩写入，收口到唯一当前学期后再冻结策略。

A-W1 同时在这里安装 ``AaTerm.is_current`` 的正式写入安全层。租户协调锁已经抽到
``app.core.academic_term_authority_lock``；SYS-12 ACTIVE 的监听由治理模型自身安装，
因此系统 API、定时激活和独立 SYS-12 测试不再依赖 academic services 包初始化顺序。
"""
from __future__ import annotations

from sqlalchemy import event, select, update
from sqlalchemy.orm import Session, object_session

from app.core.academic_term_authority_lock import (
    active_governance_term_id,
    lock_term_authority,
)
from app.core.exceptions import AppException
from app.models import AaTerm
from app.models.academic import AcademicGrade
from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_compat as _compat


def _tenant_id_of(target) -> int:
    try:
        return int(getattr(target, "tenant_id", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _lock_current_term_authority(db: Session, target: AaTerm) -> None:
    """Serialize current-term mutation and reject a direct switch against SYS-12 ACTIVE."""
    tenant_id = _tenant_id_of(target)
    locked = lock_term_authority(db, tenant_id)
    if not locked:
        # The first transient AaTerm may have no persisted lock anchor yet; there is no prior
        # current row to compete with. Once any Term exists, every writer must hit one anchor.
        if target in db.new:
            return
        raise AppException(
            "TENANT_CONTEXT_REQUIRED",
            "当前学期写入未命中可证明的租户或学期协调行，拒绝继续",
            details={"tenantId": str(tenant_id)},
            http_status=409,
        )

    active_term_id = active_governance_term_id(db, tenant_id)
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
    """Acquire the tenant Authority lock before any formal AaTerm writer accepts current=True."""
    if value is not True:
        return value
    db = object_session(target)
    if db is None:
        # Transient construction is handled by before_flush below.
        return value
    _lock_current_term_authority(db, target)
    return value


def _current_term_authority_before_flush(db: Session, flush_context, instances) -> None:
    """Fail closed when one transaction tries to manufacture multiple current terms."""
    by_tenant: dict[int, list[AaTerm]] = {}
    for obj in set(db.new).union(db.dirty):
        if not isinstance(obj, AaTerm) or obj.is_current is not True:
            continue
        tenant_id = _tenant_id_of(obj)
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
