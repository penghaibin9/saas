from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmploymentTransition:
    student_id: int
    internship_id: int
    enterprise_name: str | None = None
    position_name: str | None = None


class EmploymentGateway(Protocol):
    """岗位实习只依赖这个契约，不直接依赖完整就业中心。"""

    def transition_from_internship(self, transition: EmploymentTransition) -> dict: ...

    def get_student_destination(self, student_id: int, *, internship_id=None) -> dict | None: ...

    def cohort_metrics(self, student_ids: list[int]) -> dict: ...

    def signed_month_counts(self, student_ids: list[int], months: list[str], as_of_date: str) -> dict[str, int]: ...

    def get_my_registration(self, user: dict, *, batch_id, internship_id, notification_page=1) -> dict: ...
    def read_my_notification(self, user: dict, message_id, *, batch_id, internship_id) -> dict: ...
    def submit_registration(self, user: dict, payload: dict) -> dict: ...
    def list_registrations(self, user: dict, **filters) -> dict: ...
    def export_registrations(self, user: dict, **filters) -> dict: ...
    def get_registration(self, user: dict, registration_id) -> dict: ...
    def review_registration(self, user: dict, registration_id, payload: dict) -> dict: ...
    def disclose_registration(self, user: dict, registration_id, payload: dict) -> dict: ...


class StandaloneEmploymentGateway:
    """Local declarations; school verification never implies external employment certification."""

    @staticmethod
    def _service():
        from app.modules.internship.services import internship_employment_service
        return internship_employment_service

    def get_my_registration(self, user, *, batch_id, internship_id, notification_page=1):
        return self._service().get_my(user,batch_id=batch_id,internship_id=internship_id,notification_page=notification_page)

    def read_my_notification(self, user, message_id, *, batch_id, internship_id):
        return self._service().read_my_notification(user,message_id,batch_id=batch_id,internship_id=internship_id)

    def submit_registration(self, user, payload):
        return self._service().submit_my(user,payload)

    def list_registrations(self, user, **filters):
        return self._service().list_for_teacher(user,**filters)

    def export_registrations(self, user, **filters):
        return self._service().export_registrations(user,**filters)

    def get_registration(self, user, registration_id):
        return self._service().get_for_teacher(user,registration_id)

    def review_registration(self, user, registration_id, payload):
        return self._service().review(user,registration_id,payload)

    def disclose_registration(self, user, registration_id, payload):
        return self._service().disclose_for_teacher(user,registration_id,payload)

    def transition_from_internship(self, transition: EmploymentTransition) -> dict:
        return {
            "enabled": False,
            "status": "NOT_CONFIGURED",
            "studentId": str(transition.student_id),
            "internshipId": str(transition.internship_id),
        }

    def get_student_destination(self, student_id: int, *, internship_id=None) -> dict | None:
        return self._service().destination(student_id,internship_id=internship_id)

    def cohort_metrics(self, student_ids: list[int]) -> dict:
        return {
            "configured": False,
            "employed": 0,
            "unemployed": 0,
            "helpCovered": 0,
            "status": "NOT_CONFIGURED",
        }

    def signed_month_counts(self, student_ids: list[int], months: list[str], as_of_date: str) -> dict[str, int]:
        return {}


employment_gateway: EmploymentGateway = StandaloneEmploymentGateway()
