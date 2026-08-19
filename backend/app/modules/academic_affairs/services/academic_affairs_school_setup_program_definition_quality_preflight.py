"""INT authoritative credit-quality preflight for Program import definitions.

Source-only validation can prove workbook structure, but actual credit sufficiency
requires exact Course-version credits from the database. This pure stage runs only
after reference preflight has proven those Course snapshots. It mirrors the
existing Program governance blocker semantics closely enough to prevent import
from knowingly creating a DRAFT that cannot pass submission quality checks.

Rules:
- exact Course-version credit is authoritative; imported creditSnapshot is only an
  assertion and is not a second truth;
- ProgramCourse credit contributes to its declared module and to the mature
  Program total-credit governance check;
- practice-segment credit is tracked separately for explainability and practice
  governance, but does not satisfy ``AaProgram.total_credits`` because the mature
  submission validator compares that target against ProgramCourse credit only;
- Course credit below total or below a configured module target is a blocker;
- Course credit above total is a warning, matching current governance semantics;
- evidence is anchored to MAIN or CREDIT_REQUIREMENT workbook rows;
- no database access or writes live here.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from decimal import Decimal

from .academic_affairs_school_setup_import_contract import (
    PROGRAM_GROUP_COURSE,
    PROGRAM_GROUP_CREDIT_REQUIREMENT,
    PROGRAM_GROUP_MAIN,
    PROGRAM_GROUP_PRACTICE,
)

_GROUP_ORDER = {
    PROGRAM_GROUP_MAIN: 0,
    PROGRAM_GROUP_COURSE: 1,
    PROGRAM_GROUP_CREDIT_REQUIREMENT: 2,
    PROGRAM_GROUP_PRACTICE: 3,
}


def _decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _course_key(row: Mapping[str, object]) -> str:
    code = str(row.get("courseCode") or "").strip().upper()
    try:
        version = int(row.get("version") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("Course quality snapshot version must be positive") from exc
    if not code or version <= 0:
        raise ValueError("Course quality snapshot requires courseCode + positive version")
    return f"{code}@v{version}"


def _course_credit_index(rows: Iterable[Mapping[str, object]]) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for raw in rows:
        row = dict(raw)
        key = _course_key(row)
        if key in result:
            raise ValueError(f"duplicate Course quality snapshot: {key}")
        credit = _decimal(row.get("credit") or 0)
        if credit < 0:
            raise ValueError(f"Course quality snapshot credit cannot be negative: {key}")
        result[key] = credit
    return result


def _issue(
    *,
    program_key: str,
    row: int,
    logical_group: str,
    code: str,
    message: str,
    evidence: Mapping[str, object],
    how_to_resolve: str,
) -> dict:
    return {
        "row": int(row),
        "logicalGroup": logical_group,
        "programKey": program_key,
        "businessCode": code,
        "message": message,
        "evidence": dict(evidence),
        "howToResolve": how_to_resolve,
    }


def program_definition_quality_preflight(
    normalized_rows: Iterable[Mapping[str, object]],
    *,
    course_snapshots: Iterable[Mapping[str, object]],
) -> dict:
    """Check authoritative Program credit sufficiency without I/O."""
    rows = [dict(row) for row in normalized_rows]
    course_credit = _course_credit_index(course_snapshots)
    by_program: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        program_key = str(row.get("programKey") or "").strip()
        if not program_key:
            raise ValueError("normalized Program row missing programKey")
        by_program[program_key].append(row)

    errors: list[dict] = []
    warnings: list[dict] = []
    metrics: list[dict] = []
    for program_key, program_rows in sorted(by_program.items()):
        mains = [
            row for row in program_rows
            if str(row.get("logicalGroup") or "").strip().upper() == PROGRAM_GROUP_MAIN
        ]
        if len(mains) != 1:
            raise ValueError(f"quality preflight requires exactly one MAIN row: {program_key}")
        main_row = mains[0]
        main = dict(main_row.get("payload") or {})
        total_target = _decimal(main.get("totalCredits") or 0)

        target_by_module: dict[str, tuple[Decimal, int]] = {}
        for row in program_rows:
            if str(row.get("logicalGroup") or "").strip().upper() != PROGRAM_GROUP_CREDIT_REQUIREMENT:
                continue
            payload = dict(row.get("payload") or {})
            module = str(payload.get("module") or "").strip()
            if not module:
                raise ValueError(f"quality preflight credit requirement missing module: {program_key}")
            if module in target_by_module:
                raise ValueError(f"quality preflight duplicate module target: {program_key}:{module}")
            target_by_module[module] = (
                _decimal(payload.get("creditTarget") or 0),
                int(row.get("rowNo") or 0),
            )

        actual_by_module: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        course_credit_total = Decimal("0")
        for row in program_rows:
            if str(row.get("logicalGroup") or "").strip().upper() != PROGRAM_GROUP_COURSE:
                continue
            payload = dict(row.get("payload") or {})
            key = str(payload.get("courseKey") or "").strip()
            if key not in course_credit:
                raise ValueError(f"quality preflight missing exact Course snapshot: {key}")
            credit = course_credit[key]
            module = str(payload.get("module") or "").strip()
            if not module:
                raise ValueError(f"quality preflight ProgramCourse missing module: {program_key}:{key}")
            course_credit_total += credit
            actual_by_module[module] += credit

        practice_credit_total = Decimal("0")
        for row in program_rows:
            if str(row.get("logicalGroup") or "").strip().upper() != PROGRAM_GROUP_PRACTICE:
                continue
            credit = _decimal((row.get("payload") or {}).get("credit") or 0)
            if credit < 0:
                raise ValueError(f"quality preflight practice credit cannot be negative: {program_key}")
            practice_credit_total += credit

        # Keep the import gate identical to mature ``validate_program_db``:
        # ``totalCredits`` is checked against ProgramCourse credit only. Practice
        # credit remains separate evidence and cannot turn a submit-time blocker
        # into an import-time false GREEN.
        actual_total = course_credit_total
        if actual_total < total_target:
            errors.append(_issue(
                program_key=program_key,
                row=int(main_row.get("rowNo") or 0),
                logical_group=PROGRAM_GROUP_MAIN,
                code="PROGRAM_ACTUAL_CREDIT_INSUFFICIENT",
                message="课程学分合计未达到培养方案毕业总学分，禁止写入明知无法提交的方案定义",
                evidence={
                    "courseCreditSum": str(course_credit_total),
                    "practiceCreditSum": str(practice_credit_total),
                    "actualCreditSum": str(actual_total),
                    "totalCredits": str(total_target),
                },
                how_to_resolve="补齐 COURSE 定义或修正 MAIN.totalCredits；PRACTICE 学分按实践环节独立治理，不能替代课程学分",
            ))
        elif actual_total > total_target:
            warnings.append(_issue(
                program_key=program_key,
                row=int(main_row.get("rowNo") or 0),
                logical_group=PROGRAM_GROUP_MAIN,
                code="PROGRAM_ACTUAL_CREDIT_EXCEEDED",
                message="课程学分合计超过培养方案毕业总学分，请确认是否存在选修冗余",
                evidence={
                    "courseCreditSum": str(course_credit_total),
                    "practiceCreditSum": str(practice_credit_total),
                    "actualCreditSum": str(actual_total),
                    "totalCredits": str(total_target),
                },
                how_to_resolve="确认超出课程学分是否为允许的选修冗余；如不是，请调整 COURSE 或毕业总学分",
            ))

        for module, (target, target_row_no) in sorted(target_by_module.items()):
            actual = actual_by_module.get(module, Decimal("0"))
            if actual < target:
                errors.append(_issue(
                    program_key=program_key,
                    row=target_row_no,
                    logical_group=PROGRAM_GROUP_CREDIT_REQUIREMENT,
                    code="PROGRAM_MODULE_CREDIT_INSUFFICIENT",
                    message="课程模块实际学分未达到配置的模块目标学分",
                    evidence={
                        "module": module,
                        "actualCredit": str(actual),
                        "creditTarget": str(target),
                    },
                    how_to_resolve="补齐该模块 COURSE 定义或调整 CREDIT_REQUIREMENT 目标；PRACTICE 学分不会被静默计入课程模块",
                ))

        metrics.append({
            "programKey": program_key,
            "courseCreditSum": str(course_credit_total),
            "practiceCreditSum": str(practice_credit_total),
            "actualCreditSum": str(actual_total),
            "totalCredits": str(total_target),
            "moduleActualCredits": {
                module: str(actual_by_module[module])
                for module in sorted(actual_by_module)
            },
            "moduleTargetCredits": {
                module: str(target_by_module[module][0])
                for module in sorted(target_by_module)
            },
        })

    def sort_key(item: Mapping[str, object]):
        group = str(item.get("logicalGroup") or "")
        return (
            str(item.get("programKey") or ""),
            _GROUP_ORDER.get(group, 99),
            int(item.get("row") or 0),
            str(item.get("businessCode") or ""),
            repr(item.get("evidence") or {}),
        )

    errors.sort(key=sort_key)
    warnings.sort(key=sort_key)
    return {
        "definitionQualitySafe": not errors,
        "programMetrics": metrics,
        "errors": errors,
        "warnings": warnings,
    }
