"""A-W3/INT editable TeachingTaskBatch migration preflight contracts."""
from __future__ import annotations

import inspect

import pytest
from sqlalchemy.dialects import mysql


def _service():
    from app.modules.academic_affairs.services import academic_affairs_task_batch_inventory_service as service
    return service


def test_inventory_statement_is_single_tenant_scoped_editable_batch_read():
    sql = str(
        _service().editable_batch_inventory_statement(1000000000000000001).compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "FROM t_aa_teaching_task_batch" in sql
    assert "t_aa_teaching_task_batch.tenant_id = 1000000000000000001" in sql
    assert "t_aa_teaching_task_batch.status IN ('DRAFT', 'RETURNED')" in sql
    assert "t_aa_teaching_task_batch.is_deleted IS false" in sql
    assert "ORDER BY t_aa_teaching_task_batch.term_id ASC" in sql
    assert "t_student_profile" not in sql
    assert "t_aa_teaching_class_member" not in sql


def test_editable_scope_key_is_non_null_and_stable_for_school_and_college_scopes():
    service = _service()
    assert service.canonical_editable_scope_key(202601, None) == "V1:TERM:202601:SCHOOL"
    assert service.canonical_editable_scope_key(202601, None) == service.canonical_editable_scope_key(202601, None)
    assert service.canonical_editable_scope_key(202601, 17) == "V1:TERM:202601:COLLEGE:17"
    assert service.canonical_editable_scope_key(202601, 17) != service.canonical_editable_scope_key(202601, 18)
    assert service.canonical_editable_scope_key(202601, None) != service.canonical_editable_scope_key(202601, 17)


@pytest.mark.parametrize(
    ("term_id", "college_id", "message"),
    [
        (0, None, "term_id"),
        (-1, 17, "term_id"),
        (202601, 0, "college_id"),
        (202601, -2, "college_id"),
    ],
)
def test_editable_scope_key_rejects_non_positive_identifiers(term_id, college_id, message):
    with pytest.raises(ValueError, match=message):
        _service().canonical_editable_scope_key(term_id, college_id)


class _Result:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class _Db:
    def __init__(self, rows):
        self.rows = list(rows)
        self.execute_calls = 0
        self.statement = None

    def execute(self, statement):
        self.execute_calls += 1
        self.statement = statement
        return _Result(self.rows)


def test_inventory_reports_duplicate_school_and_college_scopes_without_guessing_winner():
    db = _Db([
        (1001, 202601, None, "DRAFT"),
        (1002, 202601, None, "RETURNED"),
        (1101, 202601, 17, "DRAFT"),
        (1102, 202601, 17, "RETURNED"),
        (1103, 202601, 17, "DRAFT"),
        (1201, 202602, 18, "RETURNED"),
    ])

    result = _service().inventory_editable_batch_scope_conflicts(
        db, 1000000000000000001, sample_limit=2
    )

    assert db.execute_calls == 1
    assert result["tenantId"] == "1000000000000000001"
    assert result["scopeKeyVersion"] == "V1"
    assert result["editableBatchCount"] == 6
    assert result["conflictScopeCount"] == 2
    assert result["conflictBatchCount"] == 5
    assert result["migrationPreflightSafe"] is False

    school, college = result["conflicts"]
    assert school == {
        "termId": "202601",
        "collegeId": "",
        "scope": "SCHOOL",
        "editableScopeKey": "V1:TERM:202601:SCHOOL",
        "editableBatchCount": 2,
        "batchIds": ["1001", "1002"],
        "batchStatuses": ["DRAFT", "RETURNED"],
        "sampleTruncated": False,
    }
    assert college == {
        "termId": "202601",
        "collegeId": "17",
        "scope": "COLLEGE:17",
        "editableScopeKey": "V1:TERM:202601:COLLEGE:17",
        "editableBatchCount": 3,
        "batchIds": ["1101", "1102"],
        "batchStatuses": ["DRAFT", "RETURNED"],
        "sampleTruncated": True,
    }


def test_inventory_clean_scope_is_migration_safe():
    db = _Db([
        (2001, 202601, None, "DRAFT"),
        (2101, 202601, 17, "RETURNED"),
        (2201, 202602, 17, "DRAFT"),
    ])
    result = _service().inventory_editable_batch_scope_conflicts(db, 1000000000000000001)
    assert result["scopeKeyVersion"] == "V1"
    assert result["conflictScopeCount"] == 0
    assert result["conflictBatchCount"] == 0
    assert result["migrationPreflightSafe"] is True
    assert result["conflicts"] == []


def test_inventory_requires_explicit_positive_tenant():
    with pytest.raises(ValueError, match="positive integer"):
        _service().editable_batch_inventory_statement(0)


@pytest.mark.parametrize(("requested", "expected"), [(0, 20), (1, 1), (200, 100)])
def test_inventory_sample_limit_is_bounded(requested, expected):
    assert _service()._sample_limit(requested) == expected


def test_inventory_source_is_read_only_and_contains_no_repair_path():
    source = inspect.getsource(_service().inventory_editable_batch_scope_conflicts)
    assert "db.execute" in source
    assert "db.add" not in source
    assert "db.flush" not in source
    assert "db.commit" not in source
    assert "delete(" not in source
    assert "update(" not in source
