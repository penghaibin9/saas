"""Exercise the real router-to-service contract without a destructive database fixture."""
import unittest
from unittest.mock import patch

from app.api.v1 import mobile
from app.core.exceptions import AppException
from app.services import _mobile_teacher_service_impl as implementation
from app.services import affairs_leave_service


class MobileLeaveQueueContractTest(unittest.TestCase):
    user = {"userId": "123", "userType": "TEACHER"}

    def test_pending_router_keeps_requested_page_and_search(self):
        rows = [{"id": "16287", "allowedActions": ["APPROVE"], "version": 0}]
        with patch.object(implementation, "db_enabled", return_value=True), patch.object(
            affairs_leave_service, "list_pending", return_value=(rows, 131)
        ) as query:
            result = mobile.teacher_affairs_leave_pending(7, 20, "2024S0001", self.user)
        query.assert_called_once_with(self.user, 7, 20, keyword="2024S0001")
        self.assertEqual(result["data"], {"list": rows, "total": 131})

    def test_followup_router_keeps_status_and_pagination(self):
        with patch.object(implementation, "db_enabled", return_value=True), patch.object(
            affairs_leave_service, "list_leaves", return_value=([], 0)
        ) as query:
            result = mobile.teacher_affairs_leave_followup(2, 10, "2024S0001", "OVERDUE", self.user)
        query.assert_called_once_with(self.user, followup_only=True, page=2, page_size=10,
                                      keyword="2024S0001", status="OVERDUE")
        self.assertEqual(result["data"], {"list": [], "total": 0})

    def test_student_cannot_use_teacher_queue(self):
        with patch.object(affairs_leave_service, "list_pending") as query, self.assertRaises(AppException):
            mobile.teacher_affairs_leave_pending(1, 20, "", {"userId": "123", "userType": "STUDENT"})
        query.assert_not_called()
