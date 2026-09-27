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

    def get_student_destination(self, student_id: int) -> dict | None: ...


class StandaloneEmploymentGateway:
    """W1 默认实现：未配置就业扩展时明确返回未启用，不伪造就业结果。"""

    def transition_from_internship(self, transition: EmploymentTransition) -> dict:
        return {
            "enabled": False,
            "status": "NOT_CONFIGURED",
            "studentId": str(transition.student_id),
            "internshipId": str(transition.internship_id),
        }

    def get_student_destination(self, student_id: int) -> dict | None:
        return None
