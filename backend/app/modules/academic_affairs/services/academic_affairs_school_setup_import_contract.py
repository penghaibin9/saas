"""A-W4/INT/A-C5 school-setup import contract for Course/Program onboarding.

This module is deliberately *not* another import framework. It owns no
FileObject/ImportJob/parser/confirm lifecycle and performs no database I/O.
Academic File Exchange remains the orchestration authority; this file freezes
only domain-facing workbook vocabulary and stable business identities.

Hard boundaries:
- Course identity is ``courseCode + version``; courseName is display only.
- Program identity is ``programSeriesKey + programVersion``. ``majorId`` and
  ``gradeYear`` are assertions/scope facts, never Program identity.
- Program binding identity is a relationship anchored to an exact Program
  version; binding scope is not a substitute for Program identity.
- ProgramCourse references an exact versioned Course and carries explicit
  ``module`` + ``formationMode``. Course nature/name never infer formation.
- Program import has six logical groups: MAIN / COURSE / CREDIT_REQUIREMENT /
  PRACTICE / GRADUATION / BINDING.
- Reconciliation actions are exactly CREATE/REUSE/CONFLICT/REJECT.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .academic_affairs_task_formation_policy import normalize_formation_mode

ACADEMIC_COURSE_CATALOG_IMPORT = "ACADEMIC_COURSE_CATALOG"
ACADEMIC_PROGRAM_IMPORT = "ACADEMIC_PROGRAM"

COURSE_TEMPLATE_VERSION = "course-catalog-v1"
PROGRAM_TEMPLATE_VERSION = "program-v2"

RECONCILIATION_CREATE = "CREATE"
RECONCILIATION_REUSE = "REUSE"
RECONCILIATION_CONFLICT = "CONFLICT"
RECONCILIATION_REJECT = "REJECT"
RECONCILIATION_ACTIONS = frozenset({
    RECONCILIATION_CREATE,
    RECONCILIATION_REUSE,
    RECONCILIATION_CONFLICT,
    RECONCILIATION_REJECT,
})

COURSE_HEADER_MAP = {
    "课程代码": "courseCode",
    "版本": "version",
    "课程名称": "courseName",
    "课程类别": "category",
    "课程性质": "nature",
    "学分": "credit",
    "总学时": "hoursTotal",
    "理论学时": "hoursTheory",
    "实践学时": "hoursPractice",
    "实验学时": "hoursExperiment",
    "上机学时": "hoursComputer",
    "考核方式": "examMode",
    "开课单位ID": "ownerCollegeId",
    "课程负责人ID": "ownerTeacherId",
    "是否核心课": "isCore",
    "先修课代码": "prerequisiteCodes",
}
COURSE_REQUIRED_FIELDS = frozenset({
    "courseCode", "version", "courseName", "category", "nature", "credit", "examMode",
})

PROGRAM_GROUP_MAIN = "MAIN"
PROGRAM_GROUP_COURSE = "COURSE"
PROGRAM_GROUP_CREDIT_REQUIREMENT = "CREDIT_REQUIREMENT"
PROGRAM_GROUP_PRACTICE = "PRACTICE"
PROGRAM_GROUP_GRADUATION = "GRADUATION"
PROGRAM_GROUP_BINDING = "BINDING"
PROGRAM_LOGICAL_GROUPS = frozenset({
    PROGRAM_GROUP_MAIN,
    PROGRAM_GROUP_COURSE,
    PROGRAM_GROUP_CREDIT_REQUIREMENT,
    PROGRAM_GROUP_PRACTICE,
    PROGRAM_GROUP_GRADUATION,
    PROGRAM_GROUP_BINDING,
})

# The stable series key is repeated on every logical child group so rows can be
# grouped without guessing from major/grade/name. major/grade remain required on
# MAIN and BINDING because they are authoritative assertions/scope facts there.
PROGRAM_MAIN_REQUIRED_FIELDS = frozenset({
    "programSeriesKey", "programName", "programVersion", "majorId", "gradeYear", "totalCredits",
})
PROGRAM_COURSE_REQUIRED_FIELDS = frozenset({
    "programSeriesKey", "programVersion", "courseCode", "courseVersion",
    "openTermNo", "module", "formationMode",
})
PROGRAM_CREDIT_REQUIREMENT_REQUIRED_FIELDS = frozenset({
    "programSeriesKey", "programVersion", "module", "creditTarget",
})
PROGRAM_PRACTICE_REQUIRED_FIELDS = frozenset({
    "programSeriesKey", "programVersion", "segmentName", "segmentType",
    "openTermNo", "weeks", "credit", "orgMode", "assessmentMode",
})
PROGRAM_GRADUATION_REQUIRED_FIELDS = frozenset({
    "programSeriesKey", "programVersion", "category", "content",
})
PROGRAM_BINDING_REQUIRED_FIELDS = frozenset({
    "programSeriesKey", "programVersion", "majorId", "gradeYear", "bindingScope",
})
PROGRAM_REQUIRED_FIELDS_BY_GROUP = {
    PROGRAM_GROUP_MAIN: PROGRAM_MAIN_REQUIRED_FIELDS,
    PROGRAM_GROUP_COURSE: PROGRAM_COURSE_REQUIRED_FIELDS,
    PROGRAM_GROUP_CREDIT_REQUIREMENT: PROGRAM_CREDIT_REQUIREMENT_REQUIRED_FIELDS,
    PROGRAM_GROUP_PRACTICE: PROGRAM_PRACTICE_REQUIRED_FIELDS,
    PROGRAM_GROUP_GRADUATION: PROGRAM_GRADUATION_REQUIRED_FIELDS,
    PROGRAM_GROUP_BINDING: PROGRAM_BINDING_REQUIRED_FIELDS,
}

BINDING_SCOPE_MAJOR_GRADE = "MAJOR_GRADE"
BINDING_SCOPE_CLASS = "CLASS"
BINDING_SCOPES = frozenset({BINDING_SCOPE_MAJOR_GRADE, BINDING_SCOPE_CLASS})

_SERIES_KEY_RE = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{0,63}$")


@dataclass(frozen=True)
class CourseBusinessKey:
    course_code: str
    version: int

    def text(self) -> str:
        return f"{self.course_code}@v{self.version}"


@dataclass(frozen=True)
class ProgramVersionKey:
    series_key: str
    version: int

    def text(self) -> str:
        return f"SERIES:{self.series_key}:v{self.version}"


@dataclass(frozen=True)
class ProgramBindingKey:
    program: ProgramVersionKey
    major_id: int
    grade_year: str
    scope: str
    class_id: int | None

    def text(self) -> str:
        suffix = f"CLASS:{self.class_id}" if self.class_id is not None else "MAJOR_GRADE"
        return f"{self.program.text()}|MAJOR:{self.major_id}:GRADE:{self.grade_year}:{suffix}"


def _text(value, *, field: str, uppercase: bool = False) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text.upper() if uppercase else text


def _positive_int(value, *, field: str) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _non_negative_decimal(value, *, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative number") from exc
    if parsed < 0:
        raise ValueError(f"{field} must be a non-negative number")
    return parsed


def missing_required_fields(row: Mapping[str, object], required_fields) -> tuple[str, ...]:
    return tuple(sorted(
        field
        for field in required_fields
        if not str(row.get(field) if row.get(field) is not None else "").strip()
    ))


def program_series_key(value: object) -> str:
    """Normalize a caller-supplied immutable Program series identity.

    This is intentionally code-like rather than display-name-like. No hash of
    major/grade/name is generated here: missing identity must fail closed.
    """
    key = _text(value, field="programSeriesKey", uppercase=True)
    if not _SERIES_KEY_RE.fullmatch(key):
        raise ValueError(
            "programSeriesKey must be 1-64 ASCII letters/digits or . _ : - and start with a letter/digit"
        )
    return key


def course_business_key(row: Mapping[str, object]) -> CourseBusinessKey:
    """Resolve the only Course import identity; courseName is never consulted."""
    return CourseBusinessKey(
        course_code=_text(row.get("courseCode"), field="courseCode", uppercase=True),
        version=_positive_int(row.get("version"), field="version"),
    )


def program_version_key(row: Mapping[str, object]) -> ProgramVersionKey:
    """Resolve Program identity without consulting major/grade/name."""
    return ProgramVersionKey(
        series_key=program_series_key(row.get("programSeriesKey")),
        version=_positive_int(row.get("programVersion"), field="programVersion"),
    )


def program_binding_key(row: Mapping[str, object]) -> ProgramBindingKey:
    program = program_version_key(row)
    major_id = _positive_int(row.get("majorId"), field="majorId")
    grade_year = _text(row.get("gradeYear"), field="gradeYear")
    scope = _text(row.get("bindingScope"), field="bindingScope", uppercase=True)
    if scope not in BINDING_SCOPES:
        raise ValueError(f"unsupported bindingScope: {scope}")
    raw_class_id = row.get("classId")
    class_id = None
    if scope == BINDING_SCOPE_CLASS:
        class_id = _positive_int(raw_class_id, field="classId")
    elif str(raw_class_id or "").strip():
        raise ValueError("classId must be empty for MAJOR_GRADE binding")
    return ProgramBindingKey(
        program=program,
        major_id=major_id,
        grade_year=grade_year,
        scope=scope,
        class_id=class_id,
    )


def program_course_reference(row: Mapping[str, object]) -> dict:
    """Normalize a ProgramCourse row without inventing plan or Course truth."""
    program = program_version_key(row)
    course = CourseBusinessKey(
        course_code=_text(row.get("courseCode"), field="courseCode", uppercase=True),
        version=_positive_int(row.get("courseVersion"), field="courseVersion"),
    )
    formation_mode = normalize_formation_mode(row.get("formationMode"), required=True)
    module = _text(row.get("module"), field="module")
    open_term_no = _positive_int(row.get("openTermNo"), field="openTermNo")
    credit_snapshot = None
    if str(row.get("creditSnapshot") or "").strip():
        credit_snapshot = _non_negative_decimal(row.get("creditSnapshot"), field="creditSnapshot")
    return {
        "programKey": program.text(),
        "courseKey": course.text(),
        "module": module,
        "formationMode": formation_mode,
        "openTermNo": open_term_no,
        "creditSnapshot": credit_snapshot,
    }


def program_credit_requirement(row: Mapping[str, object]) -> dict:
    return {
        "programKey": program_version_key(row).text(),
        "module": _text(row.get("module"), field="module"),
        "creditTarget": _non_negative_decimal(row.get("creditTarget"), field="creditTarget"),
    }


def program_practice_segment(row: Mapping[str, object]) -> dict:
    return {
        "programKey": program_version_key(row).text(),
        "segmentName": _text(row.get("segmentName"), field="segmentName"),
        "segmentType": _text(row.get("segmentType"), field="segmentType", uppercase=True),
        "openTermNo": _positive_int(row.get("openTermNo"), field="openTermNo"),
        "weeks": _non_negative_decimal(row.get("weeks"), field="weeks"),
        "credit": _non_negative_decimal(row.get("credit"), field="credit"),
        "orgMode": _text(row.get("orgMode"), field="orgMode", uppercase=True),
        "assessmentMode": _text(row.get("assessmentMode"), field="assessmentMode", uppercase=True),
        "location": str(row.get("location") or "").strip() or None,
    }


def program_graduation_requirement(row: Mapping[str, object]) -> dict:
    return {
        "programKey": program_version_key(row).text(),
        "category": _text(row.get("category"), field="category", uppercase=True),
        "content": _text(row.get("content"), field="content"),
    }


def reconciliation_action(value: object) -> str:
    action = _text(value, field="action", uppercase=True)
    if action not in RECONCILIATION_ACTIONS:
        raise ValueError(f"unsupported reconciliation action: {action}")
    return action
