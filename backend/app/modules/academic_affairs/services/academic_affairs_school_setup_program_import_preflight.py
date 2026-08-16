"""INT source-only Program import preflight.

This is the first, zero-database stage of Program import validation. It consumes
only rows already normalized by ``academic_affairs_school_setup_program_import_adapter``.
No Major/Course/Program/Binding query belongs here; those bounded authoritative
lookups are a later stage. Rejecting structural source errors before opening a
session keeps malformed workbooks cheap and deterministic.
"""
from __future__ import annotations

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
    PROGRAM_LOGICAL_GROUPS,
)


def _error(
    row: Mapping[str, object] | None,
    business_code: str,
    message: str,
    *,
    evidence: Mapping[str, object] | None = None,
    how_to_resolve: str,
) -> dict:
    return {
        "row": int(row.get("rowNo") or 0) if row else 0,
        "logicalGroup": str(row.get("logicalGroup") or "") if row else "",
        "programKey": str(row.get("programKey") or "") if row else "",
        "businessCode": business_code,
        "message": message,
        "evidence": dict(evidence or {}),
        "howToResolve": how_to_resolve,
    }


def _decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _sorted_rows(rows: Iterable[Mapping[str, object]]) -> list[dict]:
    normalized = [dict(row) for row in rows]
    for row in normalized:
        group = str(row.get("logicalGroup") or "").strip().upper()
        if group not in PROGRAM_LOGICAL_GROUPS:
            raise ValueError(f"normalized row has unsupported logicalGroup: {group}")
        if not str(row.get("programKey") or "").strip():
            raise ValueError("normalized row missing programKey")
        if not str(row.get("definitionKey") or "").strip():
            raise ValueError("normalized row missing definitionKey")
        try:
            row_no = int(row.get("rowNo") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("normalized row has invalid rowNo") from exc
        if row_no <= 0:
            raise ValueError("normalized row has invalid rowNo")
        row["logicalGroup"] = group
        row["rowNo"] = row_no
    group_order = {
        PROGRAM_GROUP_MAIN: 0,
        PROGRAM_GROUP_COURSE: 1,
        PROGRAM_GROUP_CREDIT_REQUIREMENT: 2,
        PROGRAM_GROUP_PRACTICE: 3,
        PROGRAM_GROUP_GRADUATION: 4,
        PROGRAM_GROUP_BINDING: 5,
    }
    return sorted(
        normalized,
        key=lambda row: (
            str(row["programKey"]),
            group_order[row["logicalGroup"]],
            int(row["rowNo"]),
            str(row["definitionKey"]),
        ),
    )


def program_import_source_preflight(normalized_rows: Iterable[Mapping[str, object]]) -> dict:
    """Validate workbook-internal Program structure without database access."""
    rows = _sorted_rows(normalized_rows)
    if not rows:
        message = "培养方案导入文件没有任何数据行，禁止以空工作簿进入数据库预检"
        error = _error(
            None,
            "PROGRAM_SOURCE_EMPTY",
            message,
            evidence={"dataRows": 0},
            how_to_resolve="按 program-v2 六工作表模板至少填写一套 MAIN/COURSE/CREDIT_REQUIREMENT/GRADUATION 定义后重新预检",
        )
        return {
            "totalRows": 0,
            "programCount": 0,
            "invalidRows": 1,
            "blockerCount": 1,
            "sourcePreflightSafe": False,
            "errors": [error],
        }

    errors: list[dict] = []

    by_program: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_program[str(row["programKey"])].append(row)

    definition_counts = Counter(
        (str(row["logicalGroup"]), str(row["definitionKey"])) for row in rows
    )
    duplicate_rows: set[tuple[str, int]] = set()
    for row in rows:
        duplicate_key = (str(row["logicalGroup"]), str(row["definitionKey"]))
        if definition_counts[duplicate_key] <= 1:
            continue
        duplicate_rows.add((str(row["logicalGroup"]), int(row["rowNo"])))
        errors.append(_error(
            row,
            "PROGRAM_SOURCE_DUPLICATE_DEFINITION",
            "同一逻辑组内出现重复定义，禁止按工作表行顺序猜测覆盖关系",
            evidence={
                "definitionKey": str(row["definitionKey"]),
                "occurrences": int(definition_counts[duplicate_key]),
            },
            how_to_resolve="同一 Program 版本的同一定义只保留一行后重新预检",
        ))

    for program_key, program_rows in sorted(by_program.items()):
        mains = [row for row in program_rows if row["logicalGroup"] == PROGRAM_GROUP_MAIN]
        children = [row for row in program_rows if row["logicalGroup"] != PROGRAM_GROUP_MAIN]
        if not mains:
            first = children[0] if children else None
            errors.append(_error(
                first,
                "PROGRAM_MAIN_MISSING",
                "子表引用的 Program 版本没有 MAIN 主定义",
                evidence={"programKey": program_key},
                how_to_resolve="为该 programSeriesKey + programVersion 补充且仅补充一条 MAIN 定义",
            ))
            continue
        if len(mains) > 1:
            errors.append(_error(
                mains[0],
                "PROGRAM_MAIN_NOT_UNIQUE",
                "同一 Program 版本必须且只能有一条 MAIN 主定义",
                evidence={"programKey": program_key, "mainRows": [int(row["rowNo"]) for row in mains]},
                how_to_resolve="删除重复 MAIN 行，只保留一条权威主定义",
            ))
            continue

        main = mains[0]
        main_payload = dict(main.get("payload") or {})
        courses = [row for row in program_rows if row["logicalGroup"] == PROGRAM_GROUP_COURSE]
        credit_requirements = [
            row for row in program_rows if row["logicalGroup"] == PROGRAM_GROUP_CREDIT_REQUIREMENT
        ]
        graduation_requirements = [
            row for row in program_rows if row["logicalGroup"] == PROGRAM_GROUP_GRADUATION
        ]

        if not courses:
            errors.append(_error(
                main,
                "PROGRAM_COURSE_EMPTY",
                "培养方案没有 COURSE 定义，无法形成可审核课程结构",
                evidence={"programKey": program_key},
                how_to_resolve="至少增加一条关联正式课程版本的 COURSE 定义",
            ))
        if not credit_requirements:
            errors.append(_error(
                main,
                "PROGRAM_CREDIT_REQUIREMENT_EMPTY",
                "培养方案没有 CREDIT_REQUIREMENT 分模块学分要求",
                evidence={"programKey": program_key},
                how_to_resolve="按课程模块配置 creditTarget 后重新预检",
            ))
        if not graduation_requirements:
            errors.append(_error(
                main,
                "PROGRAM_GRADUATION_REQUIREMENT_EMPTY",
                "培养方案没有 GRADUATION 毕业要求条目",
                evidence={"programKey": program_key},
                how_to_resolve="至少增加一条知识/能力/素质/证书类毕业要求",
            ))

        education_years = main_payload.get("educationYearsAssertion")
        if education_years is not None:
            max_term = int(education_years) * 2
            for row in courses:
                open_term = int((row.get("payload") or {}).get("openTermNo") or 0)
                if open_term > max_term:
                    errors.append(_error(
                        row,
                        "PROGRAM_OPEN_TERM_EXCEEDS_SOURCE_EDUCATION_YEARS",
                        "课程开课学期超过源文件声明的学制范围",
                        evidence={
                            "openTermNo": open_term,
                            "educationYearsAssertion": int(education_years),
                            "maxTermNo": max_term,
                        },
                        how_to_resolve="修正开课学期或源文件学制断言；数据库学制不会被导入修改",
                    ))

        if credit_requirements:
            target_rows = [
                row for row in credit_requirements
                if (row["logicalGroup"], int(row["rowNo"])) not in duplicate_rows
            ]
            target_sum = sum(
                (_decimal((row.get("payload") or {}).get("creditTarget") or 0) for row in target_rows),
                Decimal("0"),
            )
            total_credits = _decimal(main_payload.get("totalCredits") or 0)
            if target_rows and target_sum != total_credits:
                errors.append(_error(
                    main,
                    "PROGRAM_CREDIT_TARGET_SUM_MISMATCH",
                    "分模块目标学分合计与毕业总学分不一致",
                    evidence={
                        "creditTargetSum": str(target_sum),
                        "totalCredits": str(total_credits),
                    },
                    how_to_resolve="调整 CREDIT_REQUIREMENT 的 creditTarget，使合计精确等于 MAIN.totalCredits",
                ))

        defined_modules = {
            str((row.get("payload") or {}).get("module") or "").strip()
            for row in credit_requirements
        }
        for row in courses:
            module = str((row.get("payload") or {}).get("module") or "").strip()
            if credit_requirements and module not in defined_modules:
                errors.append(_error(
                    row,
                    "PROGRAM_COURSE_MODULE_UNDECLARED",
                    "COURSE 使用的模块未在 CREDIT_REQUIREMENT 中定义",
                    evidence={"module": module, "definedModules": sorted(defined_modules)},
                    how_to_resolve="增加对应模块学分要求，或把课程归入已定义模块",
                ))

    errors.sort(key=lambda item: (
        str(item.get("programKey") or ""),
        str(item.get("logicalGroup") or ""),
        int(item.get("row") or 0),
        str(item.get("businessCode") or ""),
    ))
    return {
        "totalRows": len(rows),
        "programCount": len(by_program),
        "invalidRows": len({
            (str(item.get("logicalGroup") or ""), int(item.get("row") or 0))
            for item in errors
            if int(item.get("row") or 0) > 0
        }),
        "blockerCount": len(errors),
        "sourcePreflightSafe": not errors,
        "errors": errors,
    }
