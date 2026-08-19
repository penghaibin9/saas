"""INT contract for the non-executable ordinary Program definition write plan."""
from __future__ import annotations

import inspect
from decimal import Decimal

import pytest


def _adapter():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter
    return adapter


def _planner():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_write_plan as planner
    return planner


def _normalized_rows():
    return _adapter().normalize_program_import_rows({
        "MAIN": [{
            "programSeriesKey": "CS-SOFT",
            "programVersion": 2,
            "programName": "软件技术2026培养方案V2",
            "majorId": 10,
            "gradeYear": "2026",
            "totalCredits": "3",
            "educationYears": 3,
        }],
        "COURSE": [{
            "programSeriesKey": "CS-SOFT",
            "programVersion": 2,
            "courseCode": "CS101",
            "courseVersion": 3,
            "openTermNo": 2,
            "module": "专业核心",
            "formationMode": "SELECTABLE",
        }],
        "CREDIT_REQUIREMENT": [{
            "programSeriesKey": "CS-SOFT",
            "programVersion": 2,
            "module": "专业核心",
            "creditTarget": "3",
        }],
        "PRACTICE": [{
            "programSeriesKey": "CS-SOFT",
            "programVersion": 2,
            "segmentName": "综合实训",
            "segmentType": "COURSE_DESIGN",
            "openTermNo": 2,
            "weeks": 1,
            "credit": 1,
            "orgMode": "CENTRALIZED",
            "assessmentMode": "CHECK",
        }],
        "GRADUATION": [{
            "programSeriesKey": "CS-SOFT",
            "programVersion": 2,
            "category": "ABILITY",
            "content": "完成综合项目",
        }],
        "BINDING": [{
            "programSeriesKey": "CS-SOFT",
            "programVersion": 2,
            "majorId": 10,
            "gradeYear": "2026",
            "bindingScope": "MAJOR_GRADE",
        }],
    })


def _create_preflight():
    return {
        "stage": "READY",
        "programPreflightSafe": True,
        "binding": {"phase": "DEFINITION", "bindingWriteAllowed": False},
        "actions": [{
            "programKey": "SERIES:CS-SOFT:v2",
            "action": "CREATE",
            "programId": "",
            "createStatus": "DRAFT",
            "predecessorProgramId": "501",
            "requiresDefinitionReconciliation": False,
        }],
    }


def _course_snapshots(credit="3"):
    return [{
        "courseId": 301,
        "courseCode": "CS101",
        "version": 3,
        "courseName": "程序设计",
        "status": "ENABLED",
        "credit": Decimal(credit),
    }]


def test_create_plan_uses_imported_definition_not_interactive_clone_semantics():
    plan = _planner().build_program_definition_write_plan(
        _normalized_rows(),
        _create_preflight(),
        course_snapshots=_course_snapshots(),
    )
    assert plan["phase"] == "DEFINITION"
    assert plan["executable"] is False
    assert plan["schemaPrerequisites"] == [
        "AaProgram.series_key",
        "AaProgramCourse.formation_mode",
    ]

    item = plan["programPlans"][0]
    assert item["action"] == "CREATE"
    assert item["writeCount"] == 4  # Program + Course + Practice + Graduation
    assert item["writes"]["program"] == {
        "seriesKey": "CS-SOFT",
        "version": 2,
        "programName": "软件技术2026培养方案V2",
        "majorId": 10,
        "gradeYear": "2026",
        "totalCredits": Decimal("3"),
        "requirementJson": {
            "creditStructure": [{"module": "专业核心", "creditTarget": Decimal("3")}],
        },
        "prevProgramId": "501",
        "status": "DRAFT",
    }
    assert item["writes"]["courses"] == [{
        "courseId": 301,
        "courseKey": "CS101@v3",
        "courseName": "程序设计",
        "openTermNo": 2,
        "module": "专业核心",
        "formationMode": "SELECTABLE",
        "creditSnapshot": Decimal("3"),
    }]
    assert item["writes"]["bindings"] == []
    assert "educationYears" not in repr(item["writes"])


def test_reuse_plan_is_strict_zero_write():
    preflight = {
        "stage": "READY",
        "programPreflightSafe": True,
        "binding": {"phase": "DEFINITION"},
        "actions": [{
            "programKey": "SERIES:CS-SOFT:v2",
            "action": "REUSE",
            "programId": "777",
            "requiresDefinitionReconciliation": False,
            "definitionReconciled": True,
        }],
    }
    plan = _planner().build_program_definition_write_plan(
        _normalized_rows(),
        preflight,
        course_snapshots=_course_snapshots(),
    )
    assert plan["programPlans"] == [{
        "programKey": "SERIES:CS-SOFT:v2",
        "action": "REUSE",
        "programId": "777",
        "writeCount": 0,
        "writes": {},
    }]


def test_write_plan_rejects_binding_phase_or_non_draft_create():
    binding = _create_preflight()
    binding["binding"] = {"phase": "BINDING"}
    with pytest.raises(ValueError, match="DEFINITION-phase only"):
        _planner().build_program_definition_write_plan(
            _normalized_rows(), binding, course_snapshots=_course_snapshots()
        )

    non_draft = _create_preflight()
    non_draft["actions"][0]["createStatus"] = "ENABLED"
    with pytest.raises(ValueError, match="must remain DRAFT"):
        _planner().build_program_definition_write_plan(
            _normalized_rows(), non_draft, course_snapshots=_course_snapshots()
        )


def test_course_credit_is_reasserted_when_write_plan_is_built():
    rows = _normalized_rows()
    course = next(row for row in rows if row["logicalGroup"] == "COURSE")
    course["payload"] = dict(course["payload"], creditSnapshot=Decimal("2"))
    with pytest.raises(ValueError, match="Course credit changed after preflight"):
        _planner().build_program_definition_write_plan(
            rows,
            _create_preflight(),
            course_snapshots=_course_snapshots(credit="3"),
        )


def test_write_plan_does_not_call_current_interactive_version_authority_or_any_writer():
    source = inspect.getsource(_planner())
    assert "create_new_version" in source  # documentation explicitly forbids this path
    assert "academic_affairs_program_authority_service" not in source
    assert "get_sessionmaker" not in source
    assert "session()" not in source
    assert "db.add" not in source
    assert "db.flush" not in source
    assert "db.commit" not in source
    assert "AaProgram(" not in source
    assert "AaProgramCourse(" not in source
