"""INT authoritative reread reconciliation for Program school-setup confirmation.

A-W4 requires confirm -> reread -> relationship reconciliation, not merely a
successful INSERT/UPDATE count. This pure owner compares the normalized source
against authoritative post-confirm snapshots and produces deterministic SHA-256
evidence. The future shared File Exchange writer owns transaction/SQL; this
module owns only semantic reconciliation.

Two phases are intentionally separate:
- DEFINITION: Program stable identity/main facts + full child definition + prev
  relationship; CREATE must reread as DRAFT, REUSE must remain zero-write.
- BINDING: exact active scope -> Program relationship, superseded predecessor
  evidence, and target Program ENABLED status.

No session, model mutation, dispatcher, FileObject, or ImportJob lifecycle lives
here.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from decimal import Decimal

from .academic_affairs_school_setup_import_contract import (
    PROGRAM_GROUP_BINDING,
    PROGRAM_GROUP_MAIN,
    RECONCILIATION_CREATE,
    RECONCILIATION_REUSE,
)
from .academic_affairs_school_setup_program_binding_policy import (
    PHASE_BINDING,
    PHASE_DEFINITION,
)
from . import academic_affairs_school_setup_program_definition_reconciliation as definition_reconciliation


def _text(value: object, *, uppercase: bool = False) -> str:
    text = str(value or "").strip()
    return text.upper() if uppercase else text


def _positive_int(value: object, *, field: str) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _decimal_text(value: object) -> str:
    parsed = _decimal(value)
    if parsed == 0:
        return "0"
    return format(parsed.normalize(), "f")


def _json_value(value: object):
    if isinstance(value, Decimal):
        return {"$decimal": _decimal_text(value)}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {
            str(key): _json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    return value


def _sha256(value: object) -> str:
    payload = json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _fact_counter_snapshot(counter: Counter) -> list[dict]:
    result = []
    for fact, count in sorted(counter.items(), key=lambda item: repr(item[0])):
        result.append({
            "fact": _json_value(tuple(fact)),
            "count": int(count),
        })
    return result


def _definition_snapshot(
    rows: Iterable[Mapping[str, object]],
    course_credit: Mapping[str, Decimal],
    *,
    existing: bool,
) -> dict:
    counters = definition_reconciliation._definition_counters(
        rows,
        course_credit,
        existing=existing,
    )
    return {
        group: _fact_counter_snapshot(counters[group])
        for group in definition_reconciliation._DEFINITION_GROUPS
    }


def _source_programs(normalized_rows: Iterable[Mapping[str, object]]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for raw in normalized_rows:
        row = dict(raw)
        program_key = _text(row.get("programKey"))
        if not program_key:
            raise ValueError("normalized Program row missing programKey")
        grouped[program_key].append(row)

    result: dict[str, dict] = {}
    for program_key, rows in grouped.items():
        mains = [
            row for row in rows
            if _text(row.get("logicalGroup"), uppercase=True) == PROGRAM_GROUP_MAIN
        ]
        if len(mains) != 1:
            raise ValueError(f"post-confirm reconciliation requires one MAIN row: {program_key}")
        payload = dict(mains[0].get("payload") or {})
        result[program_key] = {
            "rows": rows,
            "main": {
                "seriesKey": _text(payload.get("programSeriesKey"), uppercase=True),
                "version": _positive_int(payload.get("programVersion"), field="programVersion"),
                "programName": _text(payload.get("programName")),
                "majorId": _positive_int(payload.get("majorId"), field="majorId"),
                "gradeYear": _text(payload.get("gradeYear")),
                "totalCredits": _decimal(payload.get("totalCredits") or 0),
            },
        }
    return result


def _authoritative_program_index(rows: Iterable[Mapping[str, object]]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    seen_ids: set[str] = set()
    for raw in rows:
        row = dict(raw)
        series_key = _text(row.get("seriesKey"), uppercase=True)
        version = _positive_int(row.get("version"), field="authoritative Program version")
        if not series_key:
            raise ValueError("authoritative Program snapshot missing seriesKey")
        program_key = f"SERIES:{series_key}:v{version}"
        program_id = _text(row.get("programId"))
        if not program_id:
            raise ValueError(f"authoritative Program snapshot missing programId: {program_key}")
        if program_key in result:
            raise RuntimeError(f"PROGRAM_REREAD_STABLE_KEY_DUPLICATE:{program_key}")
        if program_id in seen_ids:
            raise RuntimeError(f"PROGRAM_REREAD_ID_DUPLICATE:{program_id}")
        seen_ids.add(program_id)
        result[program_key] = {
            "programId": program_id,
            "seriesKey": series_key,
            "version": version,
            "programName": _text(row.get("programName")),
            "majorId": _positive_int(row.get("majorId"), field="authoritative majorId"),
            "gradeYear": _text(row.get("gradeYear")),
            "totalCredits": _decimal(row.get("totalCredits") or 0),
            "prevProgramId": _text(row.get("prevProgramId")),
            "status": _text(row.get("status"), uppercase=True),
        }
    return result


def _error(
    program_key: str,
    code: str,
    message: str,
    *,
    evidence: Mapping[str, object],
    how_to_resolve: str,
) -> dict:
    return {
        "programKey": program_key,
        "businessCode": code,
        "message": message,
        "evidence": _json_value(dict(evidence)),
        "howToResolve": how_to_resolve,
    }


def _require_ready_phase(preflight_result: Mapping[str, object], phase: str) -> list[dict]:
    if not bool(preflight_result.get("programPreflightSafe")):
        raise ValueError("post-confirm reconciliation requires a green preflight")
    if _text(preflight_result.get("stage"), uppercase=True) != "READY":
        raise ValueError("post-confirm reconciliation requires READY stage")
    binding = dict(preflight_result.get("binding") or {})
    if _text(binding.get("phase"), uppercase=True) != phase:
        raise ValueError(f"post-confirm reconciliation requires {phase} phase")
    return [dict(item) for item in (preflight_result.get("actions") or ())]


def reconcile_program_definition_after_confirm(
    normalized_rows: Iterable[Mapping[str, object]],
    preflight_result: Mapping[str, object],
    *,
    authoritative_program_snapshots: Iterable[Mapping[str, object]],
    authoritative_definition_rows: Iterable[Mapping[str, object]],
    course_snapshots: Iterable[Mapping[str, object]],
) -> dict:
    """Reconcile Program DEFINITION confirmation against authoritative reread."""
    actions = _require_ready_phase(preflight_result, PHASE_DEFINITION)
    source = _source_programs(normalized_rows)
    authoritative = _authoritative_program_index(authoritative_program_snapshots)
    course_credit = definition_reconciliation._course_credit_index(course_snapshots)

    definitions_by_program_id: dict[str, list[dict]] = defaultdict(list)
    for raw in authoritative_definition_rows:
        row = dict(raw)
        program_id = _text(row.get("programId"))
        if not program_id:
            raise ValueError("authoritative definition row missing programId")
        definitions_by_program_id[program_id].append(row)

    errors: list[dict] = []
    items: list[dict] = []
    imported = reused = 0
    for action in sorted(actions, key=lambda item: _text(item.get("programKey"))):
        program_key = _text(action.get("programKey"))
        decision = _text(action.get("action"), uppercase=True)
        if decision not in {RECONCILIATION_CREATE, RECONCILIATION_REUSE}:
            raise ValueError(f"green DEFINITION preflight contains unsafe action: {decision}")
        if program_key not in source:
            raise ValueError(f"preflight action has no source Program: {program_key}")
        persisted = authoritative.get(program_key)
        if persisted is None:
            errors.append(_error(
                program_key,
                "PROGRAM_REREAD_NOT_FOUND",
                "确认后按稳定键回读不到培养方案，禁止把写入计为成功",
                evidence={"programKey": program_key},
                how_to_resolve="回滚/标记确认失败并检查事务提交与 tenant scope；不得仅依据 INSERT 行数出成功回执",
            ))
            continue

        source_main = source[program_key]["main"]
        main_mismatches = []
        for field in ("seriesKey", "version", "programName", "majorId", "gradeYear"):
            if source_main[field] != persisted[field]:
                main_mismatches.append({
                    "field": field,
                    "expected": source_main[field],
                    "actual": persisted[field],
                })
        if source_main["totalCredits"] != persisted["totalCredits"]:
            main_mismatches.append({
                "field": "totalCredits",
                "expected": _decimal_text(source_main["totalCredits"]),
                "actual": _decimal_text(persisted["totalCredits"]),
            })

        expected_program_id = _text(action.get("programId"))
        if decision == RECONCILIATION_REUSE:
            reused += 1
            if not expected_program_id or expected_program_id != persisted["programId"]:
                main_mismatches.append({
                    "field": "programId",
                    "expected": expected_program_id,
                    "actual": persisted["programId"],
                })
        else:
            imported += 1
            if persisted["status"] != "DRAFT":
                main_mismatches.append({
                    "field": "status",
                    "expected": "DRAFT",
                    "actual": persisted["status"],
                })
            expected_prev = _text(action.get("predecessorProgramId"))
            if expected_prev != persisted["prevProgramId"]:
                main_mismatches.append({
                    "field": "prevProgramId",
                    "expected": expected_prev,
                    "actual": persisted["prevProgramId"],
                })

        if main_mismatches:
            errors.append(_error(
                program_key,
                "PROGRAM_REREAD_MAIN_MISMATCH",
                "确认后培养方案主档与预检事实不一致",
                evidence={
                    "programId": persisted["programId"],
                    "differentFields": main_mismatches,
                },
                how_to_resolve="按 stable Program key 检查并发覆盖、错误 writer 或错误 tenant/scope；禁止继续生成成功回执",
            ))

        source_definition = _definition_snapshot(
            source[program_key]["rows"],
            course_credit,
            existing=False,
        )
        persisted_definition = _definition_snapshot(
            definitions_by_program_id.get(persisted["programId"], []),
            course_credit,
            existing=True,
        )
        source_hash = _sha256({"main": source_main, "definition": source_definition})
        persisted_main_for_hash = {
            field: persisted[field]
            for field in ("seriesKey", "version", "programName", "majorId", "gradeYear", "totalCredits")
        }
        persisted_hash = _sha256({
            "main": persisted_main_for_hash,
            "definition": persisted_definition,
        })
        hash_match = source_hash == persisted_hash
        if not hash_match:
            errors.append(_error(
                program_key,
                "PROGRAM_REREAD_DEFINITION_HASH_MISMATCH",
                "确认后完整培养方案定义 hash 与源定义不一致",
                evidence={
                    "programId": persisted["programId"],
                    "expectedHash": source_hash,
                    "actualHash": persisted_hash,
                    "expectedCounts": {
                        group: sum(item["count"] for item in source_definition[group])
                        for group in definition_reconciliation._DEFINITION_GROUPS
                    },
                    "actualCounts": {
                        group: sum(item["count"] for item in persisted_definition[group])
                        for group in definition_reconciliation._DEFINITION_GROUPS
                    },
                },
                how_to_resolve="回读并定位缺失/多余/漂移 child definition；不得以 Program 主表存在替代关系对账",
            ))

        items.append({
            "programKey": program_key,
            "programId": persisted["programId"],
            "action": decision,
            "definitionHash": source_hash,
            "rereadDefinitionHash": persisted_hash,
            "hashMatch": hash_match,
            "relationship": {
                "prevProgramId": persisted["prevProgramId"],
                "expectedPrevProgramId": _text(action.get("predecessorProgramId")) if decision == RECONCILIATION_CREATE else persisted["prevProgramId"],
            },
        })

    errors.sort(key=lambda item: (item["programKey"], item["businessCode"]))
    return {
        "phase": PHASE_DEFINITION,
        "reconciliationSafe": not errors,
        "importedPrograms": imported,
        "reusedPrograms": reused,
        "rejectedPrograms": 0,
        "conflictPrograms": 0,
        "programCount": len(actions),
        "items": items,
        "errors": errors,
    }


def _binding_scope_key(row: Mapping[str, object]) -> str:
    explicit = _text(row.get("scopeKey"))
    if explicit:
        return explicit
    major_id = _positive_int(row.get("majorId"), field="binding majorId")
    grade_year = _text(row.get("gradeYear"))
    if not grade_year:
        raise ValueError("authoritative binding snapshot missing gradeYear")
    class_id = row.get("classId")
    if class_id in (None, "", 0, "0"):
        return f"MAJOR:{major_id}:GRADE:{grade_year}:MAJOR_GRADE"
    return f"MAJOR:{major_id}:GRADE:{grade_year}:CLASS:{_positive_int(class_id, field='binding classId')}"


def reconcile_program_bindings_after_confirm(
    preflight_result: Mapping[str, object],
    *,
    authoritative_binding_snapshots: Iterable[Mapping[str, object]],
    authoritative_program_status_by_id: Mapping[str, object],
) -> dict:
    """Reconcile BINDING confirmation against authoritative current relationships."""
    _require_ready_phase(preflight_result, PHASE_BINDING)
    binding = dict(preflight_result.get("binding") or {})
    if not bool(binding.get("bindingWriteAllowed")) or binding.get("errors"):
        raise ValueError("BINDING reconciliation requires bindingWriteAllowed=true")

    rows_by_scope: dict[str, list[dict]] = defaultdict(list)
    for raw in authoritative_binding_snapshots:
        row = dict(raw)
        scope_key = _binding_scope_key(row)
        program_id = _text(row.get("programId"))
        status = _text(row.get("status"), uppercase=True)
        if not program_id or not status:
            raise ValueError(f"authoritative binding snapshot incomplete: {scope_key}")
        rows_by_scope[scope_key].append({
            "scopeKey": scope_key,
            "programId": program_id,
            "status": status,
        })

    statuses = {
        _text(program_id): _text(status, uppercase=True)
        for program_id, status in authoritative_program_status_by_id.items()
    }
    errors: list[dict] = []
    items: list[dict] = []
    created = reused = 0
    active_relationships = []
    for raw in sorted(binding.get("intents") or (), key=lambda item: _text(item.get("scopeKey"))):
        intent = dict(raw)
        scope_key = _text(intent.get("scopeKey"))
        program_key = _text(intent.get("programKey"))
        program_id = _text(intent.get("programId"))
        action = _text(intent.get("action"), uppercase=True)
        if not scope_key or not program_id:
            raise ValueError("binding intent missing scopeKey/programId")
        if action not in {RECONCILIATION_CREATE, RECONCILIATION_REUSE}:
            raise ValueError(f"green BINDING intent contains unsafe action: {action}")
        created += int(action == RECONCILIATION_CREATE)
        reused += int(action == RECONCILIATION_REUSE)

        scope_rows = rows_by_scope.get(scope_key, [])
        active_rows = [row for row in scope_rows if row["status"] == "ACTIVE"]
        if len(active_rows) != 1 or active_rows[0]["programId"] != program_id:
            errors.append(_error(
                program_key,
                "PROGRAM_BINDING_REREAD_ACTIVE_MISMATCH",
                "确认后适用范围没有唯一指向目标培养方案的 ACTIVE binding",
                evidence={
                    "scopeKey": scope_key,
                    "expectedProgramId": program_id,
                    "activeRows": active_rows,
                },
                how_to_resolve="检查 scope anchor 锁、旧 binding supersede 与新 binding insert 是否在同一事务完成",
            ))
        else:
            active_relationships.append({
                "scopeKey": scope_key,
                "programId": program_id,
            })

        supersede_program_id = _text(intent.get("supersedeProgramId"))
        supersede_match = True
        if action == RECONCILIATION_CREATE and supersede_program_id:
            supersede_match = any(
                row["programId"] == supersede_program_id and row["status"] == "SUPERSEDED"
                for row in scope_rows
            )
            if not supersede_match:
                errors.append(_error(
                    program_key,
                    "PROGRAM_BINDING_REREAD_SUPERSEDE_MISSING",
                    "确认后旧 ACTIVE binding 未留下 SUPERSEDED 历史证据",
                    evidence={
                        "scopeKey": scope_key,
                        "expectedSupersededProgramId": supersede_program_id,
                        "scopeRows": scope_rows,
                    },
                    how_to_resolve="检查旧 binding 是否被错误删除或漏改状态；历史关系不得物理覆盖",
                ))

        target_status = statuses.get(program_id, "")
        status_match = target_status == "ENABLED"
        if not status_match:
            errors.append(_error(
                program_key,
                "PROGRAM_BINDING_REREAD_TARGET_STATUS_MISMATCH",
                "适用范围确认后目标培养方案未处于 ENABLED 状态",
                evidence={
                    "programId": program_id,
                    "expectedStatus": "ENABLED",
                    "actualStatus": target_status,
                },
                how_to_resolve="检查 binding writer 的目标状态推进与事务提交；不得只写 binding 不推进目标方案状态",
            ))

        items.append({
            "programKey": program_key,
            "programId": program_id,
            "scopeKey": scope_key,
            "action": action,
            "activeRelationshipMatch": len(active_rows) == 1 and active_rows[0]["programId"] == program_id,
            "supersedeRelationshipMatch": supersede_match,
            "targetStatusMatch": status_match,
        })

    relationship_hash = _sha256(sorted(
        active_relationships,
        key=lambda item: (item["scopeKey"], item["programId"]),
    ))
    errors.sort(key=lambda item: (item["programKey"], item["businessCode"], repr(item["evidence"])))
    return {
        "phase": PHASE_BINDING,
        "reconciliationSafe": not errors,
        "createdBindings": created,
        "reusedBindings": reused,
        "bindingCount": len(binding.get("intents") or ()),
        "activeRelationshipHash": relationship_hash,
        "items": items,
        "errors": errors,
    }
