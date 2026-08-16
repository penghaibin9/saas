"""INT Program import preflight pipeline with injected bounded snapshot loaders.

This owner intentionally stops before shared File Exchange dispatch and before any
Program writer.  It composes the already-frozen source/reference/definition/
binding classifiers while preserving the required lookup order:

source-only -> affairs scope -> Major -> SchoolClass(binding only) -> exact Course
versions -> Program series/version -> REUSE child definitions -> ACTIVE bindings.

The module opens no session, performs no writes, and accepts loaders as injected
callables so targeted tests can prove malformed source rows cause zero DB work.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from .academic_affairs_school_setup_import_contract import (
    BINDING_SCOPE_CLASS,
    PROGRAM_GROUP_BINDING,
    RECONCILIATION_REUSE,
)
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

SnapshotLoader = Callable[[], Iterable[Mapping[str, object]]]
ScopeLoader = Callable[[], set[int] | None]
StatusLoader = Callable[[], Mapping[str, object]]


def _phase(value: object) -> str:
    phase = str(value or "").strip().upper()
    if phase not in {PHASE_DEFINITION, PHASE_BINDING}:
        raise ValueError("phase must be DEFINITION or BINDING")
    return phase


def _requires_class_lookup(rows: Iterable[Mapping[str, object]]) -> bool:
    for row in rows:
        if str(row.get("logicalGroup") or "").strip().upper() != PROGRAM_GROUP_BINDING:
            continue
        payload = dict(row.get("payload") or {})
        if str(payload.get("bindingScope") or "").strip().upper() == BINDING_SCOPE_CLASS:
            return True
    return False


def _result(
    *,
    stage: str,
    safe: bool,
    source: Mapping[str, object],
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
    load_major_snapshots: SnapshotLoader,
    load_class_snapshots: SnapshotLoader,
    load_course_snapshots: SnapshotLoader,
    load_program_snapshots: SnapshotLoader,
    load_existing_definition_rows: SnapshotLoader,
    load_program_status_by_id: StatusLoader,
    load_active_binding_snapshots: SnapshotLoader,
) -> dict:
    """Run all local Program preflight stages without owning DB/session lifecycle.

    Loader invocation is intentionally lazy:
    - source blockers call no loader at all;
    - SchoolClass is loaded only when a CLASS binding exists;
    - existing child definitions are loaded only for a REUSE candidate;
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

    allowed_major_ids = load_allowed_major_ids()
    major_snapshots = [dict(row) for row in load_major_snapshots()]
    class_snapshots = (
        [dict(row) for row in load_class_snapshots()]
        if _requires_class_lookup(rows)
        else []
    )
    course_snapshots = [dict(row) for row in load_course_snapshots()]
    program_snapshots = [dict(row) for row in load_program_snapshots()]

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
            reference=reference,
            actions=reference_actions,
            errors=reference.get("errors") or (),
        )

    requires_definition_reconciliation = any(
        str(action.get("action") or "").strip().upper() == RECONCILIATION_REUSE
        and bool(action.get("requiresDefinitionReconciliation"))
        for action in reference_actions
    )
    existing_definition_rows = (
        [dict(row) for row in load_existing_definition_rows()]
        if requires_definition_reconciliation
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
        # BINDING confirmation is second-phase only. These loaders are deliberately
        # postponed until all earlier Program-definition facts are green.
        program_status_by_id = dict(load_program_status_by_id())
        active_binding_snapshots = [dict(row) for row in load_active_binding_snapshots()]
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
        reference=reference,
        definition=definition,
        binding=binding,
        actions=final_actions,
        errors=(),
    )
