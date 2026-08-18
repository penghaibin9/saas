"""INT fail-closed scope guards for authoritative Program confirm rereads.

Preflight snapshot loaders already reject overfetch. Confirmation rereads need the
same property: a writer must not hand semantic reconciliation unrelated Programs,
child definitions, binding scopes, or status rows and rely on the reconciler to
silently ignore them. These pure guards prove every returned row belongs to the
exact confirmation target before hash/relationship reconciliation.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from .academic_affairs_school_setup_program_binding_policy import (
    PHASE_BINDING,
    PHASE_DEFINITION,
)
from .academic_affairs_school_setup_program_snapshot_request_plan import (
    binding_scope_key,
)


def _text(value: object) -> str:
    return str(value or "").strip()


def _phase(preflight_result: Mapping[str, object]) -> str:
    phase = _text((preflight_result.get("binding") or {}).get("phase")).upper()
    if phase not in {PHASE_DEFINITION, PHASE_BINDING}:
        raise ValueError("preflight result missing DEFINITION/BINDING phase")
    return phase


def _stable_key(series_key: object, version: object) -> str:
    series = _text(series_key).upper()
    try:
        parsed_version = int(version)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("PROGRAM_REREAD_SCOPE_VIOLATION:PROGRAM:invalid version") from exc
    if not series or parsed_version <= 0:
        raise RuntimeError("PROGRAM_REREAD_SCOPE_VIOLATION:PROGRAM:missing stable key")
    return f"SERIES:{series}:v{parsed_version}"


def _target_program_keys(preflight_result: Mapping[str, object]) -> set[str]:
    keys = {
        _text(item.get("programKey"))
        for item in (preflight_result.get("actions") or ())
        if _text(item.get("programKey"))
    }
    if not keys:
        raise ValueError("preflight result has no Program actions")
    return keys


def guard_definition_program_reread(
    preflight_result: Mapping[str, object],
    rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    if _phase(preflight_result) != PHASE_DEFINITION:
        raise ValueError("definition Program reread guard is DEFINITION-phase only")
    requested = _target_program_keys(preflight_result)
    result = [dict(row) for row in rows]
    returned: set[str] = set()
    for row in result:
        key = _stable_key(row.get("seriesKey"), row.get("version"))
        if key not in requested:
            raise RuntimeError(
                f"PROGRAM_REREAD_SCOPE_VIOLATION:PROGRAM:{key}:requested={sorted(requested)}"
            )
        if key in returned:
            raise RuntimeError(
                f"PROGRAM_REREAD_SCOPE_VIOLATION:PROGRAM_DUPLICATE:{key}"
            )
        returned.add(key)
    return result


def target_program_ids_from_reread(
    preflight_result: Mapping[str, object],
    program_rows: Iterable[Mapping[str, object]],
) -> tuple[str, ...]:
    guarded = guard_definition_program_reread(preflight_result, program_rows)
    ids: list[str] = []
    seen: set[str] = set()
    for row in guarded:
        program_id = _text(row.get("programId"))
        if not program_id:
            raise RuntimeError("PROGRAM_REREAD_SCOPE_VIOLATION:PROGRAM:missing programId")
        if program_id in seen:
            raise RuntimeError(
                f"PROGRAM_REREAD_SCOPE_VIOLATION:PROGRAM_ID_DUPLICATE:{program_id}"
            )
        seen.add(program_id)
        ids.append(program_id)
    return tuple(sorted(ids))


def guard_definition_child_reread(
    rows: Iterable[Mapping[str, object]],
    *,
    target_program_ids: Iterable[object],
) -> list[dict]:
    result = [dict(row) for row in rows]
    requested = {_text(value) for value in target_program_ids if _text(value)}
    if not requested:
        if not result:
            # A missing Program reread is semantic evidence, not a scope violation.
            # Let the reconciler emit PROGRAM_REREAD_NOT_FOUND for the requested
            # stable key instead of converting the business failure into ValueError.
            return []
        returned_ids = sorted({
            _text(row.get("programId")) or "<missing>"
            for row in result
        })
        raise RuntimeError(
            "PROGRAM_REREAD_SCOPE_VIOLATION:DEFINITION:"
            f"orphanChildren={returned_ids}:requested=[]"
        )
    for row in result:
        program_id = _text(row.get("programId"))
        if not program_id or program_id not in requested:
            raise RuntimeError(
                "PROGRAM_REREAD_SCOPE_VIOLATION:DEFINITION:"
                f"programId={program_id or '<missing>'}:requested={sorted(requested)}"
            )
    return result


def _binding_targets(preflight_result: Mapping[str, object]) -> tuple[set[str], set[str]]:
    if _phase(preflight_result) != PHASE_BINDING:
        raise ValueError("binding reread guard is BINDING-phase only")
    binding = dict(preflight_result.get("binding") or {})
    scopes: set[str] = set()
    program_ids: set[str] = set()
    for intent in binding.get("intents") or ():
        scope = _text(intent.get("scopeKey"))
        program_id = _text(intent.get("programId"))
        if not scope or not program_id:
            raise ValueError("BINDING intent missing scopeKey/programId")
        scopes.add(scope)
        program_ids.add(program_id)
        supersede = _text(intent.get("supersedeProgramId"))
        if supersede:
            program_ids.add(supersede)
    if not scopes:
        raise ValueError("BINDING preflight has no intents")
    return scopes, program_ids


def guard_binding_reread(
    preflight_result: Mapping[str, object],
    rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    requested_scopes, requested_program_ids = _binding_targets(preflight_result)
    result = [dict(row) for row in rows]
    for row in result:
        scope = _text(row.get("scopeKey"))
        if not scope:
            scope = binding_scope_key(row)
        program_id = _text(row.get("programId"))
        if scope not in requested_scopes:
            raise RuntimeError(
                "PROGRAM_REREAD_SCOPE_VIOLATION:BINDING_SCOPE:"
                f"{scope}:requested={sorted(requested_scopes)}"
            )
        if not program_id or program_id not in requested_program_ids:
            raise RuntimeError(
                "PROGRAM_REREAD_SCOPE_VIOLATION:BINDING_PROGRAM:"
                f"{program_id or '<missing>'}:requested={sorted(requested_program_ids)}"
            )
    return result


def guard_binding_status_reread(
    preflight_result: Mapping[str, object],
    statuses: Mapping[object, object],
) -> dict[str, object]:
    _scopes, requested_program_ids = _binding_targets(preflight_result)
    # Status is required only for target Programs, not superseded historical ones.
    target_ids = {
        _text(intent.get("programId"))
        for intent in (preflight_result.get("binding") or {}).get("intents") or ()
        if _text(intent.get("programId"))
    }
    result = {_text(key): value for key, value in statuses.items()}
    for program_id in result:
        if not program_id or program_id not in target_ids:
            raise RuntimeError(
                "PROGRAM_REREAD_SCOPE_VIOLATION:PROGRAM_STATUS:"
                f"{program_id or '<missing>'}:requested={sorted(target_ids)}"
            )
    return result
