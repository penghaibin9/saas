"""INT adapter from Program preflight result to Academic File Exchange preview shape.

The shared File Exchange persists preview/error summaries. Program preflight has
six worksheets and Program-level actions, so this adapter keeps row metrics and
Program action metrics separate while preserving explainable error evidence.
No file, database, parser, or dispatcher ownership lives here.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping

from .academic_affairs_school_setup_import_contract import (
    RECONCILIATION_CONFLICT,
    RECONCILIATION_CREATE,
    RECONCILIATION_REJECT,
    RECONCILIATION_REUSE,
)


def _error_item(error: Mapping[str, object]) -> dict:
    row = int(error.get("row") or error.get("rowNo") or 0)
    logical_group = str(error.get("logicalGroup") or "").strip().upper()
    program_key = str(error.get("programKey") or "").strip()
    business_code = str(error.get("businessCode") or error.get("code") or "PROGRAM_PRECHECK_FAILED").strip()
    evidence = dict(error.get("evidence") or {})
    if program_key and "programKey" not in evidence:
        evidence["programKey"] = program_key
    return {
        "row": row,
        "logicalGroup": logical_group,
        "field": f"{logical_group or 'WORKBOOK'}:{business_code}",
        "code": business_code,
        "message": str(error.get("message") or "培养方案导入预检失败"),
        "evidence": evidence,
        "howToResolve": str(error.get("howToResolve") or "").strip(),
    }


def program_preflight_to_file_exchange_preview(
    normalized_rows: Iterable[Mapping[str, object]],
    preflight_result: Mapping[str, object],
) -> dict:
    rows = [dict(row) for row in normalized_rows]
    errors = [_error_item(item) for item in (preflight_result.get("errors") or ())]
    invalid_locations = {
        (str(item.get("logicalGroup") or ""), int(item.get("row") or 0))
        for item in errors
        if int(item.get("row") or 0) > 0
    }
    invalid_rows = len(invalid_locations)

    actions = [dict(item) for item in (preflight_result.get("actions") or ())]
    action_counts = Counter(str(item.get("action") or "").strip().upper() for item in actions)
    allowed_actions = {
        RECONCILIATION_CREATE,
        RECONCILIATION_REUSE,
        RECONCILIATION_CONFLICT,
        RECONCILIATION_REJECT,
        "",
    }
    unknown = sorted(set(action_counts) - allowed_actions)
    if unknown:
        raise ValueError(f"unsupported Program preflight actions: {', '.join(unknown)}")

    return {
        "totalRows": len(rows),
        "validRows": max(0, len(rows) - invalid_rows),
        "invalidRows": invalid_rows,
        "programCount": len({str(row.get("programKey") or "") for row in rows if row.get("programKey")}),
        "createPrograms": int(action_counts[RECONCILIATION_CREATE]),
        "reusePrograms": int(action_counts[RECONCILIATION_REUSE]),
        "conflictPrograms": int(action_counts[RECONCILIATION_CONFLICT]),
        "rejectPrograms": int(action_counts[RECONCILIATION_REJECT]),
        "phase": str((preflight_result.get("binding") or {}).get("phase") or ""),
        "stage": str(preflight_result.get("stage") or ""),
        "programPreflightSafe": bool(preflight_result.get("programPreflightSafe")),
        "errors": errors,
    }
