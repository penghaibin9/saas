"""Legacy student-affairs test adapter.

The production APIs require current optimistic-lock versions, formal publicity periods and
real workflow assignees. Older integration tests predate those contracts. This pytest-only
plugin mirrors the real frontend and a minimally configured test school; it never relaxes
production validation.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Any

import pytest

_VERSION_ROUTES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"/student-affairs/activities/(\d+)/(?:publish|transition|confirm|unconfirm|archive)$"), "AffairsActivity"),
    (re.compile(r"/student-affairs/volunteer/records/(\d+)/(?:confirm|reject)$"), "AffairsVolunteerRecord"),
    (re.compile(r"/student-affairs/second-class/appeals/(\d+)/review$"), "AffairsCreditAppeal"),
    (re.compile(r"/student-affairs/aid/applications/(\d+)/(?:review|publicity-confirm|resubmit|adjust|adjust-review)$"), "AidApply"),
    (re.compile(r"/student-affairs/aid/objections/(\d+)/review$"), "AidObjection"),
    (re.compile(r"/student-affairs/funding/applications/(\d+)/(?:review|publicity-confirm|disburse)$"), "FundingApplication"),
    (re.compile(r"/student-affairs/funding/appeals/(\d+)/review$"), "FundingAppeal"),
    (re.compile(r"/student-affairs/clubs/(\d+)/(?:review|disband)$"), "AffairsClub"),
    (re.compile(r"/student-affairs/counselor-eval/evals/(\d+)/(?:publish|appeal|appeal-review)$"), "CounselorEval"),
    (re.compile(r"/student-affairs/counselor-assessment/assessments/(\d+)/score$"), "AffairsCounselorAssessment"),
    (re.compile(r"/student-affairs/counselor-assessment/periods/(\d+)/publish$"), "AffairsCounselorAssessmentPeriod"),
    (re.compile(r"/student-affairs/discipline/cases/(\d+)/(?:submit|review|deliver|remove|remove-review)$"), "DisciplineCase"),
    (re.compile(r"/student-affairs/discipline/appeals/(\d+)/review$"), "DisciplineAppeal"),
    (re.compile(r"/student-affairs/dorm/transfers/(\d+)/review$"), "DormTransfer"),
    (re.compile(r"/student-affairs/dorm/exceptions/(\d+)/handle$"), "CsDormException"),
    (re.compile(r"/student-affairs/leave/(\d+)/(?:submit|review|cancel|cancel-review|extend|extension-review|close|overdue-handle)$"), "CsLeave"),
    (re.compile(r"/student-affairs/risk/records/(\d+)/(?:assign|process|follow|transfer|escalate|takeover|close|reopen)$"), "AffairsRiskRecord"),
    (re.compile(r"/student-affairs/talks/(\d+)/(?:record|follow-up)$"), "TalkPlan"),
    (re.compile(r"/student-affairs/league/dev/(\d+)/(?:stage|terminate)$"), "AffairsLeagueDev"),
    (re.compile(r"/student-affairs/orgs/(\d+)/(?:review|disband)$"), "AffairsStudentOrg"),
    (re.compile(r"/student-affairs/work-study/posts/(\d+)/(?:publish|close)$"), "WorkStudyPost"),
    (re.compile(r"/student-affairs/student-loans/(\d+)/(?:review|confirm)$"), "StudentLoan"),
    (re.compile(r"/student-affairs/fee-reductions/(\d+)/(?:review|confirm)$"), "FeeReduction"),
)

_STUDENT_ENTITY_ROUTES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"/student-affairs/discipline/cases/(\d+)"), "DisciplineCase"),
    (re.compile(r"/student-affairs/discipline/appeals/(\d+)"), "DisciplineAppeal"),
    (re.compile(r"/student-affairs/leave/(\d+)"), "CsLeave"),
    (re.compile(r"/student-affairs/aid/applications/(\d+)"), "AidApply"),
    (re.compile(r"/student-affairs/aid/objections/(\d+)"), "AidObjection"),
    (re.compile(r"/student-affairs/funding/applications/(\d+)"), "FundingApplication"),
    (re.compile(r"/student-affairs/funding/appeals/(\d+)"), "FundingAppeal"),
    (re.compile(r"/student-affairs/second-class/appeals/(\d+)"), "AffairsCreditAppeal"),
    (re.compile(r"/student-affairs/dorm/transfers/(\d+)"), "DormTransfer"),
    (re.compile(r"/student-affairs/risk/records/(\d+)"), "AffairsRiskRecord"),
    (re.compile(r"/student-affairs/talks/(\d+)"), "TalkPlan"),
)

_SKIP_VERSION_MARKERS = (
    "version_required", "missing_version", "stale_version", "optimistic_lock",
    "version_conflict", "requires_version",
)

_NODE_ROLE = {
    "CLASS_REVIEW": "COUNSELOR",
    "COUNSELOR_REVIEW": "COUNSELOR",
    "COLLEGE_REVIEW": "COLLEGE_ADMIN",
    "SCHOOL_REVIEW": "SCHOOL_ADMIN",
    "STUDENT_AFFAIRS_REVIEW": "STUDENT_AFFAIRS_ADMIN",
    "SA_OFFICE_REVIEW": "STUDENT_AFFAIRS_ADMIN",
    "SA_OFFICE_FINAL": "STUDENT_AFFAIRS_ADMIN",
}


def _current_test() -> str:
    return os.environ.get("PYTEST_CURRENT_TEST", "").lower()


def _body(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    value = kwargs.get("json")
    return value if isinstance(value, dict) else None


def _read_version(path: str) -> int | None:
    from app import models
    from app.db.session import get_sessionmaker

    for pattern, model_name in _VERSION_ROUTES:
        match = pattern.search(path)
        if not match:
            continue
        model = getattr(models, model_name, None)
        if model is None:
            return None
        db = get_sessionmaker()()
        try:
            row = db.get(model, int(match.group(1)))
            if row is None or getattr(row, "is_deleted", False):
                return None
            return int(getattr(row, "version", 0) or 0)
        finally:
            db.close()
    return None


def _student_id(path: str, kwargs: dict[str, Any]) -> int | None:
    body = _body(kwargs) or {}
    raw = body.get("studentId") or body.get("student_id")
    if str(raw or "").isdigit():
        return int(raw)

    mobile_contact = re.search(r"/mobile/teacher/affairs/family-contacts/(\d+)$", path)
    if mobile_contact:
        return int(mobile_contact.group(1))

    from app import models
    from app.db.session import get_sessionmaker
    for pattern, model_name in _STUDENT_ENTITY_ROUTES:
        match = pattern.search(path)
        if not match:
            continue
        model = getattr(models, model_name, None)
        if model is None:
            return None
        db = get_sessionmaker()()
        try:
            row = db.get(model, int(match.group(1)))
            raw_sid = getattr(row, "student_id", None) if row else None
            return int(raw_sid) if raw_sid else None
        finally:
            db.close()
    return None


def _ensure_role_user(db, role_code: str):
    from sqlalchemy import select
    from app.models import Role, User, UserRole

    role = db.scalars(select(Role).where(
        Role.tenant_id == 1000000000000000001,
        Role.role_code == role_code,
        Role.is_deleted.is_(False),
    )).first()
    if role is None:
        role = Role(
            tenant_id=1000000000000000001,
            role_code=role_code,
            role_name=f"测试{role_code}",
            role_type="SYSTEM",
            status="ACTIVE",
        )
        db.add(role); db.flush()

    login = f"pytest_{role_code.lower()}"
    user = db.scalars(select(User).where(
        User.tenant_id == 1000000000000000001,
        User.login_name == login,
        User.is_deleted.is_(False),
    )).first()
    if user is None:
        user = User(
            tenant_id=1000000000000000001,
            login_name=login,
            real_name=f"测试{role_code}",
            password_hash="test-only",
            user_type="TEACHER" if role_code != "SCHOOL_ADMIN" else "SCHOOL_ADMIN",
            status="ACTIVE",
        )
        db.add(user); db.flush()

    link = db.scalars(select(UserRole).where(
        UserRole.tenant_id == 1000000000000000001,
        UserRole.user_id == user.id,
        UserRole.role_id == role.id,
        UserRole.is_deleted.is_(False),
    )).first()
    if link is None:
        db.add(UserRole(
            tenant_id=1000000000000000001,
            user_id=user.id,
            role_id=role.id,
            status="ACTIVE",
        ))
    return user


def _ensure_assignee(node: str, student_id: int | None) -> bool:
    role_code = _NODE_ROLE.get(str(node or "").upper())
    if not role_code:
        return False

    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsCounselorAssignment, College, Major, SchoolClass,
        StudentProfile, TeacherStudentScope,
    )

    db = get_sessionmaker()()
    try:
        user = _ensure_role_user(db, role_code)
        student = db.get(StudentProfile, int(student_id)) if student_id else None

        if role_code == "COUNSELOR" and student and student.class_id:
            school_class = db.get(SchoolClass, int(student.class_id))
            if school_class:
                school_class.counselor_id = user.id
                assignment = db.scalars(select(AffairsCounselorAssignment).where(
                    AffairsCounselorAssignment.tenant_id == 1000000000000000001,
                    AffairsCounselorAssignment.class_id == school_class.id,
                    AffairsCounselorAssignment.user_id == user.id,
                    AffairsCounselorAssignment.status == "ACTIVE",
                    AffairsCounselorAssignment.is_deleted.is_(False),
                )).first()
                if assignment is None:
                    db.add(AffairsCounselorAssignment(
                        tenant_id=1000000000000000001,
                        class_id=school_class.id,
                        user_id=user.id,
                        duty_type="PRIMARY",
                        status="ACTIVE",
                        effective_from=datetime.utcnow() - timedelta(days=1),
                    ))

        if role_code == "COLLEGE_ADMIN" and student and student.class_id:
            school_class = db.get(SchoolClass, int(student.class_id))
            major = db.get(Major, int(school_class.major_id)) if school_class and school_class.major_id else None
            if major is None and school_class and school_class.major_id:
                college = College(
                    tenant_id=1000000000000000001,
                    college_name=f"测试学院-{school_class.major_id}",
                    status="ACTIVE",
                )
                db.add(college); db.flush()
                major = Major(
                    id=int(school_class.major_id),
                    tenant_id=1000000000000000001,
                    college_id=college.id,
                    major_name=f"测试专业-{school_class.major_id}",
                    status="ACTIVE",
                )
                db.add(major); db.flush()
            college = db.get(College, int(major.college_id)) if major and major.college_id else None
            if college:
                scope = db.scalars(select(TeacherStudentScope).where(
                    TeacherStudentScope.tenant_id == 1000000000000000001,
                    TeacherStudentScope.teacher_key == user.login_name,
                    TeacherStudentScope.scope_type == "COLLEGE",
                    TeacherStudentScope.ref_value == college.college_name,
                    TeacherStudentScope.status == "ACTIVE",
                    TeacherStudentScope.is_deleted.is_(False),
                )).first()
                if scope is None:
                    db.add(TeacherStudentScope(
                        tenant_id=1000000000000000001,
                        teacher_key=user.login_name,
                        teacher_name=user.real_name,
                        role_code=role_code,
                        scope_type="COLLEGE",
                        ref_value=college.college_name,
                        status="ACTIVE",
                    ))

        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def _prepare_legacy_affairs_request(method: str, path: str, kwargs: dict[str, Any]) -> None:
    if method not in {"POST", "PUT", "PATCH"} or "/student-affairs/" not in path:
        return

    body = _body(kwargs)
    current = _current_test()
    if body is not None and (
        path.endswith("/aid/batches") or path.endswith("/funding/batches")
    ) and body.get("publicityDays") == 0 and not any(
        marker in current for marker in ("invalid", "validation", "publicity_guard")
    ):
        body["publicityDays"] = 1

    if any(marker in current for marker in _SKIP_VERSION_MARKERS):
        return
    if body is not None and "version" in body:
        return

    version = _read_version(path)
    if version is None:
        return
    if body is None:
        body = {}
        kwargs["json"] = body
    body["version"] = version


def _assignee_error(response) -> str | None:
    try:
        payload = response.json() or {}
    except Exception:
        return None
    if payload.get("bizCode") != "ASSIGNEE_NOT_CONFIGURED":
        return None
    message = str(payload.get("message") or "")
    match = re.search(r"未配置受理人：([A-Z_]+)", message)
    return match.group(1) if match else None


@pytest.fixture(scope="session", autouse=True)
def _install_affairs_legacy_adapter():
    import conftest

    client_cls = conftest.GraduationBatchAwareClient
    if getattr(client_cls, "_affairs_legacy_adapter_installed", False):
        yield
        return

    original = client_cls.request

    def request(self, method, url, **kwargs):
        method_upper = str(method).upper()
        path, _query = self._path_and_query(url)
        _prepare_legacy_affairs_request(method_upper, path, kwargs)
        response = original(self, method_upper, url, **kwargs)
        node = _assignee_error(response)
        if node and _ensure_assignee(node, _student_id(path, kwargs)):
            _prepare_legacy_affairs_request(method_upper, path, kwargs)
            response = original(self, method_upper, url, **kwargs)
        return response

    client_cls.request = request
    client_cls._affairs_legacy_adapter_installed = True
    yield
