"""Unit regressions for the shared teacher-service contract (no database acceptance)."""
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.modules.graduation.services import graduation_mobile_teacher_service as service
from app.modules.graduation.services import graduation_identity as identity


class PendingContractTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.db.scalars.return_value.all.return_value = []

        @contextmanager
        def session():
            yield self.db

        for target, name, value in (
            (service, 'session', session),
            (service, '_tid', lambda: 17),
            (service, 'accessible_student_ids', lambda db, tid: [1]),
            (identity, 'current_user_mentor', lambda db: SimpleNamespace(id=9)),
        ):
            p = patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_accepts_router_scoped_user(self):
        self.assertEqual(service.judge_pending({'graduationBatchId': '5'}), [])

    def test_context_only_caller_remains_supported(self):
        with patch.object(service, 'get_current_user_ctx', return_value={}):
            self.assertEqual(service.judge_pending(), [])

    def test_foreign_tenant_group_is_not_exposed(self):
        self.db.scalars.return_value.all.return_value = [SimpleNamespace(id=1, defense_group_id=3)]
        self.db.get.return_value = service.GraduationDefenseGroup(
            id=3, tenant_id=18, published=True, is_deleted=False,
        )
        with patch('app.core.tenant_scoped.current_tenant_id_int', return_value=17):
            with patch.object(identity, 'judge_panel_seats') as seats:
                self.assertEqual(service.judge_pending({}), [])
                seats.assert_not_called()


if __name__ == '__main__':
    unittest.main()
