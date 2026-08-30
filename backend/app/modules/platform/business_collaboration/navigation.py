from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .schemas import NavigationTarget, SearchClient


@dataclass(frozen=True, slots=True)
class _TargetSpec:
    route_name: str
    path_template: str
    param_name: str | None
    query_name: str | None
    focus_mode: str
    exact: bool
    subject_guard: Callable[[dict, int], bool] | None = None


def _student_self(actor: dict, student_id: int) -> bool:
    raw = actor.get("studentId") or actor.get("studentProfileId")
    try:
        return int(raw) == int(student_id)
    except (TypeError, ValueError):
        return False


class NavigationTargetResolver:
    """Small allowlisted resolver for PLAT-D private providers.

    The allowlist is the only place that knows path templates.  Providers pass
    stable object identifiers and receive a typed target; they cannot concatenate
    client URLs.  This private map is not a router registry and is not wired into
    any client until the shared integration gate opens.
    """

    _STUDENT: dict[SearchClient, _TargetSpec] = {
        "pc": _TargetSpec(
            route_name="student-detail",
            path_template="/admin/student/{studentId}",
            param_name="studentId",
            query_name=None,
            focus_mode="DETAIL",
            exact=True,
        ),
        "teacherMini": _TargetSpec(
            route_name="teacher-student-detail",
            path_template="/pages/teacher/student-detail/index",
            param_name=None,
            query_name="id",
            focus_mode="DETAIL",
            exact=True,
        ),
        "studentPc": _TargetSpec(
            route_name="profile",
            path_template="/profile",
            param_name=None,
            query_name=None,
            focus_mode="DETAIL",
            exact=True,
            subject_guard=_student_self,
        ),
        "studentMini": _TargetSpec(
            route_name="student-profile",
            path_template="/pages/student/profile/index",
            param_name=None,
            query_name=None,
            focus_mode="DETAIL",
            exact=True,
            subject_guard=_student_self,
        ),
    }

    _DOMAIN: dict[str, dict[SearchClient, _TargetSpec]] = {
        "GRADUATION": {
            "pc": _TargetSpec("graduation-student-detail", "/admin/graduation/students/{id}", "id", None, "DETAIL", True),
            "studentPc": _TargetSpec("graduation-workbench", "/graduation", None, None, "NONE", False),
            "teacherMini": _TargetSpec("teacher-graduation-guide", "/pages/teacher/graduation-guide/index", None, None, "NONE", False),
            "studentMini": _TargetSpec("student-graduation", "/pages/student/graduation/index", None, None, "NONE", False),
        },
        "INTERNSHIP": {
            "pc": _TargetSpec("internship-student-detail", "/admin/internship/students/{id}", "id", None, "DETAIL", True),
            "studentPc": _TargetSpec("internship", "/internship", None, None, "NONE", False),
            "teacherMini": _TargetSpec("teacher-internship-review", "/pages/teacher/internship-review/index", None, None, "NONE", False),
            "studentMini": _TargetSpec("student-internship", "/pages/student/internship/index", None, None, "NONE", False),
        },
        "AFFAIRS": {
            "pc": _TargetSpec("student-affairs-risk-detail", "/admin/student-affairs/risk/{riskId}", "riskId", None, "DETAIL", True),
            "teacherMini": _TargetSpec("teacher-risk-students", "/pages/teacher/risk-students/index", None, None, "NONE", False),
        },
    }

    def student(self, student_id: int, *, client: SearchClient, actor: dict) -> NavigationTarget | None:
        spec = self._STUDENT.get(client)
        if spec is None or (spec.subject_guard and not spec.subject_guard(actor, student_id)):
            return None
        value = str(int(student_id))
        params = {spec.param_name: value} if spec.param_name else {}
        query = {spec.query_name: value} if spec.query_name else {}
        path = spec.path_template.format(**params) if params else spec.path_template
        return NavigationTarget(
            route_name=spec.route_name,
            route_params=params,
            query=query,
            path=path,
            focus_mode=spec.focus_mode,  # type: ignore[arg-type]
            exact=spec.exact,
        )

    def domain(self, module_code: str, object_id: int, *, client: SearchClient) -> NavigationTarget | None:
        spec = self._DOMAIN.get(str(module_code or "").upper(), {}).get(client)
        if spec is None:
            return None
        value = str(int(object_id))
        params = {spec.param_name: value} if spec.param_name else {}
        query = {spec.query_name: value} if spec.query_name else {}
        path = spec.path_template.format(**params) if params else spec.path_template
        return NavigationTarget(
            route_name=spec.route_name,
            route_params=params,
            query=query,
            path=path,
            focus_mode=spec.focus_mode,  # type: ignore[arg-type]
            exact=spec.exact,
        )
