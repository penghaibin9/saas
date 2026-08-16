"""A-W4 deterministic Course/Program import dry-run classifiers.

No file lifecycle and no database access lives here. Academic File Exchange is
responsible for secure parsing and for loading bounded tenant-scoped snapshots;
this module deterministically classifies those facts before any domain writer.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable, Mapping

from .academic_affairs_school_setup_import_contract import (
    RECONCILIATION_CONFLICT,
    RECONCILIATION_CREATE,
    RECONCILIATION_REJECT,
    RECONCILIATION_REUSE,
)

_COURSE_COMPARE_FIELDS = (
    "courseName",
    "courseNameEn",
    "category",
    "nature",
    "credit",
    "hoursTotal",
    "hoursTheory",
    "hoursPractice",
    "hoursExperiment",
    "hoursComputer",
    "examMode",
    "ownerCollegeId",
    "ownerTeacherId",
    "isCore",
    "description",
    "prerequisiteCodes",
)


def _course_key(course_code: object, version: object) -> str:
    return f"{str(course_code or '').strip().upper()}@v{int(version)}"


def _snapshot_key(row: Mapping[str, object]) -> str:
    return _course_key(row.get("courseCode"), row.get("version"))


def _normalize_compare_value(field: str, value):
    if field in {"credit"}:
        return float(value or 0)
    if field in {
        "hoursTotal", "hoursTheory", "hoursPractice", "hoursExperiment", "hoursComputer",
        "ownerCollegeId", "ownerTeacherId",
    }:
        return int(value) if value not in (None, "") else None
    if field == "isCore":
        return bool(value)
    if field == "prerequisiteCodes":
        return tuple(str(item).strip().upper() for item in (value or []) if str(item).strip())
    if value is None:
        return None
    return str(value).strip()


def _payload_differences(incoming: Mapping[str, object], existing: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(
        field
        for field in _COURSE_COMPARE_FIELDS
        if _normalize_compare_value(field, incoming.get(field))
        != _normalize_compare_value(field, existing.get(field))
    )


def _item(row: Mapping[str, object], action: str, code: str, message: str, *, evidence=None, how_to_resolve="") -> dict:
    return {
        "row": int(row["rowNo"]),
        "businessKey": str(row["businessKey"]),
        "action": action,
        "code": code,
        "message": message,
        "evidence": dict(evidence or {}),
        "howToResolve": how_to_resolve,
    }


def course_catalog_preflight(
    normalized_rows: Iterable[Mapping[str, object]],
    existing_courses: Iterable[Mapping[str, object]],
    *,
    allowed_college_ids: set[int] | None = None,
) -> dict:
    """Classify Course Catalog rows with no writes and no name-based identity.

    ``existing_courses`` must be the result of one tenant-scoped batch lookup
    for all incoming course codes.  ``allowed_college_ids=None`` means the
    caller has school-wide authority; an empty/non-empty set is an explicit
    college scope and is enforced per row.
    """
    rows = [dict(row) for row in normalized_rows]
    existing = [dict(row) for row in existing_courses]
    source_key_counts = Counter(str(row["businessKey"]) for row in rows)

    existing_by_key: dict[str, dict] = {}
    versions_by_code: dict[str, list[dict]] = defaultdict(list)
    for course in existing:
        key = _snapshot_key(course)
        if key in existing_by_key:
            raise ValueError(f"duplicate existing Course stable key: {key}")
        existing_by_key[key] = course
        versions_by_code[str(course.get("courseCode") or "").strip().upper()].append(course)
    for values in versions_by_code.values():
        values.sort(key=lambda item: int(item.get("version") or 0))

    items: list[dict] = []
    errors: list[dict] = []
    counts = {
        RECONCILIATION_CREATE: 0,
        RECONCILIATION_REUSE: 0,
        RECONCILIATION_CONFLICT: 0,
        RECONCILIATION_REJECT: 0,
    }

    for row in rows:
        key = str(row["businessKey"])
        code = str(row["courseCode"]).strip().upper()
        version = int(row["version"])
        payload = dict(row.get("payload") or {})

        if source_key_counts[key] > 1:
            item = _item(
                row,
                RECONCILIATION_REJECT,
                "DUPLICATE_SOURCE_KEY",
                "同一文件内课程稳定键重复，禁止按行顺序猜测覆盖关系",
                evidence={"businessKey": key, "sourceOccurrences": source_key_counts[key]},
                how_to_resolve="每个 courseCode + version 仅保留一行后重新预检",
            )
        elif allowed_college_ids is not None and (
            payload.get("ownerCollegeId") is None
            or int(payload["ownerCollegeId"]) not in allowed_college_ids
        ):
            item = _item(
                row,
                RECONCILIATION_REJECT,
                "COURSE_OWNER_OUT_OF_SCOPE",
                "开课单位不在当前操作者的数据范围内",
                evidence={
                    "ownerCollegeId": str(payload.get("ownerCollegeId") or ""),
                    "allowedCollegeIds": [str(value) for value in sorted(allowed_college_ids)],
                },
                how_to_resolve="改为本学院课程，或由具备对应学院/全校范围的教务人员导入",
            )
        elif key in existing_by_key:
            current = existing_by_key[key]
            status = str(current.get("status") or "").strip().upper()
            if status == "DISABLED":
                item = _item(
                    row,
                    RECONCILIATION_CONFLICT,
                    "COURSE_VERSION_DISABLED",
                    "相同 courseCode + version 已存在但已停用，导入不得自动复活历史版本",
                    evidence={"businessKey": key, "status": status},
                    how_to_resolve="在课程库显式处理停用/新版本，不通过导入覆盖历史版本",
                )
            else:
                differences = _payload_differences(payload, dict(current.get("payload") or {}))
                if differences:
                    item = _item(
                        row,
                        RECONCILIATION_CONFLICT,
                        "COURSE_STABLE_KEY_CONFLICT",
                        "相同 courseCode + version 的课程事实与现有版本不一致，禁止覆盖",
                        evidence={"businessKey": key, "differentFields": list(differences), "status": status},
                        how_to_resolve="核对源系统版本；如需修改已启用课程，请按正式课程版本流程生成后继版本",
                    )
                else:
                    item = _item(
                        row,
                        RECONCILIATION_REUSE,
                        "COURSE_VERSION_REUSE",
                        "相同课程稳定键与事实已存在，本行幂等复用",
                        evidence={"businessKey": key, "status": status},
                    )
        else:
            versions = versions_by_code.get(code, [])
            if not versions:
                if version == 1:
                    item = _item(
                        row,
                        RECONCILIATION_CREATE,
                        "COURSE_VERSION_CREATE",
                        "新课程代码从 v1 建立版本链",
                        evidence={"businessKey": key},
                    )
                else:
                    item = _item(
                        row,
                        RECONCILIATION_REJECT,
                        "COURSE_PREDECESSOR_MISSING",
                        "新课程代码不能从非 v1 版本开始导入",
                        evidence={"businessKey": key, "requestedVersion": version},
                        how_to_resolve="先导入 v1，或补齐可证明的历史版本链",
                    )
            else:
                latest = versions[-1]
                latest_version = int(latest.get("version") or 0)
                latest_status = str(latest.get("status") or "").strip().upper()
                if version != latest_version + 1:
                    item = _item(
                        row,
                        RECONCILIATION_REJECT,
                        "COURSE_VERSION_GAP",
                        "导入版本不是现有课程的直接后继版本",
                        evidence={
                            "businessKey": key,
                            "latestVersion": latest_version,
                            "requestedVersion": version,
                        },
                        how_to_resolve="补齐缺失版本，或改为当前最新版本的直接后继版本",
                    )
                elif latest_status != "ENABLED":
                    item = _item(
                        row,
                        RECONCILIATION_CONFLICT,
                        "COURSE_PREDECESSOR_NOT_ENABLED",
                        "当前最新课程版本尚未启用，禁止并行创建下一版本",
                        evidence={
                            "predecessorKey": _snapshot_key(latest),
                            "predecessorStatus": latest_status,
                        },
                        how_to_resolve="先完成当前版本审核/退回处理，再决定是否创建后继版本",
                    )
                else:
                    item = _item(
                        row,
                        RECONCILIATION_CREATE,
                        "COURSE_SUCCESSOR_CREATE",
                        "现有 ENABLED 课程将按正式版本链创建直接后继版本",
                        evidence={"predecessorKey": _snapshot_key(latest), "businessKey": key},
                    )

        counts[item["action"]] += 1
        items.append(item)
        if item["action"] in {RECONCILIATION_CONFLICT, RECONCILIATION_REJECT}:
            errors.append({
                "row": item["row"],
                "field": "courseCode/version",
                "code": item["code"],
                "message": item["message"],
                "evidence": item["evidence"],
                "howToResolve": item["howToResolve"],
            })

    invalid = counts[RECONCILIATION_CONFLICT] + counts[RECONCILIATION_REJECT]
    valid = counts[RECONCILIATION_CREATE] + counts[RECONCILIATION_REUSE]
    return {
        "totalRows": len(rows),
        "validRows": valid,
        "invalidRows": invalid,
        "createRows": counts[RECONCILIATION_CREATE],
        "reuseRows": counts[RECONCILIATION_REUSE],
        "conflictRows": counts[RECONCILIATION_CONFLICT],
        "rejectRows": counts[RECONCILIATION_REJECT],
        "items": items,
        "errors": errors,
    }
