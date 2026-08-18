"""INT transactional BINDING writer for ordinary Program imports.

Definition creation and binding activation are intentionally separate.  This
module only handles the second phase after an existing Program definition has
been proven reusable and the target Program is already PUBLISHED/ENABLED.

All domain reads, relationship locks, mutation-plan execution, authoritative
rereads and reconciliation stay inside one transaction.  Shared File Exchange
job/lease ownership remains outside this local owner until the public dispatcher
is activated separately.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import OperationalError

from app.core.affairs_security import build_affairs_context
from app.core.exceptions import AppException
from app.services.db_service import _tid, session

from . import academic_affairs_program_core_service as _program_core
from .academic_affairs_school_setup_program_binding_write_plan import (
    build_program_binding_write_plan,
)
from .academic_affairs_school_setup_program_definition_confirm_service import (
    _allowed_major_ids,
    _class_snapshots,
    _course_snapshots,
    _db_error_code,
    _definition_rows,
    _is_mysql_lock_conflict,
    _major_snapshots,
    _prelock_existing_program_series,
    _program_snapshots,
)
from .academic_affairs_school_setup_program_definition_execution_gate import (
    assert_program_definition_execution_ready,
)
from .academic_affairs_school_setup_program_post_confirm_pipeline import (
    reconcile_program_confirm_reread,
)
from .academic_affairs_school_setup_program_preflight_pipeline import (
    run_program_import_preflight,
)
from .academic_affairs_school_setup_program_snapshot_request_plan import (
    binding_scope_key,
)


def _binding_scope_specs(rows: Iterable[Mapping[str, object]]) -> dict[str, dict]:
    specs: dict[str, dict] = {}
    for raw in rows:
        if str(raw.get("logicalGroup") or "").strip().upper() != "BINDING":
            continue
        payload = dict(raw.get("payload") or {})
        scope_key = binding_scope_key(payload)
        specs.setdefault(
            scope_key,
            {
                "scopeKey": scope_key,
                "majorId": int(payload.get("majorId") or 0),
                "gradeYear": str(payload.get("gradeYear") or "").strip(),
                "classId": (
                    int(payload.get("classId"))
                    if payload.get("classId") not in (None, "", 0, "0")
                    else None
                ),
            },
        )
    return specs


def _scope_predicate(model, spec: Mapping[str, object]):
    class_id = spec.get("classId")
    class_clause = model.class_id.is_(None) if class_id is None else model.class_id == int(class_id)
    return and_(
        model.major_id == int(spec["majorId"]),
        model.grade_year == str(spec["gradeYear"]),
        class_clause,
    )


def _scope_key_from_binding(row) -> str:
    if row.class_id is None:
        return f"MAJOR:{int(row.major_id)}:GRADE:{str(row.grade_year)}:MAJOR_GRADE"
    return (
        f"MAJOR:{int(row.major_id)}:GRADE:{str(row.grade_year)}:"
        f"CLASS:{int(row.class_id)}"
    )


def _binding_snapshots(
    db,
    *,
    specs: Mapping[str, Mapping[str, object]],
    requested_scope_keys: Iterable[object],
    statuses: Iterable[str] | None,
    program_ids: Iterable[object] | None = None,
    lock_rows: bool,
) -> tuple[list[dict], dict[str, list[object]]]:
    from app.models import AaProgramBinding

    requested = tuple(sorted({str(value or "").strip() for value in requested_scope_keys if str(value or "").strip()}))
    if not requested:
        return [], {}
    unknown = [key for key in requested if key not in specs]
    if unknown:
        raise RuntimeError(f"PROGRAM_BINDING_SCOPE_SPEC_MISSING:{','.join(unknown)}")

    clauses = [_scope_predicate(AaProgramBinding, specs[key]) for key in requested]
    stmt = select(AaProgramBinding).where(
        AaProgramBinding.tenant_id == _tid(),
        AaProgramBinding.is_deleted.is_(False),
        or_(*clauses),
    )
    normalized_statuses = tuple(sorted({str(value or "").strip().upper() for value in (statuses or ()) if str(value or "").strip()}))
    if normalized_statuses:
        stmt = stmt.where(AaProgramBinding.status.in_(normalized_statuses))
    wanted_program_ids = tuple(sorted({int(value) for value in (program_ids or ()) if str(value or "").strip()}))
    if wanted_program_ids:
        stmt = stmt.where(AaProgramBinding.program_id.in_(wanted_program_ids))
    stmt = stmt.order_by(
        AaProgramBinding.major_id,
        AaProgramBinding.grade_year,
        AaProgramBinding.class_id,
        AaProgramBinding.id,
    )
    if lock_rows:
        stmt = stmt.with_for_update()
    rows = db.scalars(stmt).all()

    by_scope: dict[str, list[object]] = defaultdict(list)
    snapshots: list[dict] = []
    for row in rows:
        scope_key = _scope_key_from_binding(row)
        if scope_key not in requested:
            raise RuntimeError(
                f"PROGRAM_BINDING_SCOPE_OVERFETCH:{scope_key}:requested={list(requested)}"
            )
        by_scope[scope_key].append(row)
        snapshots.append(
            {
                "scopeKey": scope_key,
                "programId": str(row.program_id),
                "majorId": int(row.major_id) if row.major_id is not None else None,
                "gradeYear": str(row.grade_year or ""),
                "classId": int(row.class_id) if row.class_id is not None else None,
                "status": str(row.status or "").strip().upper(),
            }
        )
    return snapshots, dict(by_scope)


def _program_statuses_for_update(db, ids: Iterable[object]) -> tuple[dict[str, str], dict[str, object]]:
    from app.models import AaProgram

    wanted = tuple(sorted({int(value) for value in ids if str(value or "").strip()}))
    if not wanted:
        return {}, {}
    rows = db.scalars(
        select(AaProgram).where(
            AaProgram.tenant_id == _tid(),
            AaProgram.id.in_(wanted),
            AaProgram.is_deleted.is_(False),
        ).order_by(AaProgram.id).with_for_update()
    ).all()
    by_id = {str(row.id): row for row in rows}
    return (
        {program_id: str(row.status or "").strip().upper() for program_id, row in by_id.items()},
        by_id,
    )


def _target_and_supersede_ids(preflight: Mapping[str, object]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    targets: set[str] = set()
    all_ids: set[str] = set()
    for raw in (preflight.get("binding") or {}).get("intents") or ():
        target = str(raw.get("programId") or "").strip()
        if target:
            targets.add(target)
            all_ids.add(target)
        supersede = str(raw.get("supersedeProgramId") or "").strip()
        if supersede:
            all_ids.add(supersede)
    return tuple(sorted(targets, key=int)), tuple(sorted(all_ids, key=int))


def _apply_binding_plan(
    db,
    plan: Mapping[str, object],
    *,
    locked_active_rows: Mapping[str, list[object]],
    locked_program_rows: Mapping[str, object],
) -> int:
    from app.models import AaProgramBinding

    mutation_count = 0
    for item in plan.get("plans") or ():
        action = str(item.get("action") or "").strip().upper()
        if action == "REUSE":
            if int(item.get("writeCount") or 0) != 0 or item.get("mutations"):
                raise RuntimeError("Program binding REUSE plan must remain zero-write")
            continue
        if action != "CREATE":
            raise RuntimeError(f"unsupported Program binding action: {action}")

        scope_key = str(item.get("scopeKey") or "").strip()
        for mutation in item.get("mutations") or ():
            kind = str(mutation.get("type") or "").strip().upper()
            if kind == "SUPERSEDE_ACTIVE_BINDING":
                expected_program_id = str(mutation.get("expectedProgramId") or "").strip()
                matches = [
                    row
                    for row in locked_active_rows.get(scope_key, ())
                    if str(row.program_id) == expected_program_id
                    and str(row.status or "").strip().upper() == "ACTIVE"
                ]
                if len(matches) != 1:
                    raise RuntimeError(
                        "PROGRAM_BINDING_LOCKED_SUPERSEDE_MISMATCH:"
                        f"scope={scope_key}:expectedProgramId={expected_program_id}:matches={len(matches)}"
                    )
                matches[0].status = "SUPERSEDED"
                mutation_count += 1
            elif kind == "INSERT_ACTIVE_BINDING":
                db.add(
                    AaProgramBinding(
                        tenant_id=_tid(),
                        program_id=int(mutation["programId"]),
                        major_id=int(mutation["majorId"]),
                        grade_year=str(mutation.get("gradeYear") or "").strip(),
                        class_id=(
                            int(mutation["classId"])
                            if mutation.get("classId") not in (None, "", 0, "0")
                            else None
                        ),
                        bound_at=datetime.utcnow(),
                        status="ACTIVE",
                    )
                )
                mutation_count += 1
            elif kind == "SET_TARGET_PROGRAM_STATUS":
                program_id = str(mutation.get("programId") or "").strip()
                program = locked_program_rows.get(program_id)
                if program is None:
                    raise RuntimeError(
                        f"PROGRAM_BINDING_TARGET_PROGRAM_LOCK_MISSING:{program_id}"
                    )
                program.status = str(mutation.get("status") or "").strip().upper()
                mutation_count += 1
            elif kind == "APPEND_PROGRAM_AUDIT":
                program_id = str(mutation.get("programId") or "").strip()
                if program_id not in locked_program_rows:
                    raise RuntimeError(
                        f"PROGRAM_BINDING_AUDIT_PROGRAM_LOCK_MISSING:{program_id}"
                    )
                _program_core._audit(
                    db,
                    int(program_id),
                    str(mutation.get("action") or "BIND").strip().upper(),
                    f"scope={str(mutation.get('scopeKey') or '').strip()}",
                )
                mutation_count += 1
            else:
                raise RuntimeError(f"unsupported Program binding mutation: {kind}")

        expected = int(item.get("writeCount") or 0)
        actual = len(item.get("mutations") or ())
        if actual != expected:
            raise RuntimeError(
                f"Program binding plan count mismatch: expected={expected}, actual={actual}"
            )

    expected_total = sum(int(item.get("writeCount") or 0) for item in plan.get("plans") or ())
    if mutation_count != expected_total:
        raise RuntimeError(
            f"Program binding mutation count mismatch: expected={expected_total}, actual={mutation_count}"
        )
    return mutation_count


def confirm_program_binding_import(
    normalized_rows: Iterable[Mapping[str, object]],
    *,
    user: dict,
) -> dict:
    """Atomically confirm ordinary Program BINDING against current authority facts."""
    rows = [dict(row) for row in normalized_rows]
    if not rows:
        raise AppException("VALIDATION_ERROR", "培养方案绑定导入不能为空")
    assert_program_definition_execution_ready()
    scope_specs = _binding_scope_specs(rows)
    if not scope_specs:
        raise AppException("VALIDATION_ERROR", "培养方案绑定确认至少需要一条适用范围")

    try:
        with session() as db:
            # Program is the common first lock across DEFINITION, BINDING and
            # interactive bind_grade.  The frozen pipeline then acquires
            # Major/Class, Course/definition and ACTIVE scope locks in one session.
            _prelock_existing_program_series(db, rows)
            security = build_affairs_context(user, db)
            allowed_major_ids = _allowed_major_ids(db, security)
            locked_active_rows: dict[str, list[object]] = {}
            locked_program_rows: dict[str, object] = {}

            def load_allowed_major_ids():
                return None if allowed_major_ids is None else set(allowed_major_ids)

            def load_major_snapshots(keys):
                return _major_snapshots(db, keys)

            def load_class_snapshots(keys):
                return _class_snapshots(db, keys)

            def load_course_snapshots(keys):
                return _course_snapshots(db, keys)

            def load_program_snapshots(keys):
                return _program_snapshots(db, keys)

            def load_existing_definition_rows(keys):
                return _definition_rows(db, keys, lock_rows=True)

            def load_program_status_by_id(keys):
                statuses, programs = _program_statuses_for_update(db, keys)
                locked_program_rows.update(programs)
                return statuses

            def load_active_binding_snapshots(keys):
                snapshots, by_scope = _binding_snapshots(
                    db,
                    specs=scope_specs,
                    requested_scope_keys=keys,
                    statuses=("ACTIVE",),
                    lock_rows=True,
                )
                locked_active_rows.clear()
                locked_active_rows.update(by_scope)
                return snapshots

            preflight = run_program_import_preflight(
                rows,
                phase="BINDING",
                load_allowed_major_ids=load_allowed_major_ids,
                load_major_snapshots=load_major_snapshots,
                load_class_snapshots=load_class_snapshots,
                load_course_snapshots=load_course_snapshots,
                load_program_snapshots=load_program_snapshots,
                load_existing_definition_rows=load_existing_definition_rows,
                load_program_status_by_id=load_program_status_by_id,
                load_active_binding_snapshots=load_active_binding_snapshots,
            )
            if not bool(preflight.get("programPreflightSafe")) or str(preflight.get("stage") or "").strip().upper() != "READY":
                raise AppException(
                    "DATA_CONFLICT",
                    "培养方案绑定确认前的锁内预检未通过",
                    details={
                        "stage": str(preflight.get("stage") or ""),
                        "errors": list(preflight.get("errors") or ()),
                    },
                    http_status=409,
                )

            write_plan = build_program_binding_write_plan(preflight)
            domain_mutation_count = _apply_binding_plan(
                db,
                write_plan,
                locked_active_rows=locked_active_rows,
                locked_program_rows=locked_program_rows,
            )
            db.flush()

            target_ids, all_binding_program_ids = _target_and_supersede_ids(preflight)
            authoritative_bindings, _rows_by_scope = _binding_snapshots(
                db,
                specs=scope_specs,
                requested_scope_keys=scope_specs.keys(),
                statuses=("ACTIVE", "SUPERSEDED"),
                program_ids=all_binding_program_ids,
                lock_rows=True,
            )
            authoritative_statuses, _programs = _program_statuses_for_update(db, target_ids)
            reconciliation = reconcile_program_confirm_reread(
                preflight,
                authoritative_binding_snapshots=authoritative_bindings,
                authoritative_program_status_by_id=authoritative_statuses,
            )
            if not bool(reconciliation.get("reconciliationSafe")):
                raise AppException(
                    "DATA_CONFLICT",
                    "培养方案绑定确认后的权威回读对账失败，事务已回滚",
                    details={"errors": list(reconciliation.get("errors") or ())},
                    http_status=409,
                )

            db.commit()
            return {
                "phase": "BINDING",
                "domainMutationWriteCount": domain_mutation_count,
                "preflight": preflight,
                "reconciliation": reconciliation,
            }
    except OperationalError as exc:
        if _is_mysql_lock_conflict(exc):
            raise AppException(
                "DATA_CONFLICT",
                "培养方案绑定确认期间发生并发锁冲突，请重新预检后重试",
                details={"dbErrorCode": _db_error_code(exc)},
                http_status=409,
            ) from exc
        raise
