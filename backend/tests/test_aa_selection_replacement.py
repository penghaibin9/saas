"""One-for-one reselection behavior; isolated collaborators, no database access."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_selection_final_service as service


def cancelled(record_id, replacement=None):
    return SimpleNamespace(id=record_id, status="COURSE_CANCELLED", replacement_record_id=replacement)


def test_only_unused_cancellations_supply_a_single_replacement_slot():
    first, second = cancelled(1), cancelled(2)
    records = [second, cancelled(3, 30), SimpleNamespace(id=4, status="DROPPED"), first]
    assert [row.id for row in service._pending_reselection_records(records)] == [1, 2]
    first.replacement_record_id = 20
    assert [row.id for row in service._pending_reselection_records(records)] == [2]
    second.replacement_record_id = 21
    assert service._pending_reselection_records(records) == []


def command_setup(monkeypatch, records, *, capacity=1):
    student = SimpleNamespace(id=7, student_no="test-student", real_name="虚构学生")
    course = SimpleNamespace(id=20, batch_id=8, course_id=9, status="OPEN", credit=2, course_name="替代课程", teaching_task_id=None)
    batch = SimpleNamespace(id=8, status="CLOSED")
    queries = [MagicMock() for _ in range(5)]
    for query in queries:
        query.filter.return_value = query
        query.with_for_update.return_value = query
    queries[0].first.return_value = course
    queries[1].first.return_value = batch
    queries[2].all.return_value = records
    queries[3].update.return_value = capacity
    queries[4].first.return_value = None
    db = MagicMock()
    db.query.side_effect = queries
    added = []
    db.add.side_effect = added.append
    db.flush.side_effect = lambda: [setattr(row, "id", 100) for row in added]

    @contextmanager
    def session():
        yield db

    monkeypatch.setattr(service._base._core, "session", session)
    monkeypatch.setattr(service._base._core, "_tid", lambda: 1)
    monkeypatch.setattr(service._base, "_load_student", lambda _: student)
    monkeypatch.setattr(service, "_selection_academic_identity", lambda *_, **__: (student, SimpleNamespace(id=3, version_no=1)))
    monkeypatch.setattr(service._base, "_guard_batch_writable", lambda *_: None)
    monkeypatch.setattr(service._base, "_active_round", lambda *_: None)
    monkeypatch.setattr(service, "_configured_round_batch_ids", lambda *_: set())
    monkeypatch.setattr(service.selection_trace, "attach_selection_trace", lambda exc, **_: exc)

    def validate(*_, allow_reselect_closed=False):
        if not allow_reselect_closed:
            raise AppException("DATA_CONFLICT", "本批次没有待补选资格")

    monkeypatch.setattr(service._base, "_validate_enroll", validate)
    audit = MagicMock()
    monkeypatch.setattr(service._base._core, "_audit", audit)
    monkeypatch.setattr(service._base._core, "_record_dto", lambda row: {"recordId": str(row.id), "status": row.status})
    return db, queries, audit


def test_success_links_one_source_before_audit_and_commit(monkeypatch):
    first, second = cancelled(1), cancelled(2)
    db, queries, audit = command_setup(monkeypatch, [second, first])
    audit.side_effect = lambda *_: (first.replacement_record_id == 100) or pytest.fail("关联须先于同事务审计")
    result = service._student_enroll_guarded({}, SimpleNamespace(selectionCourseId="20", isReselect=False))
    assert result == {"recordId": "100", "status": "SELECTED"}
    assert first.replacement_record_id == 100
    assert second.replacement_record_id is None
    assert queries[2].with_for_update.call_count == 1  # Current read after the batch lock.
    assert db.commit.call_count == 1
    assert "replacesRecordId=1" in audit.call_args.args[-1]


def test_used_qualification_rejects_even_when_client_claims_reselection(monkeypatch):
    source = cancelled(1, 90)
    db, queries, _ = command_setup(monkeypatch, [source])
    with pytest.raises(AppException):
        service._student_enroll_guarded({}, SimpleNamespace(selectionCourseId="20", isReselect=True))
    assert source.replacement_record_id == 90
    queries[3].update.assert_not_called()
    db.commit.assert_not_called()


def test_full_course_does_not_consume_reselection(monkeypatch):
    source = cancelled(1)
    db, _, audit = command_setup(monkeypatch, [source], capacity=0)
    with pytest.raises(AppException):
        service._student_enroll_guarded({}, SimpleNamespace(selectionCourseId="20"))
    assert source.replacement_record_id is None
    db.commit.assert_not_called()
    audit.assert_not_called()


def test_closed_batch_reselection_is_not_blocked_by_an_old_drop_only_round(monkeypatch):
    source = cancelled(1)
    command_setup(monkeypatch, [source])
    monkeypatch.setattr(service._base, "_active_round", lambda *_: SimpleNamespace(id=5, mode="LOTTERY", allow_enroll=False))
    result = service._student_enroll_guarded({}, SimpleNamespace(selectionCourseId="20"))
    assert result["status"] == "SELECTED"
    assert source.replacement_record_id == 100


@pytest.mark.parametrize("replacement_student,expected_name", [(7, "替代课程"), (8, None)])
def test_reselection_report_reads_only_the_linked_students_course(monkeypatch, replacement_student, expected_name):
    from app.modules.academic_affairs.services import academic_affairs_selection_read_core_service as read
    source = SimpleNamespace(id=1, student_id=7, replacement_record_id=100)
    target = SimpleNamespace(id=100, student_id=replacement_student, course_name="替代课程")
    queries = [MagicMock(), MagicMock()]
    for query in queries:
        for method in ("filter", "order_by", "offset", "limit"):
            getattr(query, method).return_value = query
    queries[0].count.return_value = 1; queries[0].all.return_value = [source]
    queries[1].all.return_value = [target]
    db = MagicMock(); db.query.side_effect = queries
    @contextmanager
    def session():
        yield db
    monkeypatch.setattr(read._core, "session", session)
    monkeypatch.setattr(read._core, "_ctx", lambda *_: SimpleNamespace(scope_type="TENANT_ALL"))
    monkeypatch.setattr(read._core, "_tid", lambda: 1)
    monkeypatch.setattr(read._core, "_get_batch", lambda *_: SimpleNamespace(id=8,status="CLOSED"))
    monkeypatch.setattr(read._core, "_derive_keys", lambda *_: set())
    monkeypatch.setattr(read._core, "_record_dto", lambda _: {"replacementRecordId":"100"})
    monkeypatch.setattr(read, "_scope_values", lambda *_: None)
    monkeypatch.setattr(read, "_require_batch_visible", lambda *_: None)
    courses = MagicMock()
    for method in ("filter", "order_by", "offset", "limit"):
        getattr(courses, method).return_value = courses
    courses.count.return_value = 0; courses.all.return_value = []
    from sqlalchemy import select
    from app.models import AaSelectionCourse
    courses.with_entities.return_value = select(AaSelectionCourse.id).where(AaSelectionCourse.id == -1)
    monkeypatch.setattr(read, "_course_query", lambda *_, **__: courses)
    report = read.reselect_guide({},8,cancelled_page=3,available_page=2)
    assert report["affectedRecords"]["items"][0]["replacementCourseName"] == expected_name
    assert report["cancelledPagination"]["page"] == 3
    assert report["availablePagination"]["page"] == 2
    assert [call.args[0] for call in courses.offset.call_args_list] == [40,20]
    assert [call.args[0] for call in courses.limit.call_args_list] == [20,20]


def test_replacement_column_and_unique_constraint_compile_for_mysql():
    from sqlalchemy.dialects import mysql
    from sqlalchemy.schema import CreateTable
    from app.models import AaSelectionRecord
    table = AaSelectionRecord.__table__
    assert table.c.replacement_record_id.nullable
    ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
    assert "replacement_record_id BIGINT" in ddl
    assert "UNIQUE (tenant_id, replacement_record_id)" in ddl


def test_migration_adds_nullable_link_without_rewriting_history(monkeypatch):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20261029_aa_selection_replacement.py"
    spec = importlib.util.spec_from_file_location("selection_replacement_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    operations = MagicMock()
    monkeypatch.setattr(migration, "op", operations)
    migration.upgrade()
    table, column = operations.add_column.call_args.args
    assert table == "t_aa_selection_record"
    assert column.name == "replacement_record_id" and column.nullable
    assert operations.create_unique_constraint.call_args.args == (
        "uk_aa_selection_replacement", table, ["tenant_id", "replacement_record_id"],
    )
    operations.execute.assert_not_called()
    with pytest.raises(RuntimeError):
        migration.downgrade()
