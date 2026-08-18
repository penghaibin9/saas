"""INT contracts for ProgramCourse formation provenance inventory."""
from __future__ import annotations

import inspect

from sqlalchemy.dialects import mysql


def _service():
    from app.modules.academic_affairs.services import academic_affairs_program_course_formation_provenance_inventory_service as service
    return service


def test_inventory_is_one_explicit_tenant_scoped_programcourse_query_without_task_or_student_join():
    service = _service()
    statement = service._program_course_inventory_statement(1000000000000000001)
    sql = str(statement.compile(
        dialect=mysql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))
    assert "FROM t_aa_program_course" in sql
    assert "t_aa_program_course.tenant_id = 1000000000000000001" in sql
    assert "t_aa_program_course.is_deleted IS false" in sql
    assert "t_aa_teaching_task" not in sql
    assert "t_student_profile" not in sql
    assert "t_aa_program_binding" not in sql


def test_legacy_rows_without_explicit_provenance_are_all_blocked_without_admin_default():
    report = _service()._build_inventory([
        (11, 101, 1001, 1, "公共基础"),
        (12, 101, 1002, 2, "专业核心"),
    ])
    assert report["totalProgramCourses"] == 2
    assert report["explicitProvenanceCount"] == 0
    assert report["unresolvedProgramCourseCount"] == 2
    assert report["blockerCounts"] == {"FORMATION_PROVENANCE_MISSING": 2}
    assert report["programCourseFormationBackfill"] == "REQUIRES_EXPLICIT_PROVENANCE"
    assert report["migrationPreflightSafe"] is False
    assert report["formationModeCounts"]["ADMIN_FIXED"] == 0
    assert report["inferencePolicy"] == {
        "courseNameOrNature": "FORBIDDEN",
        "teachingTaskMajority": "FORBIDDEN",
        "adminFixedDefault": "FORBIDDEN",
    }


def test_explicit_external_provenance_can_prove_each_programcourse_without_task_inference():
    report = _service()._build_inventory(
        [
            (11, 101, 1001, 1, "公共基础"),
            (12, 101, 1002, 2, "专业核心"),
        ],
        provenance_by_program_course_id={
            11: {
                "formationMode": "admin_fixed",
                "sourceSystem": "LEGACY_SIS",
                "sourceRecordId": "pc-11",
                "evidenceRef": "migration-pack-2026#pc-11",
            },
            "12": {
                "formationMode": "selectable",
                "sourceSystem": "LEGACY_SIS",
                "sourceRecordId": "pc-12",
                "evidenceRef": "migration-pack-2026#pc-12",
            },
        },
    )
    assert report["explicitProvenanceCount"] == 2
    assert report["unresolvedProgramCourseCount"] == 0
    assert report["formationModeCounts"]["ADMIN_FIXED"] == 1
    assert report["formationModeCounts"]["SELECTABLE"] == 1
    assert report["provenanceSourceCounts"] == {"LEGACY_SIS": 2}
    assert report["blockerCounts"] == {}
    assert report["programCourseFormationBackfill"] == "EXPLICIT_PROVENANCE_PROVEN"
    assert report["migrationPreflightSafe"] is True


def test_invalid_incomplete_and_orphan_provenance_fail_closed():
    service = _service()
    report = service._build_inventory(
        [(11, 101, 1001, 1, "核心"), (12, 101, 1002, 2, "选修")],
        provenance_by_program_course_id={
            11: {
                "formationMode": "NOT_A_MODE",
                "sourceSystem": "LEGACY_SIS",
                "sourceRecordId": "pc-11",
                "evidenceRef": "ref-11",
            },
            12: {
                "formationMode": "SELECTABLE",
                "sourceSystem": "LEGACY_SIS",
                "sourceRecordId": "",
                "evidenceRef": "ref-12",
            },
            999: {
                "formationMode": "ADMIN_FIXED",
                "sourceSystem": "LEGACY_SIS",
                "sourceRecordId": "pc-999",
                "evidenceRef": "ref-999",
            },
        },
        sample_limit=1,
    )
    assert report["migrationPreflightSafe"] is False
    assert report["blockerCounts"] == {
        "FORMATION_PROVENANCE_INCOMPLETE": 1,
        "FORMATION_PROVENANCE_MODE_INVALID": 1,
        "ORPHAN_FORMATION_PROVENANCE": 1,
    }
    assert report["blockerProgramCourseSamples"] == {
        "FORMATION_PROVENANCE_INCOMPLETE": ["12"],
        "FORMATION_PROVENANCE_MODE_INVALID": ["11"],
        "ORPHAN_FORMATION_PROVENANCE": ["999"],
    }


def test_empty_programcourse_table_needs_no_historical_backfill():
    report = _service()._build_inventory([])
    assert report["totalProgramCourses"] == 0
    assert report["explicitProvenanceCount"] == 0
    assert report["unresolvedProgramCourseCount"] == 0
    assert report["programCourseFormationBackfill"] == "EXPLICIT_PROVENANCE_PROVEN"
    assert report["migrationPreflightSafe"] is True


class _Rows:
    def __init__(self, values):
        self._values = list(values)

    def all(self):
        return list(self._values)


class _Db:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, statement):
        self.calls.append(statement)
        return _Rows(self.rows)


def test_inventory_executes_exactly_one_read_and_never_writes_or_uses_ambient_tenant():
    service = _service()
    db = _Db([(11, 101, 1001, 1, "核心")])
    report = service.inventory_program_course_formation_provenance(
        db,
        tenant_id=1000000000000000001,
    )
    assert len(db.calls) == 1
    assert report["migrationPreflightSafe"] is False

    source = inspect.getsource(service)
    assert "AaTeachingTask" not in source
    assert "StudentProfile" not in source
    assert "course_name" not in source.lower()
    assert "course.nature" not in source.lower()
    assert "_tid(" not in source
    assert "db.add(" not in source
    assert "db.flush(" not in source
    assert ".commit(" not in source


def test_inventory_rejects_invalid_scope_evidence_and_sample_inputs():
    service = _service()
    for tenant_id in (None, "", 0, -1, "bad"):
        try:
            service._program_course_inventory_statement(tenant_id)
        except ValueError:
            pass
        else:
            raise AssertionError(f"tenant_id {tenant_id!r} must fail closed")

    for sample_limit in (0, 101, "bad"):
        try:
            service._build_inventory([], sample_limit=sample_limit)
        except ValueError:
            pass
        else:
            raise AssertionError(f"sample_limit {sample_limit!r} must fail closed")
