"""INT ordinary Program import binding-phase policy.

Program definition confirmation and ProgramBinding activation are deliberately
separate operations. Ordinary imports create a new Program version as DRAFT and
must never activate grade/class bindings in the same confirmation. Only a later,
explicit BINDING phase may reconcile ACTIVE bindings after the target Program is
already PUBLISHED/ENABLED and its full definition has been proven reusable.

Legacy migration that needs historically-approved direct activation is not an
ordinary import path and is intentionally rejected here; it requires a separate
privileged migration policy with source approval evidence/effectiveAt/audit.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from .academic_affairs_school_setup_import_contract import (
    BINDING_SCOPE_CLASS,
    PROGRAM_GROUP_BINDING,
    RECONCILIATION_CREATE,
    RECONCILIATION_REUSE,
)

PHASE_DEFINITION = "DEFINITION"
PHASE_BINDING = "BINDING"
ORDINARY_PROGRAM_IMPORT_PHASES = frozenset({PHASE_DEFINITION, PHASE_BINDING})
_BINDABLE_PROGRAM_STATUSES = frozenset({"PUBLISHED", "ENABLED"})


def _phase(value: object) -> str:
    phase = str(value or "").strip().upper()
    if phase not in ORDINARY_PROGRAM_IMPORT_PHASES:
        raise ValueError(
            "ordinary Program import phase must be DEFINITION or BINDING; "
            "privileged historical migration is a separate policy"
        )
    return phase


def _scope_key(payload: Mapping[str, object]) -> str:
    major_id = int(payload.get("majorId") or 0)
    grade_year = str(payload.get("gradeYear") or "").strip()
    scope = str(payload.get("bindingScope") or "").strip().upper()
    if major_id <= 0 or not grade_year:
        raise ValueError("binding payload missing majorId/gradeYear")
    if scope == BINDING_SCOPE_CLASS:
        class_id = int(payload.get("classId") or 0)
        if class_id <= 0:
            raise ValueError("CLASS binding payload missing classId")
        return f"MAJOR:{major_id}:GRADE:{grade_year}:CLASS:{class_id}"
    if scope == "MAJOR_GRADE":
        if payload.get("classId") not in (None, "", 0, "0"):
            raise ValueError("MAJOR_GRADE binding must not contain classId")
        return f"MAJOR:{major_id}:GRADE:{grade_year}:MAJOR_GRADE"
    raise ValueError(f"unsupported bindingScope: {scope}")


def _active_binding_index(rows: Iterable[Mapping[str, object]]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for raw in rows:
        row = dict(raw)
        status = str(row.get("status") or "ACTIVE").strip().upper()
        if status != "ACTIVE":
            continue
        scope_key = str(row.get("scopeKey") or "").strip()
        if not scope_key:
            scope_key = _scope_key(row)
        if scope_key in result:
            raise ValueError(f"multiple ACTIVE ProgramBinding rows for scope {scope_key}")
        program_id = str(row.get("programId") or "").strip()
        if not program_id:
            raise ValueError(f"ACTIVE ProgramBinding {scope_key} missing programId")
        result[scope_key] = dict(row, scopeKey=scope_key, programId=program_id)
    return result


def _source_binding_scope_index(rows: Iterable[Mapping[str, object]]) -> dict[str, list[dict]]:
    """Index source binding intents by the relationship scope they want to own.

    Program identity is intentionally absent from this key. Two different Program
    versions targeting one exact MAJOR_GRADE/CLASS scope in the same BINDING phase
    are mutually exclusive and must fail before any writer can use row order to
    decide which one becomes ACTIVE.
    """
    result: dict[str, list[dict]] = defaultdict(list)
    for raw in rows:
        row = dict(raw)
        if str(row.get("logicalGroup") or "").strip().upper() != PROGRAM_GROUP_BINDING:
            continue
        scope_key = _scope_key(dict(row.get("payload") or {}))
        result[scope_key].append(row)
    return dict(result)


def _source_binding_scope_conflicts(
    rows: Iterable[Mapping[str, object]],
) -> tuple[dict[str, list[dict]], list[dict]]:
    source_by_scope = _source_binding_scope_index(rows)
    conflicting = {
        scope_key: scope_rows
        for scope_key, scope_rows in source_by_scope.items()
        if len(scope_rows) > 1
    }
    errors: list[dict] = []
    for scope_key, scope_rows in sorted(conflicting.items()):
        errors.append({
            "row": min(int(row.get("rowNo") or 0) for row in scope_rows),
            "logicalGroup": PROGRAM_GROUP_BINDING,
            "programKey": "",
            "businessCode": "PROGRAM_BINDING_SOURCE_SCOPE_CONFLICT",
            "message": "同一 BINDING 文件内多个 Program 同时声明同一绑定范围，禁止按行顺序决定 ACTIVE 归属",
            "evidence": {
                "scopeKey": scope_key,
                "programKeys": sorted({str(row.get("programKey") or "") for row in scope_rows}),
                "rows": sorted(int(row.get("rowNo") or 0) for row in scope_rows),
            },
            "howToResolve": "同一专业年级/班级范围仅保留一个目标 Program 后重新预检",
        })
    return conflicting, errors


def program_binding_source_scope_errors(
    normalized_rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Return pure source-only exclusivity blockers for ProgramBinding scopes."""
    _conflicting, errors = _source_binding_scope_conflicts(normalized_rows)
    return errors


def classify_program_binding_phase(
    normalized_rows: Iterable[Mapping[str, object]],
    definition_actions: Iterable[Mapping[str, object]],
    *,
    phase: object,
    program_status_by_id: Mapping[str, object] | None = None,
    active_binding_snapshots: Iterable[Mapping[str, object]] = (),
) -> dict:
    """Return binding intents without writing or silently bypassing Program review."""
    resolved_phase = _phase(phase)
    binding_rows = [
        dict(row) for row in normalized_rows
        if str(row.get("logicalGroup") or "").strip().upper() == PROGRAM_GROUP_BINDING
    ]
    action_by_program = {
        str(action.get("programKey") or ""): dict(action)
        for action in definition_actions
    }

    if resolved_phase == PHASE_DEFINITION:
        return {
            "phase": PHASE_DEFINITION,
            "bindingWriteAllowed": False,
            "deferredCount": len(binding_rows),
            "intents": [
                {
                    "programKey": str(row.get("programKey") or ""),
                    "scopeKey": _scope_key(dict(row.get("payload") or {})),
                    "decision": "DEFER_UNTIL_PUBLISHED",
                    "row": int(row.get("rowNo") or 0),
                }
                for row in binding_rows
            ],
            "errors": [],
        }

    statuses = {str(key): str(value or "").strip().upper() for key, value in (program_status_by_id or {}).items()}
    active_by_scope = _active_binding_index(active_binding_snapshots)
    conflicting_source_scopes, errors = _source_binding_scope_conflicts(binding_rows)
    intents: list[dict] = []

    for row in sorted(binding_rows, key=lambda item: (str(item.get("programKey") or ""), int(item.get("rowNo") or 0))):
        scope_key = _scope_key(dict(row.get("payload") or {}))
        if scope_key in conflicting_source_scopes:
            continue

        program_key = str(row.get("programKey") or "")
        definition = action_by_program.get(program_key)
        if not definition:
            errors.append({
                "row": int(row.get("rowNo") or 0),
                "programKey": program_key,
                "businessCode": "PROGRAM_BINDING_TARGET_NOT_RECONCILED",
                "message": "绑定目标没有对应的 Program definition reconciliation 结果",
                "howToResolve": "先完成该 Program 版本的定义预检/确认，再单独执行 BINDING phase",
            })
            continue
        if str(definition.get("action") or "").upper() != RECONCILIATION_REUSE or not bool(
            definition.get("definitionReconciled")
        ):
            errors.append({
                "row": int(row.get("rowNo") or 0),
                "programKey": program_key,
                "businessCode": "PROGRAM_BINDING_REQUIRES_EXISTING_RECONCILED_PROGRAM",
                "message": "普通绑定确认只能作用于已存在且完整定义已对账的 Program 版本",
                "howToResolve": "若本次是 CREATE，先以 DRAFT 创建并完成正式审核发布，再发起第二轮 BINDING confirm",
            })
            continue
        program_id = str(definition.get("programId") or "").strip()
        status = statuses.get(program_id, "")
        if status not in _BINDABLE_PROGRAM_STATUSES:
            errors.append({
                "row": int(row.get("rowNo") or 0),
                "programKey": program_key,
                "businessCode": "PROGRAM_BINDING_TARGET_NOT_PUBLISHED",
                "message": "目标 Program 尚未发布/启用，禁止激活绑定",
                "evidence": {"programId": program_id, "status": status},
                "howToResolve": "按正式培养方案审核流程将目标版本发布或启用后，再执行 BINDING phase",
            })
            continue

        current = active_by_scope.get(scope_key)
        if current and str(current["programId"]) == program_id:
            intents.append({
                "row": int(row.get("rowNo") or 0),
                "programKey": program_key,
                "programId": program_id,
                "scopeKey": scope_key,
                "action": RECONCILIATION_REUSE,
                "supersedeProgramId": "",
            })
        else:
            intents.append({
                "row": int(row.get("rowNo") or 0),
                "programKey": program_key,
                "programId": program_id,
                "scopeKey": scope_key,
                "action": RECONCILIATION_CREATE,
                "supersedeProgramId": str(current["programId"]) if current else "",
            })

    return {
        "phase": PHASE_BINDING,
        "bindingWriteAllowed": not errors,
        "deferredCount": 0,
        "intents": intents,
        "errors": errors,
    }
