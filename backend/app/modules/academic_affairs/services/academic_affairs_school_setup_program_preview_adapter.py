"""INT adapter from Program preflight result to Academic File Exchange preview shape.

Program import spans six worksheets and Program-level actions. This adapter keeps
row metrics separate from Program action metrics, preserves blocker evidence, and
also carries non-blocking quality warnings/metrics so governance evidence is not
lost before the shared File Exchange owner persists the preview.
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


def _evidence_item(item: Mapping[str, object], *, default_message: str) -> dict:
    row = int(item.get("row") or item.get("rowNo") or 0)
    logical_group = str(item.get("logicalGroup") or "").strip().upper()
    program_key = str(item.get("programKey") or "").strip()
    business_code = str(
        item.get("businessCode") or item.get("code") or "PROGRAM_PRECHECK_FAILED"
    ).strip()
    evidence = dict(item.get("evidence") or {})
    if program_key and "programKey" not in evidence:
        evidence["programKey"] = program_key
    return {
        "row": row,
        "logicalGroup": logical_group,
        "field": f"{logical_group or 'WORKBOOK'}:{business_code}",
        "code": business_code,
        "message": str(item.get("message") or default_message),
        "evidence": evidence,
        "howToResolve": str(item.get("howToResolve") or "").strip(),
    }


def program_preflight_to_file_exchange_preview(
    normalized_rows: Iterable[Mapping[str, object]],
    preflight_result: Mapping[str, object],
) -> dict:
    rows = [dict(row) for row in normalized_rows]
    errors = [
        _evidence_item(item, default_message="培养方案导入预检失败")
        for item in (preflight_result.get("errors") or ())
    ]
    quality = dict(preflight_result.get("quality") or {})
    warnings = [
        _evidence_item(item, default_message="培养方案导入存在治理提示")
        for item in (quality.get("warnings") or ())
    ]
    invalid_locations = {
        (str(item.get("logicalGroup") or ""), int(item.get("row") or 0))
        for item in errors
        if int(item.get("row") or 0) > 0
    }
    invalid_rows = len(invalid_locations)
    if errors and invalid_rows == 0:
        # Workbook/program-level blockers have row=0. They still must make the
        # preview invalid instead of looking like an all-green zero-row import.
        invalid_rows = 1

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
        "warningCount": len(warnings),
        "warnings": warnings,
        "qualityMetrics": [dict(item) for item in (quality.get("programMetrics") or ())],
        "errors": errors,
    }
