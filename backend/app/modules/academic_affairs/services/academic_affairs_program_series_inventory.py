"""Academic INT Program stable-series dirty-data inventory.

This module is intentionally read-only and schema-free.  It proves whether the
legacy ``AaProgram.prev_version_id`` graph can be assigned a stable series key
without guessing from program name, major, grade, binding scope, or row order.

A migration may consume ``proposedBackfill`` only when
``migrationPreflightSafe`` is true.  Any structural ambiguity blocks the whole
backfill instead of partially guessing history.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping


def _int(value: object, *, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be positive")
    return parsed


def _optional_int(value: object, *, field: str) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    return _int(value, field=field)


def _grade(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _blocker(code: str, message: str, *, program_ids: Iterable[int] = (), evidence: Mapping[str, object] | None = None) -> dict:
    return {
        "code": code,
        "message": message,
        "programIds": sorted({int(value) for value in program_ids}),
        "evidence": dict(evidence or {}),
        "howToResolve": {
            "PROGRAM_ROW_INVALID": "修复非法 programId/tenantId/version/prevVersionId 后重新盘点",
            "PROGRAM_ID_DUPLICATE": "清理重复主键来源；不得按输入顺序覆盖",
            "PROGRAM_PARENT_MISSING": "补齐可证明的前序版本，或将无法证明的历史转入 baseline migration policy",
            "PROGRAM_PARENT_CROSS_TENANT": "修复跨租户 prevVersionId 污染；禁止跨租户串链",
            "PROGRAM_VERSION_FORK": "人工确认唯一直接后继；不得自动挑选分支",
            "PROGRAM_VERSION_CYCLE": "修复 prevVersionId 环；循环历史不能自动回填 series key",
            "PROGRAM_VERSION_NOT_DIRECT_SUCCESSOR": "修复版本号/前驱关系，使链严格 v1→v2→…",
            "PROGRAM_SERIES_SCOPE_DRIFT": "核对 majorId/gradeYear；版本链内作用域漂移必须先人工定责",
            "PROGRAM_ROOT_NOT_V1": "补齐可证明的 v1 历史，或使用独立 baseline migration policy",
            "PROGRAM_SERIES_VERSION_COLLISION": "修复同一可证明 series 内重复 version；不得靠新 key 掩盖冲突",
        }.get(code, "修复脏数据并重新盘点"),
    }


def inventory_program_series(rows: Iterable[Mapping[str, object]]) -> dict:
    """Audit legacy Program version graphs and propose deterministic series keys.

    Required input fields: ``programId``, ``tenantId``, ``majorId``,
    ``gradeYear``, ``version``, ``prevVersionId``.  Extra fields are ignored on
    purpose; notably ``programName`` and binding scope never participate in
    identity.
    """
    normalized: list[dict] = []
    blockers: list[dict] = []
    seen_ids: set[int] = set()

    for ordinal, raw in enumerate(rows, start=1):
        item = dict(raw)
        try:
            program_id = _int(item.get("programId"), field="programId")
            tenant_id = _int(item.get("tenantId"), field="tenantId")
            version = _int(item.get("version"), field="version")
            prev_version_id = _optional_int(item.get("prevVersionId"), field="prevVersionId")
            major_id = _optional_int(item.get("majorId"), field="majorId")
        except ValueError as exc:
            blockers.append(_blocker(
                "PROGRAM_ROW_INVALID",
                "Program inventory row contains an invalid identifier/version",
                evidence={"ordinal": ordinal, "error": str(exc)},
            ))
            continue

        if program_id in seen_ids:
            blockers.append(_blocker(
                "PROGRAM_ID_DUPLICATE",
                "Program inventory input contains duplicate programId",
                program_ids=[program_id],
                evidence={"programId": program_id},
            ))
            continue
        seen_ids.add(program_id)
        normalized.append({
            "programId": program_id,
            "tenantId": tenant_id,
            "majorId": major_id,
            "gradeYear": _grade(item.get("gradeYear")),
            "version": version,
            "prevVersionId": prev_version_id,
        })

    by_id = {row["programId"]: row for row in normalized}
    children: dict[int, list[int]] = defaultdict(list)

    for row in normalized:
        program_id = row["programId"]
        parent_id = row["prevVersionId"]
        if parent_id is None:
            continue
        parent = by_id.get(parent_id)
        if parent is None:
            blockers.append(_blocker(
                "PROGRAM_PARENT_MISSING",
                "Program prevVersionId points to a missing row",
                program_ids=[program_id],
                evidence={"programId": program_id, "prevVersionId": parent_id},
            ))
            continue
        if parent["tenantId"] != row["tenantId"]:
            blockers.append(_blocker(
                "PROGRAM_PARENT_CROSS_TENANT",
                "Program prevVersionId crosses tenant boundary",
                program_ids=[program_id, parent_id],
                evidence={
                    "programTenantId": row["tenantId"],
                    "parentTenantId": parent["tenantId"],
                    "prevVersionId": parent_id,
                },
            ))
            continue
        children[parent_id].append(program_id)

    for parent_id, child_ids in sorted(children.items()):
        if len(child_ids) > 1:
            blockers.append(_blocker(
                "PROGRAM_VERSION_FORK",
                "Program version graph has more than one direct successor",
                program_ids=[parent_id, *child_ids],
                evidence={"parentProgramId": parent_id, "childProgramIds": sorted(child_ids)},
            ))

    root_by_id: dict[int, int] = {}
    for start in normalized:
        start_id = start["programId"]
        current = start
        path: list[int] = []
        path_set: set[int] = set()
        chain_ok = True

        while True:
            current_id = current["programId"]
            if current_id in path_set:
                cycle_start = path.index(current_id)
                cycle_ids = path[cycle_start:] + [current_id]
                blockers.append(_blocker(
                    "PROGRAM_VERSION_CYCLE",
                    "Program prevVersionId graph contains a cycle",
                    program_ids=cycle_ids,
                    evidence={"cycleProgramIds": cycle_ids},
                ))
                chain_ok = False
                break
            path.append(current_id)
            path_set.add(current_id)

            parent_id = current["prevVersionId"]
            if parent_id is None:
                if current["version"] != 1:
                    blockers.append(_blocker(
                        "PROGRAM_ROOT_NOT_V1",
                        "Program version chain root is not v1",
                        program_ids=path,
                        evidence={"rootProgramId": current_id, "rootVersion": current["version"]},
                    ))
                    chain_ok = False
                if chain_ok:
                    root_by_id[start_id] = current_id
                break

            parent = by_id.get(parent_id)
            if parent is None or parent["tenantId"] != current["tenantId"]:
                chain_ok = False
                break
            if current["version"] != parent["version"] + 1:
                blockers.append(_blocker(
                    "PROGRAM_VERSION_NOT_DIRECT_SUCCESSOR",
                    "Program version is not the direct successor of prevVersionId",
                    program_ids=[current_id, parent_id],
                    evidence={
                        "programId": current_id,
                        "version": current["version"],
                        "parentProgramId": parent_id,
                        "parentVersion": parent["version"],
                    },
                ))
                chain_ok = False
            if current["majorId"] != parent["majorId"] or current["gradeYear"] != parent["gradeYear"]:
                blockers.append(_blocker(
                    "PROGRAM_SERIES_SCOPE_DRIFT",
                    "Program majorId/gradeYear changes inside one prevVersionId chain",
                    program_ids=[current_id, parent_id],
                    evidence={
                        "programMajorId": current["majorId"],
                        "parentMajorId": parent["majorId"],
                        "programGradeYear": current["gradeYear"],
                        "parentGradeYear": parent["gradeYear"],
                    },
                ))
                chain_ok = False
            current = parent

    # De-duplicate repeated findings caused by walking the same dirty chain from
    # multiple descendants while preserving deterministic ordering.
    unique_blockers: list[dict] = []
    signatures: set[tuple] = set()
    for issue in blockers:
        signature = (
            issue["code"],
            tuple(issue["programIds"]),
            repr(sorted(issue["evidence"].items())),
        )
        if signature not in signatures:
            signatures.add(signature)
            unique_blockers.append(issue)
    blockers = unique_blockers

    proposed: list[dict] = []
    if not blockers:
        seen_series_versions: set[tuple[int, str, int]] = set()
        for row in sorted(normalized, key=lambda value: (value["tenantId"], root_by_id[value["programId"]], value["version"], value["programId"])):
            root_id = root_by_id[row["programId"]]
            series_key = f"LEGACY-{root_id}"
            identity = (row["tenantId"], series_key, row["version"])
            if identity in seen_series_versions:
                blockers.append(_blocker(
                    "PROGRAM_SERIES_VERSION_COLLISION",
                    "Two Program rows would collide on tenant + seriesKey + version",
                    program_ids=[row["programId"]],
                    evidence={"tenantId": row["tenantId"], "seriesKey": series_key, "version": row["version"]},
                ))
                proposed = []
                break
            seen_series_versions.add(identity)
            proposed.append({
                "programId": row["programId"],
                "tenantId": row["tenantId"],
                "version": row["version"],
                "rootProgramId": root_id,
                "seriesKey": series_key,
            })

    tenants = sorted({row["tenantId"] for row in normalized})
    roots = sorted({item["rootProgramId"] for item in proposed}) if proposed else []
    return {
        "totalRows": len(normalized),
        "tenantCount": len(tenants),
        "rootCount": len(roots),
        "blockerCount": len(blockers),
        "blockers": blockers,
        "proposedBackfill": proposed if not blockers else [],
        "migrationPreflightSafe": not blockers,
    }
