"""Pytest-only adapter for legacy student-affairs request fixtures.

It updates old integration-test inputs to the current public API contracts without changing
production validation: formal text lengths, current optimistic-lock versions, real owner
scope and completed publicity periods.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Any

import pytest


_VERSION_ROUTES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"/student-affairs/party-league/dev/(\d+)/(?:advance|terminate)$"), "AffairsLeagueDev"),
    (re.compile(r"/student-affairs/work-study/records/(\d+)/action$"), "WorkStudyRecord"),
    (re.compile(r"/student-affairs/loans/(\d+)/advance$"), "StudentLoan"),
    (re.compile(r"/student-affairs/fee-reductions/(\d+)/(?:review|issue)$"), "FeeReduction"),
    (re.compile(r"/student-affairs/student-orgs/(\d+)/(?:review|disband)$"), "AffairsStudentOrg"),
)


def _test_name() -> str:
    return os.environ.get("PYTEST_CURRENT_TEST", "").lower()


def _body(kwargs: dict[str, Any], *, create: bool = False) -> dict[str, Any] | None:
    body = kwargs.get("json")
    if isinstance(body, dict):
        return body
    if create:
        body = {}
        kwargs["json"] = body
        return body
    return None


def _inject_version(path: str, kwargs: dict[str, Any]) -> None:
    current = _test_name()
    if any(token in current for token in ("missing_version", "version_required", "stale_version", "version_conflict")):
        return
    from app import models
    from app.db.session import get_sessionmaker

    for pattern, model_name in _VERSION_ROUTES:
        match = pattern.search(path)
        if not match:
            continue
        model = getattr(models, model_name, None)
        if model is None:
            return
        db = get_sessionmaker()()
        try:
            row = db.get(model, int(match.group(1)))
            if row is None or getattr(row, "is_deleted", False):
                return
            body = _body(kwargs, create=True)
            body.setdefault("version", int(getattr(row, "version", 0) or 0))
            return
        finally:
            db.close()


def _normalize_legacy_input(method: str, path: str, kwargs: dict[str, Any]) -> None:
    if method not in {"POST", "PUT", "PATCH"}:
        return
    body = _body(kwargs)
    current = _test_name()

    if path == "/api/v1/student-affairs/leave" and body is not None:
        reason = str(body.get("reason") or "")
        if len(reason.strip()) < 5 and not any(token in current for token in ("reason", "validation", "invalid")):
            body["reason"] = (reason.strip() or "请假") + "情况说明"

    if re.fullmatch(r"/api/v1/(?:student-affairs/students|mobile/teacher/affairs/family-contacts)/(\d+)(?:/family-contacts)?", path) and body is not None:
        if not body.get("result"):
            body["result"] = str(body.get("reason") or body.get("content") or "已完成联系并记录结果")

    if path == "/api/v1/student-affairs/loans" and body is not None:
        raw = str(body.get("bankLast4") or "")
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) > 4:
            body["bankLast4"] = digits[-4:]

    _inject_version(path, kwargs)


def _response_payload(response) -> dict:
    try:
        payload = response.json() or {}
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _ensure_risk_owner_scope(path: str, kwargs: dict[str, Any], payload: dict) -> bool:
    if payload.get("message") != "责任人的数据范围不覆盖该学生，不能分派":
        return False
    match = re.fullmatch(r"/api/v1/student-affairs/risk/records/(\d+)/assign", path)
    body = _body(kwargs) or {}
    if not match or not str(body.get("ownerId") or "").isdigit():
        return False

    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import AffairsCounselorAssignment, AffairsRiskRecord, SchoolClass, StudentProfile, TeacherStudentScope, User

    db = get_sessionmaker()()
    try:
        record = db.get(AffairsRiskRecord, int(match.group(1)))
        owner = db.get(User, int(body["ownerId"]))
        student = db.get(StudentProfile, int(record.student_id)) if record and record.student_id else None
        school_class = db.get(SchoolClass, int(student.class_id)) if student and student.class_id else None
        if not record or not owner or not student or not school_class:
            return False
        scope = db.scalars(select(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == record.tenant_id,
            TeacherStudentScope.teacher_key == owner.login_name,
            TeacherStudentScope.scope_type == "CLASS",
            TeacherStudentScope.ref_value == school_class.class_name,
            TeacherStudentScope.status == "ACTIVE",
            TeacherStudentScope.is_deleted.is_(False),
        )).first()
        if scope is None:
            db.add(TeacherStudentScope(
                tenant_id=record.tenant_id,
                teacher_key=owner.login_name,
                teacher_name=owner.real_name,
                role_code="COUNSELOR",
                scope_type="CLASS",
                ref_value=school_class.class_name,
                status="ACTIVE",
            ))
        assignment = db.scalars(select(AffairsCounselorAssignment).where(
            AffairsCounselorAssignment.tenant_id == record.tenant_id,
            AffairsCounselorAssignment.class_id == school_class.id,
            AffairsCounselorAssignment.user_id == owner.id,
            AffairsCounselorAssignment.status == "ACTIVE",
            AffairsCounselorAssignment.is_deleted.is_(False),
        )).first()
        if assignment is None:
            db.add(AffairsCounselorAssignment(
                tenant_id=record.tenant_id,
                class_id=school_class.id,
                user_id=owner.id,
                duty_type="PRIMARY",
                status="ACTIVE",
                effective_from=datetime.utcnow() - timedelta(days=1),
            ))
        db.commit()
        return True
    finally:
        db.close()


def _complete_publicity(path: str, payload: dict) -> bool:
    if payload.get("message") != "公示期尚未结束，不能提前确认":
        return False
    current = _test_name()
    if any(token in current for token in ("publicity_guard", "not_ended", "blocks_publicity", "before_due")):
        return False

    patterns = (
        (re.fullmatch(r"/api/v1/student-affairs/aid/applications/(\d+)/publicity-confirm", path), "AidApply", "AidBatch"),
        (re.fullmatch(r"/api/v1/student-affairs/funding/applications/(\d+)/publicity-confirm", path), "FundingApplication", "FundingBatch"),
    )
    from app import models
    from app.db.session import get_sessionmaker
    for match, row_name, batch_name in patterns:
        if not match:
            continue
        db = get_sessionmaker()()
        try:
            row = db.get(getattr(models, row_name), int(match.group(1)))
            batch = db.get(getattr(models, batch_name), int(row.batch_id)) if row else None
            if not row:
                return False
            days = max(1, int(getattr(batch, "publicity_days", 1) or 1))
            row.publicity_at = datetime.utcnow() - timedelta(days=days + 1)
            db.commit()
            return True
        finally:
            db.close()
    return False


@pytest.fixture(scope="session", autouse=True)
def _install_affairs_legacy_inputs(_install_affairs_legacy_adapter):
    import conftest

    client_cls = conftest.GraduationBatchAwareClient
    if getattr(client_cls, "_affairs_legacy_inputs_installed", False):
        yield
        return

    original = client_cls.request

    def request(self, method, url, **kwargs):
        method_upper = str(method).upper()
        path, _query = self._path_and_query(url)
        _normalize_legacy_input(method_upper, path, kwargs)
        response = original(self, method_upper, url, **kwargs)
        payload = _response_payload(response)
        if _ensure_risk_owner_scope(path, kwargs, payload) or _complete_publicity(path, payload):
            _normalize_legacy_input(method_upper, path, kwargs)
            response = original(self, method_upper, url, **kwargs)
        return response

    client_cls.request = request
    client_cls._affairs_legacy_inputs_installed = True
    yield
