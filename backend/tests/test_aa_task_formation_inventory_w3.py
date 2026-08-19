"""A-W3 formation dirty-data inventory contracts."""
from __future__ import annotations

import inspect

from sqlalchemy.dialects import mysql


def _service():
    from app.modules.academic_affairs.services import academic_affairs_task_formation_inventory_service as service
    return service


def test_inventory_queries_are_explicit_tenant_scoped_current_roster_and_pii_free():
    service = _service()
    statements = service._formation_inventory_statements(1000000000000000001)
    assert len(statements) == 4

    sql = [
        str(statement.compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        ))
        for statement in statements
    ]
    joined = "\n".join(sql)
    assert joined.count("tenant_id = 1000000000000000001") >= 4
    assert "t_aa_teaching_task" in sql[0]
    assert "t_aa_teaching_class" in sql[1]
    assert "t_aa_selection_course" in sql[2]
    assert "teaching_task_id IS NOT NULL" in sql[2]
    assert "LEFT OUTER JOIN t_aa_teaching_class_roster_version" in sql[3]
    assert "t_aa_teaching_class_roster_version.id = t_aa_teaching_class.current_roster_version_id" in sql[3]
    assert "t_aa_teaching_class.roster_status" in sql[3]
    assert "t_aa_teaching_class_roster_version.source_type" in sql[3]
    assert "t_student_profile" not in joined
    assert "t_aa_teaching_class_member" not in joined
    assert "t_aa_selection_record" not in joined


def test_inventory_classifies_only_proven_current_evidence_and_reports_blockers():
    service = _service()
    report = service._build_inventory(
        task_rows=[
            (1, False, 101),  # ADMIN_FIXED
            (2, False, 102),  # SELECTABLE
            (3, True, 103),   # MERGED
            (4, False, None), # unknown/no source
            (5, False, None), # unknown layered
            (6, True, 106),   # merge + selection conflict
            (7, False, 107),  # admin task with current retake roster provenance
            (8, False, None), # unproven RETAKE class type
            (9, False, None), # second missing-source row for sample bounding
        ],
        teaching_class_rows=[
            (1, "ADMIN"),
            (2, "SELECTION"),
            (3, "MERGED"),
            (5, "LAYERED"),
            (6, "MERGED"),
            (7, "ADMIN"),
            (8, "RETAKE"),
            (999, "ADMIN"),  # orphan relationship
        ],
        selection_rows=[(2,), (6,), (998,)],
        current_roster_rows=[
            (1, 1101, "LOCKED", 1101, "ADMIN_CLASS", "LOCKED"),
            (2, 1202, "LOCKED", 1202, "SELECTION_LOCK", "LOCKED"),
            (3, None, "DRAFT", None, None, None),
            (5, None, "DRAFT", None, None, None),
            (6, None, "DRAFT", None, None, None),
            (7, 1707, "LOCKED", 1707, "RETAKE", "LOCKED"),
            (8, 1808, "LOCKED", 1808, "RETAKE", "LOCKED"),
        ],
        sample_limit=1,
    )

    assert report["totalTasks"] == 9
    assert report["evidenceStatusCounts"] == {
        "PROVEN": 4,
        "UNKNOWN": 4,
        "CONFLICT": 1,
    }
    assert report["formationModeCounts"]["ADMIN_FIXED"] == 2
    assert report["formationModeCounts"]["SELECTABLE"] == 1
    assert report["formationModeCounts"]["MERGED"] == 1
    assert report["formationModeCounts"]["RETAKE"] == 0
    assert report["formationModeCounts"]["LAYERED"] == 0
    assert report["blockerCounts"] == {
        "FORMATION_SOURCE_MISSING": 2,
        "LAYERED_SOURCE_UNPROVEN": 1,
        "MERGED_FORMATION_CONFLICT": 1,
        "RETAKE_TASK_SOURCE_UNPROVEN": 1,
    }
    assert report["blockerTaskSamples"]["FORMATION_SOURCE_MISSING"] == ["4"]
    assert report["relationshipBlockerCounts"] == {
        "ORPHAN_SELECTION_TASK": 1,
        "ORPHAN_TEACHING_CLASS_TASK": 1,
    }
    assert report["migrationPreflightSafe"] is False
    assert report["programCourseFormationBackfill"] == "REQUIRES_EXPLICIT_PROVENANCE"


def test_selectable_current_admin_roster_is_reported_as_conflict():
    service = _service()
    report = service._build_inventory(
        task_rows=[(21, False, 2101)],
        teaching_class_rows=[(21, "ADMIN")],
        selection_rows=[(21,)],
        current_roster_rows=[
            (21, 2121, "LOCKED", 2121, "ADMIN_CLASS", "LOCKED"),
        ],
    )
    assert report["evidenceStatusCounts"] == {
        "PROVEN": 0,
        "UNKNOWN": 0,
        "CONFLICT": 1,
    }
    assert report["blockerCounts"] == {"SELECTABLE_CURRENT_ADMIN_ROSTER": 1}
    assert report["blockerTaskSamples"] == {"SELECTABLE_CURRENT_ADMIN_ROSTER": ["21"]}
    assert report["migrationPreflightSafe"] is False


def test_retake_current_roster_provenance_does_not_reclassify_admin_task():
    service = _service()
    report = service._build_inventory(
        task_rows=[(77, False, 701)],
        teaching_class_rows=[(77, "ADMIN")],
        selection_rows=[],
        current_roster_rows=[
            (77, 7077, "LOCKED", 7077, "RETAKE", "LOCKED"),
        ],
    )
    assert report["evidenceStatusCounts"] == {
        "PROVEN": 1,
        "UNKNOWN": 0,
        "CONFLICT": 0,
    }
    assert report["formationModeCounts"]["ADMIN_FIXED"] == 1
    assert report["formationModeCounts"]["RETAKE"] == 0
    assert report["evidenceSourceCounts"] == {"ADMIN_CLASS_WITH_RETAKE_ROSTER": 1}
    assert report["migrationPreflightSafe"] is True


def test_dangling_current_roster_pointer_blocks_migration_without_guessing_source():
    service = _service()
    report = service._build_inventory(
        task_rows=[(88, False, 801)],
        teaching_class_rows=[(88, "ADMIN")],
        selection_rows=[],
        current_roster_rows=[
            (88, 8088, "LOCKED", None, None, None),
        ],
    )
    assert report["evidenceStatusCounts"]["PROVEN"] == 1
    assert report["relationshipBlockerCounts"] == {"CURRENT_ROSTER_POINTER_DANGLING": 1}
    assert report["relationshipBlockerTaskSamples"] == {"CURRENT_ROSTER_POINTER_DANGLING": ["88"]}
    assert report["migrationPreflightSafe"] is False


class _Rows:
    def __init__(self, values):
        self._values = list(values)

    def all(self):
        return list(self._values)


class _Db:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def execute(self, statement):
        self.calls.append(statement)
        return _Rows(self._responses[len(self.calls) - 1])


def test_inventory_executes_exactly_four_read_queries_and_never_commits():
    service = _service()
    db = _Db([
        [(1, False, 101)],
        [(1, "ADMIN")],
        [],
        [(1, None, "DRAFT", None, None, None)],
    ])
    report = service.inventory_legacy_task_formation(
        db,
        tenant_id=1000000000000000001,
    )
    assert len(db.calls) == 4
    assert report["migrationPreflightSafe"] is True

    source = inspect.getsource(service)
    assert "StudentProfile" not in source
    assert "AaTeachingClassMember" not in source
    assert "AaSelectionRecord" not in source
    assert "resolve_teaching_task_roster" not in source
    assert ".commit(" not in source
    assert "db.add(" not in source
    assert "db.flush(" not in source
    assert "_tid(" not in source


def test_inventory_rejects_ambient_or_unbounded_scope_inputs():
    service = _service()
    for tenant_id in (None, "", 0, -1, "not-a-tenant"):
        try:
            service._formation_inventory_statements(tenant_id)
        except ValueError:
            pass
        else:
            raise AssertionError(f"tenant_id {tenant_id!r} must fail closed")

    for sample_limit in (0, 101, "bad"):
        try:
            service._build_inventory([], [], [], [], sample_limit=sample_limit)
        except ValueError:
            pass
        else:
            raise AssertionError(f"sample_limit {sample_limit!r} must fail closed")
