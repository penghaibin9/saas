from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.dialects import mysql


def test_composition_filters_apply_before_count_and_page():
    from app.modules.academic_affairs.services import academic_affairs_task_service as service
    from app.modules.academic_affairs.services import academic_affairs_teacher_relation_authority as authority
    statements = []

    class Capture:
        def scalar(self, statement):
            statements.append(statement)
            return 31

        def scalars(self, statement):
            statements.append(statement)
            return SimpleNamespace(all=lambda: [])

    @contextmanager
    def session():
        yield Capture()

    with patch.object(service, 'session', session), patch.object(service, '_tid', lambda: 123), \
            patch.object(authority, 'relation_scope', return_value={'taskIds': {17}}):
        assert service.list_all_tasks({}, mine=True, merged=True, exclude_merged=True,
                                      page=2, page_size=10) == ([], 31)
    for statement in statements:
        sql = str(statement.compile(dialect=mysql.dialect()))
        assert 't_aa_teaching_task.is_merged IS true' in sql
        assert 't_aa_teaching_task.status !=' in sql
        assert 't_aa_teaching_task.tenant_id =' in sql
        assert 't_aa_teaching_task.id IN' in sql
    assert statements[1]._offset_clause.value == 10
    assert statements[1]._limit_clause.value == 10


def test_review_records_are_bounded_tenant_and_batch_scoped_without_raw_details():
    from app.modules.academic_affairs.services import academic_affairs_task_service as service
    statements = []

    class Capture:
        def scalars(self, statement):
            statements.append(statement)
            return SimpleNamespace(all=lambda: [
                SimpleNamespace(id=1, action='ACADEMIC_APPROVE', operator='教务责任人', detail='READY x23', occurred_at=datetime(2026, 10, 27)),
                SimpleNamespace(id=2, action='ACADEMIC_RETURN', operator='教务责任人', detail='请核对课程安排', occurred_at=datetime(2026, 10, 26)),
            ])

    with patch.object(service, '_tid', lambda: 123):
        records = service._batch_review_records(Capture(), 456)
    compiled = statements[0].compile(dialect=mysql.dialect())
    assert 123 in compiled.params.values() and 456 in compiled.params.values()
    assert 'AA_TASK_BATCH' in compiled.params.values()
    assert statements[0]._limit_clause.value == 30
    assert records[0]['action'] == '校教务终审通过' and records[0]['reason'] == ''
    assert records[0]['at'].endswith('Z')
    assert records[1]['reason'] == '请核对课程安排'


def test_review_records_never_include_another_tenant_or_batch(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail
    from app.modules.academic_affairs.services import academic_affairs_task_service as service
    with get_sessionmaker()() as db:
        for tenant, batch, detail in [(123, 456, '本批次退回原因'), (124, 456, '其他租户'), (123, 457, '其他批次')]:
            db.add(AffairsAuditTrail(tenant_id=tenant, biz_type='AA_TASK_BATCH', biz_id=batch,
                                    action='ACADEMIC_RETURN', detail=detail, occurred_at=datetime(2026, 10, 27)))
        db.commit()
        with patch.object(service, '_tid', lambda: 123):
            rows = service._batch_review_records(db, 456)
    assert [row['reason'] for row in rows] == ['本批次退回原因']


def test_composition_pagination_reads_only_matching_tasks_in_mysql(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTaskBatch, AaTeachingTask, AaTerm
    from app.modules.academic_affairs.services import academic_affairs_task_service as service
    tenant = 1000000000000000001
    with get_sessionmaker()() as db:
        term = AaTerm(tenant_id=tenant, year_code='SEVEN-2026', term_no=1)
        db.add(term); db.flush()
        batch = AaTeachingTaskBatch(tenant_id=tenant, term_id=term.id, batch_name='七页分页验证')
        db.add(batch); db.flush()
        for index in range(3):
            db.add(AaTeachingTask(tenant_id=tenant, batch_id=batch.id, course_id=1,
                                 course_name='合班课程', status='PENDING_ASSIGN', is_merged=True))
        db.add(AaTeachingTask(tenant_id=tenant, batch_id=batch.id, course_id=1,
                             course_name='已并入任务', status='MERGED', is_merged=False))
        db.add(AaTeachingTask(tenant_id=tenant + 1, batch_id=batch.id, course_id=1,
                             course_name='其他租户', status='PENDING_ASSIGN', is_merged=True))
        db.commit()
        batch_id = batch.id
    with patch.object(service, '_tid', lambda: tenant), \
            patch.object(service, '_scope', return_value=service.TaskManageScope(all=True)):
        items, total = service.list_all_tasks({}, batch_id=batch_id, merged=True, page=2, page_size=2)
        assert total == 3 and len(items) == 1
        assert items[0]['isMerged'] is True
        assert items[0]['batchName'] == '七页分页验证'
        assert items[0]['courseName'] == '合班课程'
        items, total = service.list_all_tasks({}, batch_id=batch_id, exclude_merged=True)
        assert total == 3 and all(row['status'] != 'MERGED' for row in items)
