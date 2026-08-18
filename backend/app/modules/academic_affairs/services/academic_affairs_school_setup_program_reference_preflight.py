"""INT authoritative-reference Program import preflight classifier.

This stage consumes bounded tenant-scoped snapshots loaded by a caller after the
source-only preflight. It does not open sessions itself. The classifier proves
Major/Class/Course references and Program series/version semantics without
creating a second truth or mutating organization/course masters.

Expected DB lookup order for the future bridge is fixed outside this pure file:
affairs context -> Major -> SchoolClass(binding only) -> exact Course versions ->
Program series/version. Child-definition and active-binding reconciliation run
after these references are green.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable, Mapping

from .academic_affairs_school_setup_import_contract import (
    BINDING_SCOPE_CLASS,
    PROGRAM_GROUP_BINDING,
    PROGRAM_GROUP_COURSE,
    PROGRAM_GROUP_MAIN,
    RECONCILIATION_CONFLICT,
    RECONCILIATION_CREATE,
    RECONCILIATION_REJECT,
    RECONCILIATION_REUSE,
)
from .academic_affairs_school_setup_program_import_preflight import (
    program_import_source_preflight,
)

_VERSIONABLE_PROGRAM_STATUSES = frozenset({"PUBLISHED", "ENABLED", "FROZEN", "DISABLED"})
_ACTIVE_MAJOR_STATUSES = frozenset({"ACTIVE", "ENABLED"})


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _int(value, *, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be positive")
    return parsed


def _optional_int(value, *, field: str) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    return _int(value, field=field)


def _error(
    row: Mapping[str, object],
    business_code: str,
    message: str,
    *,
    evidence: Mapping[str, object] | None = None,
    how_to_resolve: str,
) -> dict:
    return {
        "row": int(row.get("rowNo") or 0),
        "logicalGroup": str(row.get("logicalGroup") or ""),
        "programKey": str(row.get("programKey") or ""),
        "businessCode": business_code,
        "message": message,
        "evidence": dict(evidence or {}),
        "howToResolve": how_to_resolve,
    }


def _major_index(rows: Iterable[Mapping[str, object]]) -> dict[int, dict]:
    result: dict[int, dict] = {}
    for raw in rows:
        row = dict(raw)
        major_id = _int(row.get("majorId"), field="majorId")
        if major_id in result:
            raise ValueError(f"duplicate Major snapshot: {major_id}")
        education_years = _int(row.get("educationYears"), field="educationYears")
        result[major_id] = dict(row, majorId=major_id, educationYears=education_years)
    return result


def _class_index(rows: Iterable[Mapping[str, object]]) -> dict[int, dict]:
    result: dict[int, dict] = {}
    for raw in rows:
        row = dict(raw)
        class_id = _int(row.get("classId"), field="classId")
        if class_id in result:
            raise ValueError(f"duplicate SchoolClass snapshot: {class_id}")
        result[class_id] = dict(row, classId=class_id)
    return result


def _course_index(rows: Iterable[Mapping[str, object]]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    seen_ids: set[int] = set()
    for raw in rows:
        row = dict(raw)
        course_id = _int(row.get("courseId"), field="courseId")
        if course_id in seen_ids:
            raise ValueError(f"duplicate Course courseId snapshot: {course_id}")
        seen_ids.add(course_id)
        code = str(row.get("courseCode") or "").strip().upper()
        version = _int(row.get("version"), field="course.version")
        if not code:
            raise ValueError("Course snapshot missing courseCode")
        key = f"{code}@v{version}"
        if key in result:
            raise ValueError(f"duplicate Course stable-key snapshot: {key}")
        result[key] = dict(row, courseId=course_id, courseCode=code, version=version)
    return result


def _program_series_index(
    rows: Iterable[Mapping[str, object]],
) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """Validate already-keyed Program series snapshots and return exact/series maps."""
    exact: dict[str, dict] = {}
    by_series: dict[str, list[dict]] = defaultdict(list)
    seen_ids: set[int] = set()
    for raw in rows:
        row = dict(raw)
        program_id = _int(row.get("programId"), field="programId")
        if program_id in seen_ids:
            raise ValueError(f"duplicate Program programId snapshot: {program_id}")
        seen_ids.add(program_id)
        series_key = str(row.get("seriesKey") or "").strip().upper()
        if not series_key:
            raise ValueError(
                "existing Program snapshot missing seriesKey; stable-series schema/backfill is not ready"
            )
        version = _int(row.get("version"), field="program.version")
        key = f"SERIES:{series_key}:v{version}"
        if key in exact:
            raise ValueError(f"duplicate Program stable key snapshot: {key}")
        normalized = dict(
            row,
            programId=program_id,
            seriesKey=series_key,
            version=version,
            prevVersionId=_optional_int(row.get("prevVersionId"), field="prevVersionId"),
        )
        exact[key] = normalized
        by_series[series_key].append(normalized)

    for series_key, versions in by_series.items():
        versions.sort(key=lambda item: int(item["version"]))
        first = versions[0]
        if int(first["version"]) != 1 or first.get("prevVersionId") is not None:
            raise ValueError(f"Program series {series_key} does not have a proven v1 root")
        previous = first
        for current in versions[1:]:
            if int(current["version"]) != int(previous["version"]) + 1:
                raise ValueError(
                    f"Program series {series_key} has version gap: "
                    f"v{previous['version']} -> v{current['version']}"
                )
            if int(current.get("prevVersionId") or 0) != int(previous["programId"]):
                raise ValueError(
                    f"Program series {series_key} prevVersionId mismatch at v{current['version']}"
                )
            if (
                current.get("majorId") != previous.get("majorId")
                or str(current.get("gradeYear") or "") != str(previous.get("gradeYear") or "")
            ):
                raise ValueError(
                    f"Program series {series_key} changes major/grade across versions"
                )
            previous = current
    return exact, by_series


def _main_fact_differences(incoming: Mapping[str, object], existing: Mapping[str, object]) -> list[str]:
    differences: list[str] = []
    pairs = (
        ("programName", str(incoming.get("programName") or "").strip(), str(existing.get("programName") or "").strip()),
        ("majorId", int(incoming.get("majorId") or 0), int(existing.get("majorId") or 0)),
        ("gradeYear", str(incoming.get("gradeYear") or "").strip(), str(existing.get("gradeYear") or "").strip()),
        ("totalCredits", _decimal(incoming.get("totalCredits") or 0), _decimal(existing.get("totalCredits") or 0)),
    )
    for field, left, right in pairs:
        if left != right:
            differences.append(field)
    return differences


def program_import_reference_preflight(
    normalized_rows: Iterable[Mapping[str, object]],
    *,
    major_snapshots: Iterable[Mapping[str, object]],
    class_snapshots: Iterable[Mapping[str, object]] = (),
    course_snapshots: Iterable[Mapping[str, object]] = (),
    program_snapshots: Iterable[Mapping[str, object]] = (),
    allowed_major_ids: set[int] | None = None,
) -> dict:
    """Classify authoritative references and Program version CREATE/REUSE candidates.

    ``allowed_major_ids=None`` means tenant-wide affairs scope. Any concrete set,
    including an empty set, is an explicit restricted scope.
    """
    rows = [dict(row) for row in normalized_rows]
    source = program_import_source_preflight(rows)
    if not source["sourcePreflightSafe"]:
        return {
            "stage": "SOURCE",
            "referencePreflightSafe": False,
            "actions": [],
            "errors": list(source["errors"]),
        }

    majors = _major_index(major_snapshots)
    classes = _class_index(class_snapshots)
    courses = _course_index(course_snapshots)
    programs_exact, programs_by_series = _program_series_index(program_snapshots)

    main_by_key = {
        str(row["programKey"]): row
        for row in rows
        if row["logicalGroup"] == PROGRAM_GROUP_MAIN
    }
    errors: list[dict] = []
    actions: list[dict] = []

    for program_key, main in sorted(main_by_key.items()):
        payload = dict(main.get("payload") or {})
        major_id = int(payload.get("majorId") or 0)
        major = majors.get(major_id)
        if allowed_major_ids is not None and major_id not in allowed_major_ids:
            errors.append(_error(
                main,
                "PROGRAM_MAJOR_OUT_OF_SCOPE",
                "培养方案专业不在当前操作者的数据范围内",
                evidence={"majorId": major_id, "allowedMajorIds": sorted(allowed_major_ids)},
                how_to_resolve="改为当前可管理专业，或由具备对应学院/全校范围的教务人员导入",
            ))
        if major is None:
            errors.append(_error(
                main,
                "PROGRAM_MAJOR_NOT_FOUND",
                "培养方案引用的专业不存在或不属于当前学校",
                evidence={"majorId": major_id},
                how_to_resolve="使用本校现有 Major.id；导入不会创建或修改专业主档",
            ))
        else:
            major_status = str(major.get("status") or "ACTIVE").strip().upper()
            if major_status not in _ACTIVE_MAJOR_STATUSES:
                errors.append(_error(
                    main,
                    "PROGRAM_MAJOR_INACTIVE",
                    "培养方案引用的专业当前不可用",
                    evidence={"majorId": major_id, "status": major_status},
                    how_to_resolve="先在组织主档处理专业状态，不通过培养方案导入修改专业",
                ))
            assertion = payload.get("educationYearsAssertion")
            if assertion is not None and int(assertion) != int(major["educationYears"]):
                errors.append(_error(
                    main,
                    "PROGRAM_EDUCATION_YEARS_ASSERTION_MISMATCH",
                    "源文件学制断言与 Major.education_years 权威值不一致",
                    evidence={
                        "majorId": major_id,
                        "sourceEducationYears": int(assertion),
                        "majorEducationYears": int(major["educationYears"]),
                    },
                    how_to_resolve="修正源文件断言；Major.education_years 是唯一学制真值且不会被导入覆盖",
                ))

        exact = programs_exact.get(program_key)
        series_key = program_key.split(":v", 1)[0].removeprefix("SERIES:")
        requested_version = int(program_key.rsplit(":v", 1)[1])
        series = programs_by_series.get(series_key, [])
        if exact is not None:
            differences = _main_fact_differences(payload, exact)
            existing_status = str(exact.get("status") or "").strip().upper()
            if differences or existing_status == "DISABLED":
                errors.append(_error(
                    main,
                    "PROGRAM_STABLE_KEY_CONFLICT",
                    "相同 programSeriesKey + programVersion 已存在但主事实不一致或版本已停用",
                    evidence={
                        "programKey": program_key,
                        "differentFields": differences,
                        "status": existing_status,
                    },
                    how_to_resolve="核对源系统系列键/版本；禁止覆盖、复活或重解释既有 Program 版本",
                ))
                actions.append({
                    "programKey": program_key,
                    "action": RECONCILIATION_CONFLICT,
                    "programId": str(exact["programId"]),
                    "requiresDefinitionReconciliation": False,
                })
            else:
                actions.append({
                    "programKey": program_key,
                    "action": RECONCILIATION_REUSE,
                    "programId": str(exact["programId"]),
                    "requiresDefinitionReconciliation": True,
                })
        elif requested_version == 1:
            if series:
                errors.append(_error(
                    main,
                    "PROGRAM_VERSION_GAP_OR_COLLISION",
                    "Program 系列已有其它版本但缺少 v1，历史链不可证明",
                    evidence={"programKey": program_key, "existingVersions": [row["version"] for row in series]},
                    how_to_resolve="先修复历史 series/backfill blocker，禁止把当前快照伪装成 v1",
                ))
                actions.append({
                    "programKey": program_key,
                    "action": RECONCILIATION_REJECT,
                    "programId": "",
                    "requiresDefinitionReconciliation": False,
                })
            else:
                actions.append({
                    "programKey": program_key,
                    "action": RECONCILIATION_CREATE,
                    "programId": "",
                    "createStatus": "DRAFT",
                    "predecessorProgramId": "",
                    "requiresDefinitionReconciliation": False,
                })
        else:
            predecessor_key = f"SERIES:{series_key}:v{requested_version - 1}"
            predecessor = programs_exact.get(predecessor_key)
            latest_version = max((int(row["version"]) for row in series), default=0)
            if predecessor is None or latest_version != requested_version - 1:
                errors.append(_error(
                    main,
                    "PROGRAM_PREDECESSOR_MISSING",
                    "普通 Program Import 只能创建同系列当前最新版本的直接后继",
                    evidence={
                        "programKey": program_key,
                        "requiredPredecessorKey": predecessor_key,
                        "latestExistingVersion": latest_version,
                    },
                    how_to_resolve="先补齐并证明同 series 的前一版本；不得为 v3-only 当前快照伪造 v1/v2",
                ))
                actions.append({
                    "programKey": program_key,
                    "action": RECONCILIATION_REJECT,
                    "programId": "",
                    "requiresDefinitionReconciliation": False,
                })
            else:
                predecessor_status = str(predecessor.get("status") or "").strip().upper()
                if predecessor_status not in _VERSIONABLE_PROGRAM_STATUSES:
                    errors.append(_error(
                        main,
                        "PROGRAM_PREDECESSOR_NOT_VERSIONABLE",
                        "前一 Program 版本仍处于编制/审核中，禁止并行创建后继版本",
                        evidence={
                            "predecessorKey": predecessor_key,
                            "predecessorStatus": predecessor_status,
                        },
                        how_to_resolve="先完成前一版本发布/启用/冻结/停用流程，再创建直接后继",
                    ))
                    actions.append({
                        "programKey": program_key,
                        "action": RECONCILIATION_CONFLICT,
                        "programId": "",
                        "requiresDefinitionReconciliation": False,
                    })
                else:
                    actions.append({
                        "programKey": program_key,
                        "action": RECONCILIATION_CREATE,
                        "programId": "",
                        "createStatus": "DRAFT",
                        "predecessorProgramId": str(predecessor["programId"]),
                        "requiresDefinitionReconciliation": False,
                    })

    for row in rows:
        program_key = str(row["programKey"])
        main = main_by_key[program_key]
        main_payload = dict(main.get("payload") or {})
        major_id = int(main_payload.get("majorId") or 0)
        major = majors.get(major_id)

        if row["logicalGroup"] == PROGRAM_GROUP_COURSE:
            payload = dict(row.get("payload") or {})
            course_key = str(payload.get("courseKey") or "")
            course = courses.get(course_key)
            if course is None:
                errors.append(_error(
                    row,
                    "PROGRAM_COURSE_VERSION_NOT_FOUND",
                    "方案课程引用的 exact Course version 不存在",
                    evidence={"courseKey": course_key},
                    how_to_resolve="先在课程库建立并启用该 courseCode + version，不按课程名称猜测匹配",
                ))
            else:
                course_status = str(course.get("status") or "").strip().upper()
                if course_status != "ENABLED":
                    errors.append(_error(
                        row,
                        "PROGRAM_COURSE_VERSION_NOT_ENABLED",
                        "方案课程只能引用已启用的 exact Course version",
                        evidence={"courseKey": course_key, "status": course_status},
                        how_to_resolve="完成课程版本审核并启用，或引用另一已启用正式版本",
                    ))
                credit_snapshot = payload.get("creditSnapshot")
                if credit_snapshot is not None and _decimal(credit_snapshot) != _decimal(course.get("credit") or 0):
                    errors.append(_error(
                        row,
                        "PROGRAM_COURSE_CREDIT_ASSERTION_MISMATCH",
                        "显式 creditSnapshot 与 exact Course version 学分不一致",
                        evidence={
                            "courseKey": course_key,
                            "sourceCreditSnapshot": str(credit_snapshot),
                            "courseCredit": str(course.get("credit")),
                        },
                        how_to_resolve="修正源文件学分断言；课程学分由 exact Course version 提供权威值",
                    ))
            if major is not None:
                max_term = int(major["educationYears"]) * 2
                open_term = int(payload.get("openTermNo") or 0)
                if open_term > max_term:
                    errors.append(_error(
                        row,
                        "PROGRAM_OPEN_TERM_EXCEEDS_MAJOR_EDUCATION_YEARS",
                        "课程开课学期超过 Major.education_years 对应学制范围",
                        evidence={
                            "majorId": major_id,
                            "openTermNo": open_term,
                            "majorEducationYears": int(major["educationYears"]),
                            "maxTermNo": max_term,
                        },
                        how_to_resolve="修正方案开课学期；不得通过导入修改 Major.education_years",
                    ))

        elif row["logicalGroup"] == PROGRAM_GROUP_BINDING:
            payload = dict(row.get("payload") or {})
            binding_major = int(payload.get("majorId") or 0)
            binding_grade = str(payload.get("gradeYear") or "").strip()
            if binding_major != major_id or binding_grade != str(main_payload.get("gradeYear") or "").strip():
                errors.append(_error(
                    row,
                    "PROGRAM_BINDING_SCOPE_ASSERTION_MISMATCH",
                    "BINDING 的专业/年级与目标 Program MAIN 主事实不一致",
                    evidence={
                        "bindingMajorId": binding_major,
                        "bindingGradeYear": binding_grade,
                        "programMajorId": major_id,
                        "programGradeYear": str(main_payload.get("gradeYear") or ""),
                    },
                    how_to_resolve="修正绑定范围；binding 关系不能重定义 Program identity 或主档专业/年级",
                ))
            if str(payload.get("bindingScope") or "").upper() == BINDING_SCOPE_CLASS:
                class_id = int(payload.get("classId") or 0)
                clazz = classes.get(class_id)
                if clazz is None:
                    errors.append(_error(
                        row,
                        "PROGRAM_BINDING_CLASS_NOT_FOUND",
                        "班级特例绑定引用的班级不存在或不属于当前学校",
                        evidence={"classId": class_id},
                        how_to_resolve="选择本校现有正常在读班级",
                    ))
                else:
                    class_major = int(clazz.get("majorId") or 0)
                    class_grade = str(clazz.get("gradeYear") or clazz.get("grade") or "").strip()
                    class_status = str(clazz.get("classStatus") or clazz.get("status") or "").strip().upper()
                    if class_major != binding_major or class_grade != binding_grade:
                        errors.append(_error(
                            row,
                            "PROGRAM_BINDING_CLASS_SCOPE_MISMATCH",
                            "班级所属专业/年级与绑定范围不一致",
                            evidence={
                                "classId": class_id,
                                "classMajorId": class_major,
                                "classGradeYear": class_grade,
                            },
                            how_to_resolve="选择与 Program 专业/年级一致的班级，或改为正确范围",
                        ))
                    if class_status != "NORMAL":
                        errors.append(_error(
                            row,
                            "PROGRAM_BINDING_CLASS_INACTIVE",
                            "仅正常在读班级可作为 Program 班级特例绑定",
                            evidence={"classId": class_id, "classStatus": class_status},
                            how_to_resolve="改用 NORMAL 班级或移除该班级特例",
                        ))

    errors.sort(key=lambda item: (
        str(item.get("programKey") or ""),
        str(item.get("logicalGroup") or ""),
        int(item.get("row") or 0),
        str(item.get("businessCode") or ""),
    ))
    return {
        "stage": "REFERENCE",
        "referencePreflightSafe": not errors,
        "actions": sorted(actions, key=lambda item: str(item["programKey"])),
        "errors": errors,
    }
