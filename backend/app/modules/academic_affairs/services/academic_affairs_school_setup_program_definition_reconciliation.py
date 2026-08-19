"""INT full Program-version definition reconciliation.

Reference preflight may classify an exact Program stable key as a REUSE candidate,
but idempotent reuse is not proven until all definition children match. This pure
module compares the complete normalized definition snapshot as unordered sets:
COURSE / CREDIT_REQUIREMENT / PRACTICE / GRADUATION. BINDING is deliberately
excluded because it is a separate relationship lifecycle and is reconciled after
Program definition identity is settled.

No database access or writes live here. Existing ProgramCourse rows without
explicit formation provenance fail closed instead of receiving a guessed mode.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Iterable, Mapping

from .academic_affairs_school_setup_import_contract import (
    PROGRAM_GROUP_BINDING,
    PROGRAM_GROUP_COURSE,
    PROGRAM_GROUP_CREDIT_REQUIREMENT,
    PROGRAM_GROUP_GRADUATION,
    PROGRAM_GROUP_MAIN,
    PROGRAM_GROUP_PRACTICE,
    RECONCILIATION_CONFLICT,
    RECONCILIATION_CREATE,
    RECONCILIATION_REJECT,
    RECONCILIATION_REUSE,
)

_DEFINITION_GROUPS = (
    PROGRAM_GROUP_COURSE,
    PROGRAM_GROUP_CREDIT_REQUIREMENT,
    PROGRAM_GROUP_PRACTICE,
    PROGRAM_GROUP_GRADUATION,
)
_COURSE_KEY_RE = re.compile(r"^(.+)@v([1-9][0-9]*)$", re.IGNORECASE)


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _text(value, *, uppercase: bool = False) -> str:
    text = str(value or "").strip()
    return text.upper() if uppercase else text


def _normalize_course_key(value: object) -> str:
    raw = _text(value)
    match = _COURSE_KEY_RE.fullmatch(raw)
    if not match:
        raise ValueError(f"invalid Course stable key: {raw}")
    return f"{match.group(1).strip().upper()}@v{int(match.group(2))}"


def _course_credit_index(rows: Iterable[Mapping[str, object]]) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for raw in rows:
        row = dict(raw)
        code = _text(row.get("courseCode"), uppercase=True)
        try:
            version = int(row.get("version") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("course snapshot version must be a positive integer") from exc
        if not code or version <= 0:
            raise ValueError("course snapshot requires courseCode + positive version")
        key = f"{code}@v{version}"
        if key in result:
            raise ValueError(f"duplicate Course stable-key snapshot: {key}")
        result[key] = _decimal(row.get("credit") or 0)
    return result


def _course_fact(payload: Mapping[str, object], course_credit: Mapping[str, Decimal], *, existing: bool) -> tuple:
    course_key = _normalize_course_key(payload.get("courseKey"))
    module = _text(payload.get("module"))
    if not module:
        raise ValueError("ProgramCourse definition missing module")
    formation_mode = _text(payload.get("formationMode"), uppercase=True)
    if not formation_mode:
        if existing:
            raise RuntimeError("PROGRAM_EXISTING_FORMATION_PROVENANCE_MISSING")
        raise ValueError("ProgramCourse source definition missing formationMode")
    try:
        open_term_no = int(payload.get("openTermNo") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("ProgramCourse definition openTermNo must be positive") from exc
    if open_term_no <= 0:
        raise ValueError("ProgramCourse definition openTermNo must be positive")
    explicit_credit = payload.get("creditSnapshot")
    if explicit_credit is None or str(explicit_credit).strip() == "":
        if course_key not in course_credit:
            raise ValueError(f"Course credit snapshot missing for {course_key}")
        effective_credit = course_credit[course_key]
    else:
        effective_credit = _decimal(explicit_credit)
    return (course_key, module, formation_mode, open_term_no, effective_credit)


def _credit_fact(payload: Mapping[str, object]) -> tuple:
    module = _text(payload.get("module"))
    if not module:
        raise ValueError("credit requirement missing module")
    return (module, _decimal(payload.get("creditTarget") or 0))


def _practice_fact(payload: Mapping[str, object]) -> tuple:
    return (
        _text(payload.get("segmentName")),
        _text(payload.get("segmentType"), uppercase=True),
        int(payload.get("openTermNo") or 0),
        _decimal(payload.get("weeks") or 0),
        _decimal(payload.get("credit") or 0),
        _text(payload.get("orgMode"), uppercase=True),
        _text(payload.get("location")) or None,
        _text(payload.get("assessmentMode"), uppercase=True),
        int(payload.get("sortOrder") or 0),
    )


def _graduation_fact(payload: Mapping[str, object]) -> tuple:
    return (
        _text(payload.get("category"), uppercase=True),
        _text(payload.get("content")),
        int(payload.get("sortOrder") or 0),
    )


def _canonical_fact(
    group: str,
    payload: Mapping[str, object],
    course_credit: Mapping[str, Decimal],
    *,
    existing: bool,
) -> tuple:
    if group == PROGRAM_GROUP_COURSE:
        return _course_fact(payload, course_credit, existing=existing)
    if group == PROGRAM_GROUP_CREDIT_REQUIREMENT:
        return _credit_fact(payload)
    if group == PROGRAM_GROUP_PRACTICE:
        return _practice_fact(payload)
    if group == PROGRAM_GROUP_GRADUATION:
        return _graduation_fact(payload)
    raise ValueError(f"unsupported Program definition group: {group}")


def _definition_counters(
    rows: Iterable[Mapping[str, object]],
    course_credit: Mapping[str, Decimal],
    *,
    existing: bool,
) -> dict[str, Counter]:
    counters = {group: Counter() for group in _DEFINITION_GROUPS}
    for raw in rows:
        row = dict(raw)
        group = _text(row.get("logicalGroup"), uppercase=True)
        if group in {PROGRAM_GROUP_MAIN, PROGRAM_GROUP_BINDING}:
            continue
        if group not in counters:
            raise ValueError(f"unsupported Program definition group: {group}")
        payload = dict(row.get("payload") or {})
        fact = _canonical_fact(group, payload, course_credit, existing=existing)
        counters[group][fact] += 1
    return counters


def _counter_evidence(counter: Counter) -> list[dict]:
    """Return bounded, deterministic non-PII fact evidence."""
    result = []
    for fact, count in sorted(counter.items(), key=lambda item: repr(item[0]))[:20]:
        result.append({"fact": [str(value) if value is not None else None for value in fact], "count": int(count)})
    return result


def reconcile_program_definitions(
    normalized_rows: Iterable[Mapping[str, object]],
    reference_actions: Iterable[Mapping[str, object]],
    *,
    existing_definition_rows: Iterable[Mapping[str, object]] = (),
    course_snapshots: Iterable[Mapping[str, object]] = (),
) -> dict:
    """Finalize CREATE/REUSE decisions by comparing full Program definition snapshots.

    Existing definition rows must contain ``programId``, ``logicalGroup`` and a
    canonical ``payload``. A future DB bridge is responsible for joining
    ProgramCourse.course_id to exact Course code/version before calling here.
    """
    source_rows = [dict(row) for row in normalized_rows]
    actions = [dict(action) for action in reference_actions]
    course_credit = _course_credit_index(course_snapshots)

    source_by_program: dict[str, list[dict]] = defaultdict(list)
    for row in source_rows:
        source_by_program[str(row.get("programKey") or "")].append(row)

    existing_by_program_id: dict[str, list[dict]] = defaultdict(list)
    for raw in existing_definition_rows:
        row = dict(raw)
        program_id = str(row.get("programId") or "").strip()
        if not program_id:
            raise ValueError("existing definition row missing programId")
        existing_by_program_id[program_id].append(row)

    final_actions: list[dict] = []
    errors: list[dict] = []
    for action in sorted(actions, key=lambda item: str(item.get("programKey") or "")):
        program_key = str(action.get("programKey") or "")
        current_action = str(action.get("action") or "").upper()
        if current_action in {RECONCILIATION_CREATE, RECONCILIATION_CONFLICT, RECONCILIATION_REJECT}:
            final_actions.append(dict(action))
            continue
        if current_action != RECONCILIATION_REUSE:
            raise ValueError(f"unsupported reference action: {current_action}")

        program_id = str(action.get("programId") or "").strip()
        if not program_id:
            raise ValueError(f"REUSE action for {program_key} missing programId")
        source_definition_rows = source_by_program.get(program_key, [])
        existing_rows = existing_by_program_id.get(program_id, [])
        try:
            incoming = _definition_counters(source_definition_rows, course_credit, existing=False)
            persisted = _definition_counters(existing_rows, course_credit, existing=True)
        except RuntimeError as exc:
            if str(exc) != "PROGRAM_EXISTING_FORMATION_PROVENANCE_MISSING":
                raise
            errors.append({
                "programKey": program_key,
                "businessCode": "PROGRAM_EXISTING_FORMATION_PROVENANCE_MISSING",
                "message": "既有 ProgramCourse 缺少显式 formationMode provenance，禁止猜测后复用",
                "evidence": {"programId": program_id},
                "howToResolve": "先按 migration inventory 证明并回填 formation provenance；未知/冲突历史必须阻断",
            })
            final_actions.append({
                **action,
                "action": RECONCILIATION_CONFLICT,
                "requiresDefinitionReconciliation": False,
            })
            continue

        mismatches = []
        for group in _DEFINITION_GROUPS:
            if incoming[group] != persisted[group]:
                missing = incoming[group] - persisted[group]
                extra = persisted[group] - incoming[group]
                mismatches.append({
                    "logicalGroup": group,
                    "missingFromExisting": _counter_evidence(missing),
                    "extraInExisting": _counter_evidence(extra),
                })
        if mismatches:
            errors.append({
                "programKey": program_key,
                "businessCode": "PROGRAM_DEFINITION_SNAPSHOT_CONFLICT",
                "message": "相同 Program 稳定键的完整定义快照与现有版本不一致，禁止覆盖式 REUSE",
                "evidence": {"programId": program_id, "groupDiffs": mismatches},
                "howToResolve": "核对源文件；若业务定义需要变化，请创建同 series 的正式后继版本",
            })
            final_actions.append({
                **action,
                "action": RECONCILIATION_CONFLICT,
                "requiresDefinitionReconciliation": False,
            })
        else:
            final_actions.append({
                **action,
                "action": RECONCILIATION_REUSE,
                "requiresDefinitionReconciliation": False,
                "definitionReconciled": True,
            })

    return {
        "definitionReconciliationSafe": not errors,
        "actions": final_actions,
        "errors": errors,
    }
