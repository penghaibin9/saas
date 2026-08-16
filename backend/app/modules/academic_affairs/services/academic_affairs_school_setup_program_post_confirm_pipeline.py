"""INT guarded post-confirm entrypoint for Program school-setup imports.

Future shared writers should call this module after their transactional writes and
bounded authoritative rereads. It refuses overfetched evidence first, then delegates
semantic hash/relationship reconciliation to the frozen local owner.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from .academic_affairs_school_setup_program_binding_policy import (
    PHASE_BINDING,
    PHASE_DEFINITION,
)
from .academic_affairs_school_setup_program_post_confirm_reconciliation import (
    reconcile_program_bindings_after_confirm,
    reconcile_program_definition_after_confirm,
)
from .academic_affairs_school_setup_program_post_confirm_response_guard import (
    guard_binding_reread,
    guard_binding_status_reread,
    guard_definition_child_reread,
    guard_definition_program_reread,
    target_program_ids_from_reread,
)


def _phase(preflight_result: Mapping[str, object]) -> str:
    phase = str((preflight_result.get("binding") or {}).get("phase") or "").strip().upper()
    if phase not in {PHASE_DEFINITION, PHASE_BINDING}:
        raise ValueError("post-confirm pipeline requires DEFINITION/BINDING phase")
    return phase


def reconcile_program_confirm_reread(
    preflight_result: Mapping[str, object],
    *,
    normalized_rows: Iterable[Mapping[str, object]] = (),
    authoritative_program_snapshots: Iterable[Mapping[str, object]] = (),
    authoritative_definition_rows: Iterable[Mapping[str, object]] = (),
    course_snapshots: Iterable[Mapping[str, object]] = (),
    authoritative_binding_snapshots: Iterable[Mapping[str, object]] = (),
    authoritative_program_status_by_id: Mapping[object, object] | None = None,
) -> dict:
    """Guard exact reread scope and reconcile one Program confirm phase."""
    phase = _phase(preflight_result)
    if phase == PHASE_DEFINITION:
        program_rows = guard_definition_program_reread(
            preflight_result,
            authoritative_program_snapshots,
        )
        target_program_ids = target_program_ids_from_reread(
            preflight_result,
            program_rows,
        )
        definition_rows = guard_definition_child_reread(
            authoritative_definition_rows,
            target_program_ids=target_program_ids,
        )
        return reconcile_program_definition_after_confirm(
            normalized_rows,
            preflight_result,
            authoritative_program_snapshots=program_rows,
            authoritative_definition_rows=definition_rows,
            course_snapshots=course_snapshots,
        )

    binding_rows = guard_binding_reread(
        preflight_result,
        authoritative_binding_snapshots,
    )
    statuses = guard_binding_status_reread(
        preflight_result,
        authoritative_program_status_by_id or {},
    )
    return reconcile_program_bindings_after_confirm(
        preflight_result,
        authoritative_binding_snapshots=binding_rows,
        authoritative_program_status_by_id=statuses,
    )
