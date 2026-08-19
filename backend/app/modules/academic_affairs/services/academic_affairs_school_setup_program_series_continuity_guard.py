"""Fail-closed continuity guard for ordinary Program version CREATE actions.

The reference classifier already proves historical rows inside one series form a
linear chain.  This guard closes the other direction: an incoming vN MAIN row may
not change the immutable major/grade scope relative to its proven vN-1
predecessor.  It is pure and runs in the REFERENCE stage before quality or child
reconciliation.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from .academic_affairs_school_setup_import_contract import (
    PROGRAM_GROUP_MAIN,
    RECONCILIATION_CONFLICT,
    RECONCILIATION_CREATE,
)


def enforce_program_series_continuity(
    normalized_rows: Iterable[Mapping[str, object]],
    reference_result: Mapping[str, object],
    *,
    program_snapshots: Iterable[Mapping[str, object]],
) -> dict:
    result = dict(reference_result)
    actions = [dict(item) for item in result.get("actions") or ()]
    errors = [dict(item) for item in result.get("errors") or ()]
    if not bool(result.get("referencePreflightSafe")):
        result["actions"] = actions
        result["errors"] = errors
        return result

    mains = {
        str(row.get("programKey") or "").strip(): dict(row)
        for row in normalized_rows
        if str(row.get("logicalGroup") or "").strip().upper() == PROGRAM_GROUP_MAIN
    }
    programs_by_id = {
        str(row.get("programId") or "").strip(): dict(row)
        for row in program_snapshots
        if str(row.get("programId") or "").strip()
    }

    for action in actions:
        if str(action.get("action") or "").strip().upper() != RECONCILIATION_CREATE:
            continue
        predecessor_id = str(action.get("predecessorProgramId") or "").strip()
        if not predecessor_id:
            continue  # v1 has no predecessor scope to compare.
        program_key = str(action.get("programKey") or "").strip()
        main = mains.get(program_key)
        predecessor = programs_by_id.get(predecessor_id)
        if main is None or predecessor is None:
            raise RuntimeError(
                "PROGRAM_SERIES_CONTINUITY_EVIDENCE_MISSING:"
                f"programKey={program_key}:predecessorProgramId={predecessor_id}"
            )

        payload = dict(main.get("payload") or {})
        incoming_major = int(payload.get("majorId") or 0)
        predecessor_major = int(predecessor.get("majorId") or 0)
        incoming_grade = str(payload.get("gradeYear") or "").strip()
        predecessor_grade = str(predecessor.get("gradeYear") or "").strip()
        if incoming_major == predecessor_major and incoming_grade == predecessor_grade:
            continue

        errors.append(
            {
                "row": int(main.get("rowNo") or 0),
                "logicalGroup": PROGRAM_GROUP_MAIN,
                "programKey": program_key,
                "businessCode": "PROGRAM_SERIES_SCOPE_DRIFT",
                "message": "同一 Program series 的新版本不得改变专业或年级范围",
                "evidence": {
                    "predecessorProgramId": predecessor_id,
                    "incomingMajorId": incoming_major,
                    "predecessorMajorId": predecessor_major,
                    "incomingGradeYear": incoming_grade,
                    "predecessorGradeYear": predecessor_grade,
                },
                "howToResolve": "保持该 series 与前一版本相同的 majorId/gradeYear；若业务对象已变化，请使用新的不可变 programSeriesKey",
            }
        )
        action["action"] = RECONCILIATION_CONFLICT
        action["programId"] = ""
        action["requiresDefinitionReconciliation"] = False

    errors.sort(
        key=lambda item: (
            str(item.get("programKey") or ""),
            int(item.get("row") or 0),
            str(item.get("businessCode") or ""),
        )
    )
    result["actions"] = actions
    result["errors"] = errors
    result["referencePreflightSafe"] = not errors
    result["blockerCount"] = len(errors)
    return result
