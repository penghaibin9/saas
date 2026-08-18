"""INT Program stable-series adapter/canonical-classifier contracts."""
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


def test_linear_series_delegate_to_canonical_classifier_and_keep_natural_identity_non_authoritative():
    service = _service()
    report = service._build_inventory([
        (1, 1, 10, "2026", 1, None, "ENABLED"),
        (2, 1, 10, "2026", 2, 1, "DRAFT"),
        (3, 1, 10, "2026", 1, None, "ENABLED"),
        (4, 1, 10, "2026", 2, 3, "DRAFT"),
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
    assert report["seriesKeyBackfill"] == "CANONICAL_PROPOSED_BACKFILL"
    assert report["canonicalClassifier"] == "inventory_program_series"
    assert report["migrationPreflightSafe"] is True
    assert report["proposedBackfill"] == [
        {"programId": 1, "tenantId": 1, "version": 1, "rootProgramId": 1, "seriesKey": "LEGACY-1"},
        {"programId": 2, "tenantId": 1, "version": 2, "rootProgramId": 1, "seriesKey": "LEGACY-1"},
        {"programId": 3, "tenantId": 1, "version": 1, "rootProgramId": 3, "seriesKey": "LEGACY-3"},
        {"programId": 4, "tenantId": 1, "version": 2, "rootProgramId": 3, "seriesKey": "LEGACY-3"},
    ]


def test_inventory_fail_closed_via_canonical_blockers_and_never_returns_partial_backfill():
    service = _service()
    report = service._build_inventory([
        (10, 1, 10, "2026", 2, 999, "ENABLED"),  # missing predecessor
        (20, 1, 20, "2026", 1, None, "ENABLED"),
        (21, 1, 20, "2026", 2, 20, "ENABLED"),
        (22, 1, 20, "2026", 2, 20, "DRAFT"),     # fork
        (30, 1, 30, "2026", 1, 31, "ENABLED"),
        (31, 1, 30, "2026", 2, 30, "ENABLED"),   # cycle
        (40, 1, 40, "2026", 1, None, "ENABLED"),
        (41, 1, 41, "2026", 2, 40, "DRAFT"),     # major drift
        (50, 1, 50, "2026", 1, None, "ENABLED"),
        (51, 1, 50, "2027", 2, 50, "DRAFT"),     # grade drift
        (60, 1, 60, "2026", 1, None, "ENABLED"),
        (61, 1, 60, "2026", 3, 60, "DRAFT"),     # version gap
        (70, 1, 70, "2026", 3, None, "ENABLED"), # v3-only baseline
    ], sample_limit=3)

    blockers = report["blockerCounts"]
    assert blockers["PROGRAM_PARENT_MISSING"] == 1
    assert blockers["PROGRAM_VERSION_FORK"] == 1
    assert blockers["PROGRAM_VERSION_CYCLE"] >= 1
    assert blockers["PROGRAM_SERIES_SCOPE_DRIFT"] == 2
    assert blockers["PROGRAM_VERSION_NOT_DIRECT_SUCCESSOR"] >= 2
    assert blockers["PROGRAM_ROOT_NOT_V1"] == 1
    assert report["unresolvedProgramCount"] > 0
    assert report["migrationPreflightSafe"] is False
    assert report["proposedBackfill"] == []
    assert len(report["blockerProgramSamples"]["PROGRAM_VERSION_FORK"]) <= 3


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


def test_inventory_executes_exactly_one_read_query_and_delegates_graph_truth():
    service = _service()
    db = _Db([
        (1, 1000000000000000001, 10, "2026", 1, None, "ENABLED"),
        (2, 1000000000000000001, 10, "2026", 2, 1, "DRAFT"),
    ])

    report = service.inventory_legacy_program_series(
        db,
        tenant_id=1000000000000000001,
    )
    assert len(db.calls) == 1
    assert report["migrationPreflightSafe"] is True
    assert [item["seriesKey"] for item in report["proposedBackfill"]] == ["LEGACY-1", "LEGACY-1"]

    source = inspect.getsource(service)
    assert "inventory_program_series(rows)" in source
    assert "VERSION_CYCLE" not in source
    assert "PREDECESSOR_FORK" not in source
    assert "successors" not in source
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
