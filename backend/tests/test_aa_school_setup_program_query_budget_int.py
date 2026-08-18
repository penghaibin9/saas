"""INT query-budget seal for Program preflight loaders.

The public Program preview must batch exact Course-version reads. Growing a
representative definition from one Course to 37 Courses must not grow the SQL
statement count.
"""
from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import event

TID = 1000000000000000001


def _service():
    from app.modules.academic_affairs.services import (
        academic_affairs_school_setup_program_preview_service as service,
    )

    return service


def _adapter():
    from app.modules.academic_affairs.services import (
        academic_affairs_school_setup_program_import_adapter as adapter,
    )

    return adapter


def _seed_authorities(course_count: int) -> tuple[int, list[str]]:
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, Major

    suffix = uuid.uuid4().hex[:8].upper()
    db = get_sessionmaker()()
    try:
        major = Major(
            tenant_id=TID,
            college_id=889003,
            major_name=f"Program query budget {suffix}",
            code=f"PQ{suffix}",
            status="ACTIVE",
            education_years=3,
            enroll_status="ENROLLING",
        )
        db.add(major)
        db.flush()
        courses = [
            AaCourse(
                tenant_id=TID,
                course_code=f"PQ{suffix}-{index:02d}",
                course_name=f"Program query budget course {index:02d}",
                category="MAJOR_CORE",
                nature="REQUIRED",
                credit=1,
                exam_mode="EXAM",
                is_core=True,
                prerequisite_codes_json="[]",
                applicable_majors_json="[]",
                is_all_major=False,
                version=1,
                status="ENABLED",
            )
            for index in range(1, course_count + 1)
        ]
        db.add_all(courses)
        db.commit()
        return int(major.id), [str(row.course_code) for row in courses]
    finally:
        db.close()


def _normalized(*, major_id: int, course_codes: list[str], series_key: str) -> list[dict]:
    total = len(course_codes)
    grouped = {
        "MAIN": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "programName": f"{series_key} 人才培养方案",
            "majorId": major_id,
            "gradeYear": "2026",
            "totalCredits": total,
            "educationYears": 3,
        }],
        "COURSE": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "courseCode": code,
            "courseVersion": 1,
            "openTermNo": ((index - 1) % 6) + 1,
            "module": "MAJOR_CORE",
            "formationMode": "ADMIN_FIXED",
            "creditSnapshot": "",
        } for index, code in enumerate(course_codes, start=1)],
        "CREDIT_REQUIREMENT": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "module": "MAJOR_CORE",
            "creditTarget": total,
        }],
        "PRACTICE": [],
        "GRADUATION": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "category": "ABILITY",
            "content": "完成专业综合项目并通过考核",
            "sortOrder": 1,
        }],
        "BINDING": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "majorId": major_id,
            "gradeYear": "2026",
            "bindingScope": "MAJOR_GRADE",
            "classId": "",
        }],
    }
    return _adapter().normalize_program_import_rows(grouped)


def _run_and_count_selects(engine, callback) -> tuple[dict, list[str]]:
    statements: list[str] = []

    def before_cursor_execute(
        _conn,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ):
        normalized = " ".join(str(statement).upper().split())
        if normalized.startswith("SELECT "):
            statements.append(normalized)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        result = callback()
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    return result, statements


@pytest.mark.usefixtures("db_mode")
def test_definition_preflight_query_budget_is_constant_for_1_and_37_courses(monkeypatch):
    from app.db.session import get_engine

    service = _service()
    monkeypatch.setattr(service, "_tid", lambda: TID)
    monkeypatch.setattr(
        service,
        "build_affairs_context",
        lambda _user, _db: SimpleNamespace(
            scope_type="TENANT_ALL",
            college_ids=set(),
            class_ids=set(),
        ),
    )

    major_id, course_codes = _seed_authorities(37)
    engine = get_engine()

    def preview(codes: list[str], label: str):
        normalized = _normalized(
            major_id=major_id,
            course_codes=codes,
            series_key=f"PROGRAM-QUERY-{label}-{uuid.uuid4().hex[:8].upper()}",
        )
        return service.preview_program_normalized_rows(
            normalized,
            phase="DEFINITION",
            user={"currentRoleCode": "ACADEMIC_ADMIN"},
        )

    one_result, one_selects = _run_and_count_selects(
        engine,
        lambda: preview(course_codes[:1], "ONE"),
    )
    full_result, full_selects = _run_and_count_selects(
        engine,
        lambda: preview(course_codes, "THIRTY-SEVEN"),
    )

    assert one_result["stage"] == "READY"
    assert one_result["programPreflightSafe"] is True
    assert full_result["stage"] == "READY"
    assert full_result["programPreflightSafe"] is True

    # TENANT_ALL fresh DEFINITION is exactly Major + exact Course versions +
    # Program series. Course cardinality must not add statements.
    assert len(one_selects) == 3
    assert len(full_selects) == len(one_selects) == 3
    assert sum("T_AA_COURSE" in statement for statement in full_selects) == 1
    assert all(" FOR UPDATE" not in statement for statement in full_selects)
