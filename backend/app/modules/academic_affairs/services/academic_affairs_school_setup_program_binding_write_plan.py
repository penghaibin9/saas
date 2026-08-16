"""INT pure mutation plan for ordinary Program BINDING confirmation.

This is not a writer. It freezes the lock/mutation order that a later shared
transactional owner must execute after locked BINDING preflight is green. The
current interactive ``bind_grade`` service is not called because File Exchange
confirm must keep preflight revalidation, supersede, insert and audit inside one
caller-owned transaction.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

from .academic_affairs_school_setup_import_contract import (
    RECONCILIATION_CREATE,
    RECONCILIATION_REUSE,
)
from .academic_affairs_school_setup_program_binding_policy import PHASE_BINDING

_SCOPE_RE = re.compile(
    r"^MAJOR:(?P<major>[1-9][0-9]*):GRADE:(?P<grade>[^:]+):"
    r"(?:(?P<major_grade>MAJOR_GRADE)|CLASS:(?P<class_id>[1-9][0-9]*))$"
)


def _scope(scope_key: object) -> dict:
    text = str(scope_key or "").strip()
    match = _SCOPE_RE.fullmatch(text)
    if not match:
        raise ValueError(f"invalid Program binding scopeKey: {text}")
    major_id = int(match.group("major"))
    grade_year = str(match.group("grade") or "").strip()
    class_id = int(match.group("class_id")) if match.group("class_id") else None
    return {
        "scopeKey": text,
        "majorId": major_id,
        "gradeYear": grade_year,
        "classId": class_id,
        "bindingScope": "CLASS" if class_id is not None else "MAJOR_GRADE",
    }


def build_program_binding_write_plan(preflight_result: Mapping[str, object]) -> dict:
    """Build deterministic BINDING mutation intent; performs zero I/O."""
    if not bool(preflight_result.get("programPreflightSafe")):
        raise ValueError("Program binding write plan requires a green full preflight")
    if str(preflight_result.get("stage") or "").strip().upper() != "READY":
        raise ValueError("Program binding write plan requires READY stage")

    binding = dict(preflight_result.get("binding") or {})
    if str(binding.get("phase") or "").strip().upper() != PHASE_BINDING:
        raise ValueError("Program binding write plan is BINDING-phase only")
    if not bool(binding.get("bindingWriteAllowed")) or binding.get("errors"):
        raise ValueError("Program binding write plan requires bindingWriteAllowed=true with zero errors")

    plans = []
    seen_scopes: set[str] = set()
    for raw in sorted(binding.get("intents") or (), key=lambda item: str(item.get("scopeKey") or "")):
        intent = dict(raw)
        scope = _scope(intent.get("scopeKey"))
        scope_key = scope["scopeKey"]
        if scope_key in seen_scopes:
            raise ValueError(f"duplicate Program binding mutation scope: {scope_key}")
        seen_scopes.add(scope_key)

        program_id = str(intent.get("programId") or "").strip()
        if not program_id:
            raise ValueError(f"Program binding intent missing programId: {scope_key}")
        action = str(intent.get("action") or "").strip().upper()
        if action == RECONCILIATION_REUSE:
            plans.append({
                "scopeKey": scope_key,
                "action": RECONCILIATION_REUSE,
                "programId": program_id,
                "lockOrder": [],
                "mutations": [],
                "writeCount": 0,
            })
            continue
        if action != RECONCILIATION_CREATE:
            raise ValueError(f"unsupported Program binding mutation action: {action}")

        anchor_lock = (
            f"CLASS:{scope['classId']}"
            if scope["classId"] is not None
            else f"MAJOR:{scope['majorId']}"
        )
        previous_program_id = str(intent.get("supersedeProgramId") or "").strip()
        mutations = []
        if previous_program_id:
            mutations.append({
                "type": "SUPERSEDE_ACTIVE_BINDING",
                "scopeKey": scope_key,
                "expectedProgramId": previous_program_id,
                "nextStatus": "SUPERSEDED",
            })
        mutations.extend([
            {
                "type": "INSERT_ACTIVE_BINDING",
                "programId": program_id,
                "majorId": scope["majorId"],
                "gradeYear": scope["gradeYear"],
                "classId": scope["classId"],
                "status": "ACTIVE",
            },
            {
                "type": "SET_TARGET_PROGRAM_STATUS",
                "programId": program_id,
                "status": "ENABLED",
            },
            {
                "type": "APPEND_PROGRAM_AUDIT",
                "programId": program_id,
                "action": "BIND",
                "scopeKey": scope_key,
            },
        ])
        plans.append({
            "scopeKey": scope_key,
            "action": RECONCILIATION_CREATE,
            "programId": program_id,
            "lockOrder": [
                f"PROGRAM:{program_id}",
                anchor_lock,
                f"ACTIVE_BINDING_SCOPE:{scope_key}",
            ],
            "mutations": mutations,
            "writeCount": len(mutations),
        })

    return {
        "phase": PHASE_BINDING,
        "sharedTransactionRequired": True,
        "rerunLockedPreflightRequired": True,
        "plans": plans,
    }
