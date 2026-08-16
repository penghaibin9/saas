"""A-W4/A-C5 school setup import contract for Course/Program onboarding.

This module is deliberately *not* another import framework.  It owns no
FileObject/ImportJob/parser/confirm lifecycle and performs no database I/O.
Academic File Exchange remains the only orchestration authority.  The purpose
here is to freeze the domain-facing template vocabulary and stable business
identities before the existing File Exchange is extended by later A-W4/INT
steps.

Hard boundaries:
- course identity is ``courseCode + version``; courseName is display only;
- program identity is a version within major/grade, while binding scope is a
  separate relationship identity;
- ProgramCourse references a versioned Course by code/version and carries an
  explicit formationMode; course nature/name must never infer formation;
- reconciliation actions are exactly CREATE/REUSE/CONFLICT/REJECT.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .academic_affairs_task_formation_policy import normalize_formation_mode

ACADEMIC_COURSE_CATALOG_IMPORT = "ACADEMIC_COURSE_CATALOG"
ACADEMIC_PROGRAM_IMPORT = "ACADEMIC_PROGRAM"

COURSE_TEMPLATE_VERSION = "course-catalog-v1"
PROGRAM_TEMPLATE_VERSION = "program-v1"

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

# Program import is relational rather than a flattened second Program truth.
# Later File Exchange adapters may use separate workbook sheets, but every row
# must resolve to these canonical logical field sets before any domain writer.
PROGRAM_MAIN_REQUIRED_FIELDS = frozenset({
    "programName", "programVersion", "majorId", "gradeYear", "totalCredits",
})
PROGRAM_COURSE_REQUIRED_FIELDS = frozenset({
    "programVersion", "majorId", "gradeYear", "courseCode", "courseVersion",
    "openTermNo", "formationMode",
})
PROGRAM_BINDING_REQUIRED_FIELDS = frozenset({
    "programVersion", "majorId", "gradeYear", "bindingScope",
})

BINDING_SCOPE_MAJOR_GRADE = "MAJOR_GRADE"
BINDING_SCOPE_CLASS = "CLASS"
BINDING_SCOPES = frozenset({BINDING_SCOPE_MAJOR_GRADE, BINDING_SCOPE_CLASS})


@dataclass(frozen=True)
class CourseBusinessKey:
    course_code: str
    version: int

    def text(self) -> str:
        return f"{self.course_code}@v{self.version}"


@dataclass(frozen=True)
class ProgramVersionKey:
    major_id: int
    grade_year: str
    version: int

    def text(self) -> str:
        return f"MAJOR:{self.major_id}:GRADE:{self.grade_year}:v{self.version}"


@dataclass(frozen=True)
class ProgramBindingKey:
    major_id: int
    grade_year: str
    scope: str
    class_id: int | None

    def text(self) -> str:
        suffix = f"CLASS:{self.class_id}" if self.class_id is not None else "MAJOR_GRADE"
        return f"MAJOR:{self.major_id}:GRADE:{self.grade_year}:{suffix}"


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


def course_business_key(row: Mapping[str, object]) -> CourseBusinessKey:
    """Resolve the only Course import identity; courseName is never consulted."""
    return CourseBusinessKey(
        course_code=_text(row.get("courseCode"), field="courseCode", uppercase=True),
        version=_positive_int(row.get("version"), field="version"),
    )


def program_version_key(row: Mapping[str, object]) -> ProgramVersionKey:
    return ProgramVersionKey(
        major_id=_positive_int(row.get("majorId"), field="majorId"),
        grade_year=_text(row.get("gradeYear"), field="gradeYear"),
        version=_positive_int(row.get("programVersion"), field="programVersion"),
    )


def program_binding_key(row: Mapping[str, object]) -> ProgramBindingKey:
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
        major_id=major_id,
        grade_year=grade_year,
        scope=scope,
        class_id=class_id,
    )


def program_course_reference(row: Mapping[str, object]) -> dict:
    """Normalize a ProgramCourse import row without inferring domain truth."""
    program = program_version_key(row)
    course = CourseBusinessKey(
        course_code=_text(row.get("courseCode"), field="courseCode", uppercase=True),
        version=_positive_int(row.get("courseVersion"), field="courseVersion"),
    )
    formation_mode = normalize_formation_mode(row.get("formationMode"), required=True)
    open_term_no = _positive_int(row.get("openTermNo"), field="openTermNo")
    credit_snapshot = None
    if str(row.get("creditSnapshot") or "").strip():
        credit_snapshot = _non_negative_decimal(row.get("creditSnapshot"), field="creditSnapshot")
    return {
        "programKey": program.text(),
        "courseKey": course.text(),
        "formationMode": formation_mode,
        "openTermNo": open_term_no,
        "creditSnapshot": credit_snapshot,
    }


def reconciliation_action(value: object) -> str:
    action = _text(value, field="action", uppercase=True)
    if action not in RECONCILIATION_ACTIONS:
        raise ValueError(f"unsupported reconciliation action: {action}")
    return action
