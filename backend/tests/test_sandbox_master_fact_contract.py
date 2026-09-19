"""Unit coverage for validator query/decision contract; MySQL replay is separate."""
import unittest
from unittest.mock import MagicMock
from sqlalchemy.dialects import mysql
from app.services import sandbox_school_master_seed as seed


class MasterFactContractTests(unittest.TestCase):
    def db(self, current=20000, invalid=0):
        db = MagicMock()
        db.scalar.side_effect = [20000, current, invalid, 8, 32, 384, 20000, 1280, 19999, 1]
        return db

    def test_counts_only_current_versions_and_checks_every_student(self):
        db = self.db()
        self.assertTrue(seed.validate_school_master(db, 17)['passed'])
        queries = [str(call.args[0].compile(dialect=mysql.dialect(), compile_kwargs={'literal_binds': True}))
                   for call in db.scalar.call_args_list]
        self.assertIn('valid_to IS NULL', queries[1])
        self.assertIn('tenant_id = 17', queries[1])
        self.assertIn('LEFT OUTER JOIN', queries[2])
        self.assertIn('GROUP BY', queries[2])
        self.assertIn('coalesce', queries[2])
        self.assertIn('!= 1', queries[2])

    def test_missing_and_duplicate_current_facts_cannot_cancel_out(self):
        with self.assertRaisesRegex(RuntimeError, 'studentsWithInvalidCurrentFact'):
            seed.validate_school_master(self.db(current=20000, invalid=2), 17)

    def test_extra_current_fact_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'studentAcademicFacts'):
            seed.validate_school_master(self.db(current=20001), 17)


if __name__ == '__main__':
    unittest.main()
