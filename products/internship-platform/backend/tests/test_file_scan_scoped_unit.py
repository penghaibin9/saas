"""Scoped scan recovery never consumes an unrelated shared-database job."""
import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy.dialects import mysql
from app.services import file_scan_service as scan


class ScopedScanTests(unittest.TestCase):
    def test_all_recovery_identifiers_limit_the_existing_locked_query(self):
        factory = MagicMock()
        db = factory.return_value.__enter__.return_value
        db.scalar.return_value = None
        with patch.object(scan, 'get_sessionmaker', return_value=factory):
            result = scan.process_next_scan_job(tenant_id=12, job_id=4, file_id=76)
        self.assertFalse(result['processed'])
        query = db.scalar.call_args.args[0]
        sql = str(query.compile(dialect=mysql.dialect(), compile_kwargs={'literal_binds': True}))
        for condition in ('tenant_id = 12', '.id = 4', 'file_id = 76', 'SKIP LOCKED'):
            self.assertIn(condition, sql)
        db.commit.assert_not_called()

    def test_invalid_scope_never_opens_a_database_session(self):
        with patch.object(scan, 'get_sessionmaker') as factory:
            for value in (0, -1, True, '12', 1.5):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    scan.claim_one(tenant_id=value)
            factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
