"""Query-construction regression: filters apply to count and page within teacher scope."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.dialects import mysql


@pytest.mark.parametrize("filtered_total", [0, 17])
def test_task_list_term_and_literal_keyword_filter_both_queries(filtered_total):
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    from app.modules.academic_affairs.services import academic_affairs_teacher_relation_authority as authority
    statements = []

    class QueryCapture:
        def scalar(self, statement):
            statements.append(statement)
            return filtered_total

        def scalars(self, statement):
            statements.append(statement)
            return SimpleNamespace(all=lambda: [])

    @contextmanager
    def session():
        yield QueryCapture()

    with patch.object(service, "session", session), patch.object(service, "_tid", lambda: 123), \
            patch.object(authority, "relation_scope", return_value={"taskIds": {17}}) as formal_scope:
        assert service.list_all_tasks({}, term_id=456, keyword="50%_", mine=True,
                                      page=2, page_size=10) == ([], filtered_total)
        formal_scope.assert_called_once()
        assert formal_scope.call_args.kwargs == {"term_id": 456}
    assert len(statements) == 2
    for statement in statements:
        compiled = statement.compile(dialect=mysql.dialect())
        sql, values = str(compiled), list(compiled.params.values())
        assert "t_aa_teaching_task_batch.term_id" in sql and 456 in values
        assert "t_aa_teaching_task_batch.tenant_id" in sql and 123 in values
        assert "t_aa_teaching_task_batch.is_deleted IS false" in sql
        assert "t_aa_teaching_task.id IN" in sql
        assert [17] in values
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


def test_task_search_matches_class_and_teacher_keys_before_paging_without_foreign_class_names(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, AaTeachingTaskBatch, AaTeachingTask, SchoolClass
    tid = 1000000000000000001
    with get_sessionmaker()() as db:
        term = AaTerm(tenant_id=tid, year_code='SEARCH-2026', term_no=1)
        own = SchoolClass(tenant_id=tid, major_id=1, class_name='验收50%_行政班', grade='2026')
        foreign = SchoolClass(tenant_id=tid+1, major_id=1, class_name='外校专属班', grade='2026')
        db.add_all([term, own, foreign]); db.flush()
        batch = AaTeachingTaskBatch(tenant_id=tid, term_id=term.id, batch_name='搜索验收')
        db.add(batch); db.flush()
        tasks = [AaTeachingTask(tenant_id=tid, batch_id=batch.id, course_id=1,
            course_name='实践课程', class_id=own.id, teacher_key=f'precise_teacher_{index}',
            teaching_class_name=f'独立授课组{index}', teaching_class_code=f'GROUP-{index}', status='READY') for index in range(2)]
        db.add_all(tasks)
        db.add(AaTeachingTask(tenant_id=tid+1, batch_id=batch.id, course_id=1, course_name='验收50%_行政班', status='READY'))
        db.add(AaTeachingTask(tenant_id=tid, batch_id=batch.id, course_id=1, course_name='普通课程', class_id=foreign.id, status='READY'))
        db.commit()
        term_id, batch_id, expected_id = term.id, batch.id, str(tasks[1].id)
    from tests.support_task_review_identity import task_reader_headers
    headers = task_reader_headers()
    base = '/api/v1/academic-affairs'
    for endpoint in [f'{base}/teaching-tasks', f'{base}/teaching-task-batches/{batch_id}/tasks']:
        response = client.get(endpoint, headers=headers, params={'termId': term_id, 'keyword': '50%_', 'page': 2, 'pageSize': 1}).json()
        assert response['code'] == 0, response
        assert response['data']['total'] == 2
        assert response['data']['items'][0]['taskId'] == expected_id
        for keyword in ['GROUP-1', '独立授课组1', 'precise_teacher_1']:
            data = client.get(endpoint, headers=headers, params={'termId': term_id, 'keyword': keyword}).json()['data']
            assert data['total'] == 1 and data['items'][0]['taskId'] == expected_id
        data = client.get(endpoint, headers=headers, params={'termId': term_id, 'keyword': '外校专属班'}).json()['data']
        assert data['total'] == 0
