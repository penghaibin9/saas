"""The student projection preserves inbox identity and domain limits without a database."""
import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy.dialects import mysql
from app.services import message_center_service as messages


class StudentMessageScopeTests(unittest.TestCase):
    def test_all_four_operations_keep_tenant_receiver_context_and_source(self):
        user = {'userId': '41', 'tenantId': '12', 'userType': 'STUDENT', 'activeContextId': 'student-context'}
        manager = MagicMock()
        db = manager.__enter__.return_value
        db.scalar.return_value = None
        db.scalars.return_value.all.return_value = []
        operations = (lambda: messages.list_messages(user, source_module='internship'),
                      lambda: messages.count_messages(user, source_module='internship'),
                      lambda: messages.get_message(user, '16', source_module='internship'),
                      lambda: messages.read_message(user, '16', source_module='internship'))
        with patch.object(messages, 'session', return_value=manager), patch.object(messages, '_tid', return_value=12):
            for operation in operations:
                db.reset_mock()
                operation()
                queries = [call.args[0] for call in db.scalar.call_args_list + db.scalars.call_args_list]
                self.assertTrue(queries)
                for query in queries:
                    sql = str(query.compile(dialect=mysql.dialect(), compile_kwargs={'literal_binds': True}))
                    for condition in ('tenant_id = 12', 'receiver_user_id = 41', "'student-context'", "source_module = 'internship'"):
                        self.assertIn(condition, sql)
                db.commit.assert_not_called()
            db.reset_mock()
            messages.list_messages(user)
            sql = str(db.scalar.call_args.args[0].compile(dialect=mysql.dialect(), compile_kwargs={'literal_binds': True}))
            self.assertNotIn('source_module =', sql)


if __name__ == '__main__':
    unittest.main()
