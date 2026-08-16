"""A-W2 canonical Program activation resolver.

This module is the single read authority for deciding which formal Program version
applies to one major/grade/class scope. Opening Projection, TeachingTask generation,
graduation and student academic progress must consume the same precedence and status
policy instead of reinterpreting Program states independently.

Current execution:
- only ACTIVE bindings participate;
- class override wins over major+grade fallback;
- PUBLISHED / ENABLED / FROZEN are executable for an already bound cohort;
- multiple valid bindings in one scope fail closed.

Historical replay:
- ACTIVE and SUPERSEDED bindings are evaluated by bound_at <= as_of;
- the latest effective binding wins inside the selected scope;
- DISABLED is replayable because a later lifecycle change must not erase an older
  formally effective Program version from graduation/archive evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from sqlalchemy import select

from app.core.tenant_scoped import tenant_get


CURRENT_EFFECTIVE_PROGRAM_STATUSES = frozenset({"PUBLISHED", "ENABLED", "FROZEN"})
HISTORICAL_REPLAY_PROGRAM_STATUSES = frozenset({
    "PUBLISHED", "ENABLED", "FROZEN", "DISABLED",
})


@dataclass(frozen=True)
class ProgramActivationResolution:
    program: object | None
    binding: object | None
    status: str
    rule: str
    message: str


def _naive_utc(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, time.min)
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _binding_time(binding) -> datetime | None:
    return _naive_utc(getattr(binding, "bound_at", None))


def _program_for_binding(db, binding, *, tenant_id: int, historical: bool):
    from app.models import AaProgram

    if not binding or not getattr(binding, "program_id", None):
        return None
    program = tenant_get(db, AaProgram, int(binding.program_id), tenant_id=int(tenant_id))
    if not program or program.is_deleted or int(program.tenant_id) != int(tenant_id):
        return None
    allowed = HISTORICAL_REPLAY_PROGRAM_STATUSES if historical else CURRENT_EFFECTIVE_PROGRAM_STATUSES
    return program if str(program.status or "").upper() in allowed else None


def _current_choice(db, rows, *, tenant_id: int, current_rule: str,
                    conflict_rule: str, invalid_rule: str, scope_label: str):
    active = [row for row in rows if str(row.status or "").upper() == "ACTIVE"]
    if not active:
        return None
    valid = [(row, _program_for_binding(db, row, tenant_id=tenant_id, historical=False)) for row in active]
    valid = [(row, program) for row, program in valid if program is not None]
    if len(valid) == 1:
        row, program = valid[0]
        return ProgramActivationResolution(program, row, "RESOLVED", current_rule,
                                           f"按{scope_label}当前绑定解析")
    if len(valid) > 1:
        return ProgramActivationResolution(
            None, None, "AMBIGUOUS", conflict_rule,
            f"{scope_label}存在多条当前有效培养方案绑定，请先修复绑定数据",
        )
    return ProgramActivationResolution(
        None, None, "MISSING", invalid_rule,
        f"{scope_label}存在当前绑定，但培养方案状态不允许当前执行",
    )


def _historical_choice(db, rows, *, tenant_id: int, as_of: datetime,
                       history_rule: str, conflict_rule: str, invalid_rule: str,
                       scope_label: str):
    eligible = [
        row for row in rows
        if str(row.status or "").upper() in {"ACTIVE", "SUPERSEDED"}
        and _binding_time(row) is not None
        and _binding_time(row) <= as_of
    ]
    if not eligible:
        return None
    latest_at = max(_binding_time(row) for row in eligible)
    latest = [row for row in eligible if _binding_time(row) == latest_at]
    valid = [(row, _program_for_binding(db, row, tenant_id=tenant_id, historical=True)) for row in latest]
    valid = [(row, program) for row, program in valid if program is not None]
    if len(valid) == 1 and len(latest) == 1:
        row, program = valid[0]
        return ProgramActivationResolution(program, row, "RESOLVED", history_rule,
                                           f"按{scope_label}生效日期内历史绑定解析")
    if len(latest) > 1:
        return ProgramActivationResolution(
            None, None, "AMBIGUOUS", conflict_rule,
            f"{scope_label}同一生效时点存在多条历史培养方案绑定",
        )
    return ProgramActivationResolution(
        None, None, "MISSING", invalid_rule,
        f"{scope_label}历史绑定存在，但对应正式方案版本不可回放",
    )


def resolve_program_for_scope(
    db,
    *,
    tenant_id: int,
    major_id: int | None,
    grade_year: str | None,
    class_id: int | None = None,
    as_of=None,
) -> ProgramActivationResolution:
    """Resolve the one formal Program version for a major/grade/class scope.

    ``as_of=None`` means current execution. A supplied ``as_of`` switches to historical
    replay and never lets a future binding shadow an older effective version.
    """
    from app.models import AaProgramBinding

    if not major_id:
        return ProgramActivationResolution(None, None, "MISSING", "NO_MAJOR",
                                           "未提供专业，无法解析培养方案")

    grade = str(grade_year or "").strip()
    rows = db.scalars(select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == int(tenant_id),
        AaProgramBinding.major_id == int(major_id),
        AaProgramBinding.status.in_(["ACTIVE", "SUPERSEDED"]),
        AaProgramBinding.is_deleted.is_(False),
    ).order_by(AaProgramBinding.id.desc())).all()

    historical_at = _naive_utc(as_of) if as_of is not None else None
    historical = as_of is not None
    if historical and historical_at is None:
        return ProgramActivationResolution(None, None, "MISSING", "AS_OF_INVALID",
                                           "历史培养方案解析需要有效 as_of 时点")

    def choose(scope_rows, *, current_rule, history_rule, conflict_rule, invalid_rule, scope_label):
        if historical:
            return _historical_choice(
                db, scope_rows, tenant_id=int(tenant_id), as_of=historical_at,
                history_rule=history_rule, conflict_rule=conflict_rule,
                invalid_rule=invalid_rule, scope_label=scope_label,
            )
        return _current_choice(
            db, scope_rows, tenant_id=int(tenant_id), current_rule=current_rule,
            conflict_rule=conflict_rule, invalid_rule=invalid_rule, scope_label=scope_label,
        )

    deferred_invalid = None
    if class_id:
        class_rows = [
            row for row in rows
            if row.class_id and int(row.class_id) == int(class_id)
        ]
        picked = choose(
            class_rows,
            current_rule="CLASS_BINDING",
            history_rule="CLASS_HISTORICAL_EFFECTIVE",
            conflict_rule="CLASS_BINDING_CONFLICT",
            invalid_rule="CLASS_BINDING_INVALID",
            scope_label="行政班",
        )
        if picked is not None:
            return picked
        if class_rows:
            deferred_invalid = ProgramActivationResolution(
                None, None, "MISSING", "CLASS_BINDING_INVALID",
                "行政班绑定存在，但在当前执行/历史时点尚无可证明的有效版本",
            )

    if grade:
        grade_rows = [
            row for row in rows
            if not row.class_id and str(row.grade_year or "").strip() == grade
        ]
        picked = choose(
            grade_rows,
            current_rule="MAJOR_GRADE_BINDING",
            history_rule="MAJOR_GRADE_HISTORICAL_EFFECTIVE",
            conflict_rule="MAJOR_GRADE_CONFLICT",
            invalid_rule="MAJOR_GRADE_BINDING_INVALID",
            scope_label="专业与入学年级",
        )
        if picked is not None:
            return picked
        if grade_rows and deferred_invalid is None:
            deferred_invalid = ProgramActivationResolution(
                None, None, "MISSING", "MAJOR_GRADE_BINDING_INVALID",
                "专业年级绑定存在，但在当前执行/历史时点尚无可证明的有效版本",
            )

    if deferred_invalid is not None:
        return deferred_invalid
    return ProgramActivationResolution(
        None, None, "MISSING", "NO_EFFECTIVE_BINDING",
        "未找到班级、专业年级或该历史时点内有效的培养方案绑定",
    )
