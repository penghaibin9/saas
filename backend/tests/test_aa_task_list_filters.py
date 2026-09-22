"""Query-construction regression: filters apply to count and page within teacher scope."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.dialects import mysql


def test_task_list_term_and_literal_keyword_filter_both_queries():
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    statements = []

    class QueryCapture:
        def scalar(self, statement):
            statements.append(statement)
            return 0

        def scalars(self, statement):
            statements.append(statement)
            return SimpleNamespace(all=lambda: [])

    @contextmanager
    def session():
        yield QueryCapture()

    with patch.object(service, "session", session), patch.object(service, "_tid", lambda: 123), \
            patch.object(service._core, "_user_keys", lambda user: {"teacher-A"}):
        assert service.list_all_tasks({}, term_id=456, keyword="50%_", mine=True,
                                      page=2, page_size=10) == ([], 0)
    assert len(statements) == 2
    for statement in statements:
        compiled = statement.compile(dialect=mysql.dialect())
        sql, values = str(compiled), list(compiled.params.values())
        assert "t_aa_teaching_task_batch.term_id" in sql and 456 in values
        assert "t_aa_teaching_task_batch.tenant_id" in sql and 123 in values
        assert "t_aa_teaching_task_batch.is_deleted IS false" in sql
        assert "t_aa_teaching_task.teacher_key IN" in sql
        assert ["teacher-A"] in values
        assert "50/%/_" in values  # percent/underscore must be literal, not wildcard
        assert "course_name LIKE" in sql and "teacher_name LIKE" in sql
    assert "LIMIT" not in str(statements[0])
    assert statements[1]._limit_clause.value == 10
    assert statements[1]._offset_clause.value == 10


def test_task_list_projects_batch_status_without_n_plus_one():
    import inspect
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    source = inspect.getsource(service.list_all_tasks)
    assert 'batch_ids = sorted({int(task.batch_id) for task in rows if task.batch_id})' in source
    assert 'AaTeachingTaskBatch.id.in_(batch_ids)' in source
    assert 'item["batchStatus"] = batch_status.get' in source
