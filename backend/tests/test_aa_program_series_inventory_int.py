"""INT Program stable-series dirty-data inventory contracts."""
from __future__ import annotations

import inspect

from sqlalchemy.dialects import mysql


def _service():
    from app.modules.academic_affairs.services import academic_affairs_program_series_inventory_service as service
    return service


def test_program_series_inventory_query_is_single_tenant_scoped_and_binding_free():
    service = _service()
    statement = service._program_series_inventory_statement(1000000000000000001)
    sql = str(statement.compile(
        dialect=mysql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))

    assert "FROM t_aa_program" in sql
    assert "t_aa_program.tenant_id = 1000000000000000001" in sql
    assert "t_aa_program.is_deleted IS false" in sql
    assert "t_aa_program_binding" not in sql
    assert "t_aa_program_course" not in sql


def test_linear_series_are_proven_without_treating_major_grade_version_as_identity():
    service = _service()
    report = service._build_inventory([
        (1, 10, "2026", 1, None, "ENABLED"),
        (2, 10, "2026", 2, 1, "DRAFT"),
        (3, 10, "2026", 1, None, "ENABLED"),
        (4, 10, "2026", 2, 3, "DRAFT"),
    ])

    assert report["totalPrograms"] == 4
    assert report["rootProgramCount"] == 2
    assert report["provenSeriesCount"] == 2
    assert report["provenProgramCount"] == 4
    assert report["unresolvedProgramCount"] == 0
    assert report["blockerCounts"] == {}
    assert report["ambiguousNaturalIdentityGroupCount"] == 2
    assert report["naturalIdentityPolicy"] == "MAJOR_GRADE_VERSION_NOT_IDENTITY"
    assert report["bindingIdentityPolicy"] == "FORBIDDEN"
    assert report["seriesKeyBackfill"] == "PROVABLE_PREV_VERSION_ROOT_ONLY"
    assert report["migrationPreflightSafe"] is True


def test_inventory_fail_closed_on_missing_fork_cycle_drift_gap_and_unproven_baseline():
    service = _service()
    report = service._build_inventory([
        (10, 10, "2026", 2, 999, "ENABLED"),  # missing predecessor
        (20, 20, "2026", 1, None, "ENABLED"),
        (21, 20, "2026", 2, 20, "ENABLED"),
        (22, 20, "2026", 2, 20, "DRAFT"),     # fork
        (30, 30, "2026", 1, 31, "ENABLED"),
        (31, 30, "2026", 2, 30, "ENABLED"),   # cycle
        (40, 40, "2026", 1, None, "ENABLED"),
        (41, 41, "2026", 2, 40, "DRAFT"),     # major drift
        (50, 50, "2026", 1, None, "ENABLED"),
        (51, 50, "2027", 2, 50, "DRAFT"),     # grade drift
        (60, 60, "2026", 1, None, "ENABLED"),
        (61, 60, "2026", 3, 60, "DRAFT"),     # version gap
        (70, 70, "2026", 3, None, "ENABLED"), # v3-only baseline
    ], sample_limit=3)

    blockers = report["blockerCounts"]
    assert blockers["PREDECESSOR_MISSING"] == 1
    assert blockers["PREDECESSOR_FORK"] == 1
    assert blockers["VERSION_CYCLE"] >= 1
    assert blockers["MAJOR_ID_DRIFT"] == 1
    assert blockers["GRADE_YEAR_DRIFT"] == 1
    assert blockers["VERSION_SEQUENCE_INVALID"] >= 1
    assert blockers["BASELINE_VERSION_WITHOUT_HISTORY"] == 1
    assert report["unresolvedProgramCount"] > 0
    assert report["migrationPreflightSafe"] is False
    assert len(report["blockerProgramSamples"]["PREDECESSOR_FORK"]) <= 3


class _Rows:
    def __init__(self, values):
        self._values = list(values)

    def all(self):
        return list(self._values)


class _Db:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, statement):
        self.calls.append(statement)
        return _Rows(self.rows)


def test_inventory_executes_exactly_one_read_query_and_never_writes():
    service = _service()
    db = _Db([
        (1, 10, "2026", 1, None, "ENABLED"),
        (2, 10, "2026", 2, 1, "DRAFT"),
    ])

    report = service.inventory_legacy_program_series(
        db,
        tenant_id=1000000000000000001,
    )
    assert len(db.calls) == 1
    assert report["migrationPreflightSafe"] is True

    source = inspect.getsource(service)
    assert "AaProgramBinding" not in source
    assert ".commit(" not in source
    assert "db.add(" not in source
    assert "db.flush(" not in source
    assert "_tid(" not in source


def test_inventory_rejects_ambient_or_unbounded_inputs():
    service = _service()
    for tenant_id in (None, "", 0, -1, "not-a-tenant"):
        try:
            service._program_series_inventory_statement(tenant_id)
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
