"""查询构造隔离检查，不连接数据库，不替代 MySQL 集成验收。"""
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.dialects import mysql
from app.modules.academic_affairs.services import academic_affairs_course_service as service


class CourseConsoleQueryTests(unittest.TestCase):
    def query(self, **filters):
        statements = []
        row = SimpleNamespace(owner_teacher_id=None)

        class Db:
            def scalar(self, statement):
                statements.append(statement)
                return 1

            def scalars(self, statement):
                statements.append(statement)
                return SimpleNamespace(all=lambda: [row])

        @contextmanager
        def session():
            yield Db()

        with patch.object(service, 'session', session), patch.object(service, '_tid', return_value=42), patch.object(service, '_resolve_teacher_names', return_value={}), patch.object(service, '_row', return_value={'version': 1, 'status': 'ENABLED'}):
            result = service.list_courses({}, page=2, page_size=20, **filters)
        sql = '\n'.join(str(s.compile(dialect=mysql.dialect(), compile_kwargs={'literal_binds': True})) for s in statements)
        return sql, result

    def test_history_query_is_scoped_and_paged_and_ignores_draft_successor(self):
        sql, (rows, total) = self.query(history='SUPERSEDED')
        self.assertIn('EXISTS', sql)
        self.assertIn('tenant_id = 42', sql)
        self.assertIn("status IN ('ENABLED', 'DISABLED')", sql)
        self.assertNotIn("'DRAFT'", sql)
        self.assertIn('version >', sql)
        self.assertIn('LIMIT 20, 20', sql)
        self.assertIn('更高正式版本', rows[0]['archiveReason'])
        self.assertEqual(total, 1)

    def test_owner_and_exam_filters_apply_before_pagination(self):
        sql, _ = self.query(owner_assigned=False, exam_mode='EXAM', togglable=True)
        self.assertIn('owner_teacher_id IS NULL', sql)
        self.assertIn("exam_mode = 'EXAM'", sql)
        self.assertIn("status IN ('ENABLED', 'DISABLED')", sql)
        self.assertIn('LIMIT 20, 20', sql)


if __name__ == '__main__':
    unittest.main()
