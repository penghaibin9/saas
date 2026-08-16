"""INT Program import preflight pipeline with bounded injected snapshot loaders.

This owner stops before shared File Exchange dispatch and before any Program
writer. It composes the frozen source/reference/definition/binding classifiers
while enforcing the read order and exact lookup keys a later DB bridge must use:

source-only -> affairs scope -> Major -> SchoolClass(binding only) -> exact Course
versions -> Program series/version -> REUSE child definitions -> ACTIVE bindings.

The module opens no session, performs no writes, and accepts injected loaders so
targeted tests can prove malformed source rows cause zero DB work and valid rows
never authorize an unbounded lookup.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from .academic_affairs_school_setup_import_contract import RECONCILIATION_REUSE
from .academic_affairs_school_setup_program_binding_policy import (
    PHASE_BINDING,
    PHASE_DEFINITION,
    classify_program_binding_phase,
)
from .academic_affairs_school_setup_program_definition_reconciliation import (
    reconcile_program_definitions,
)
from .academic_affairs_school_setup_program_import_preflight import (
    program_import_source_preflight,
)
from .academic_affairs_school_setup_program_reference_preflight import (
    program_import_reference_preflight,
)
from .academic_affairs_school_setup_program_snapshot_request_plan import (
    plan_program_snapshot_requests,
)

ScopeLoader = Callable[[], set[int] | None]
IdSnapshotLoader = Callable[[tuple[int, ...]], Iterable[Mapping[str, object]]]
KeySnapshotLoader = Callable[[tuple[str, ...]], Iterable[Mapping[str, object]]]
ProgramStatusLoader = Callable[[tuple[str, ...]], Mapping[str, object]]


def _phase(value: object) -> str:
    phase = str(value or "").strip().upper()
    if phase not in {PHASE_DEFINITION, PHASE_BINDING}:
        raise ValueError("phase must be DEFINITION or BINDING")
    return phase


def _result(
    *,
    stage: str,
    safe: bool,
    source: Mapping[str, object],
    request_keys: Mapping[str, object] | None = None,
    reference: Mapping[str, object] | None = None,
    definition: Mapping[str, object] | None = None,
    binding: Mapping[str, object] | None = None,
    actions: Iterable[Mapping[str, object]] = (),
    errors: Iterable[Mapping[str, object]] = (),
) -> dict:
    errors_list = [dict(item) for item in errors]
    return {
        "stage": stage,
        "programPreflightSafe": bool(safe),
        "source": dict(source),
        "requestKeys": dict(request_keys or {}),
        "reference": dict(reference or {}),
        "definition": dict(definition or {}),
        "binding": dict(binding or {}),
        "actions": [dict(item) for item in actions],
        "errors": errors_list,
        "blockerCount": len(errors_list),
    }


def run_program_import_preflight(
    normalized_rows: Iterable[Mapping[str, object]],
    *,
    phase: object,
    load_allowed_major_ids: ScopeLoader,
    load_major_snapshots: IdSnapshotLoader,
    load_class_snapshots: IdSnapshotLoader,
    load_course_snapshots: KeySnapshotLoader,
    load_program_snapshots: KeySnapshotLoader,
    load_existing_definition_rows: KeySnapshotLoader,
    load_program_status_by_id: ProgramStatusLoader,
    load_active_binding_snapshots: KeySnapshotLoader,
) -> dict:
    """Run all local Program preflight stages without owning DB/session lifecycle.

    Every snapshot loader except the affairs-scope resolver receives the exact
    bounded keys it is allowed to query. Loader invocation remains lazy:
    - source blockers call no loader at all;
    - SchoolClass is loaded only for exact CLASS ids present in source;
    - child definitions are loaded only for exact REUSE program ids;
    - Program status / ACTIVE bindings are loaded only during BINDING phase after
      reference + definition reconciliation are green.
    """
    resolved_phase = _phase(phase)
    rows = [dict(row) for row in normalized_rows]

    source = program_import_source_preflight(rows)
    if not bool(source.get("sourcePreflightSafe")):
        return _result(
            stage="SOURCE",
            safe=False,
            source=source,
            errors=source.get("errors") or (),
        )

    request_keys = plan_program_snapshot_requests(rows)
    allowed_major_ids = load_allowed_major_ids()
    major_snapshots = [
        dict(row) for row in load_major_snapshots(request_keys["majorIds"])
    ]
    class_snapshots = (
        [dict(row) for row in load_class_snapshots(request_keys["classIds"])]
        if request_keys["classIds"]
        else []
    )
    course_snapshots = [
        dict(row) for row in load_course_snapshots(request_keys["courseKeys"])
    ]
    program_snapshots = [
        dict(row) for row in load_program_snapshots(request_keys["seriesKeys"])
    ]

    reference = program_import_reference_preflight(
        rows,
        major_snapshots=major_snapshots,
        class_snapshots=class_snapshots,
        course_snapshots=course_snapshots,
        program_snapshots=program_snapshots,
        allowed_major_ids=allowed_major_ids,
    )
    reference_actions = [dict(item) for item in reference.get("actions") or ()]
    if not bool(reference.get("referencePreflightSafe")):
        return _result(
            stage="REFERENCE",
            safe=False,
            source=source,
            request_keys=request_keys,
            reference=reference,
            actions=reference_actions,
            errors=reference.get("errors") or (),
        )

    reuse_program_ids = tuple(sorted({
        str(action.get("programId") or "").strip()
        for action in reference_actions
        if (
            str(action.get("action") or "").strip().upper() == RECONCILIATION_REUSE
            and bool(action.get("requiresDefinitionReconciliation"))
            and str(action.get("programId") or "").strip()
        )
    }))
    existing_definition_rows = (
        [dict(row) for row in load_existing_definition_rows(reuse_program_ids)]
        if reuse_program_ids
        else []
    )
    definition = reconcile_program_definitions(
        rows,
        reference_actions,
        existing_definition_rows=existing_definition_rows,
        course_snapshots=course_snapshots,
    )
    final_actions = [dict(item) for item in definition.get("actions") or ()]
    if not bool(definition.get("definitionReconciliationSafe")):
        return _result(
            stage="DEFINITION",
            safe=False,
            source=source,
            request_keys=request_keys,
            reference=reference,
            definition=definition,
            actions=final_actions,
            errors=definition.get("errors") or (),
        )

    if resolved_phase == PHASE_DEFINITION:
        binding = classify_program_binding_phase(
            rows,
            final_actions,
            phase=PHASE_DEFINITION,
        )
    else:
        target_program_ids = tuple(sorted({
            str(action.get("programId") or "").strip()
            for action in final_actions
            if str(action.get("programId") or "").strip()
        }))
        program_status_by_id = dict(load_program_status_by_id(target_program_ids))
        active_binding_snapshots = [
            dict(row)
            for row in load_active_binding_snapshots(request_keys["bindingScopeKeys"])
        ]
        binding = classify_program_binding_phase(
            rows,
            final_actions,
            phase=PHASE_BINDING,
            program_status_by_id=program_status_by_id,
            active_binding_snapshots=active_binding_snapshots,
        )

    binding_errors = list(binding.get("errors") or ())
    if binding_errors or (
        resolved_phase == PHASE_BINDING and not bool(binding.get("bindingWriteAllowed"))
    ):
        return _result(
            stage="BINDING",
            safe=False,
            source=source,
            request_keys=request_keys,
            reference=reference,
            definition=definition,
            binding=binding,
            actions=final_actions,
            errors=binding_errors,
        )

    return _result(
        stage="READY",
        safe=True,
        source=source,
        request_keys=request_keys,
        reference=reference,
        definition=definition,
        binding=binding,
        actions=final_actions,
        errors=(),
    )
