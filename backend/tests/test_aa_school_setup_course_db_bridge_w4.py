"""A-W4 fixed-query Course Catalog DB bridge contracts."""
from __future__ import annotations

import inspect
from contextlib import contextmanager
from types import SimpleNamespace

import pytest


def _bridge():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_course_preflight_service as bridge
    return bridge


def _row(code="CS101", *, college="17", teacher="81", **changes):
    row = {
        "courseCode": code,
        "version": "1",
        "courseName": f"课程{code}",
        "category": "MAJOR_CORE",
        "nature": "REQUIRED",
        "credit": "3",
        "hoursTotal": "48",
        "hoursTheory": "32",
        "hoursPractice": "16",
        "hoursExperiment": "",
        "hoursComputer": "",
        "examMode": "EXAM",
        "ownerCollegeId": college,
        "ownerTeacherId": teacher,
        "isCore": "是",
        "description": "",
        "prerequisiteCodes": "",
    }
    row.update(changes)
    return row


class _ScalarResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class _FakeDb:
    def __init__(self, answers):
        self.answers = list(answers)
        self.scalar_calls = 0

    def scalars(self, _stmt):
        if self.scalar_calls >= len(self.answers):
            raise AssertionError("unexpected per-row/additional SQL query")
        rows = self.answers[self.scalar_calls]
        self.scalar_calls += 1
        return _ScalarResult(rows)


def _install_fake_session(monkeypatch, *, course_rows=None, college_rows=None, teacher_rows=None, security=None):
    bridge = _bridge()
    fake = _FakeDb([course_rows or [], college_rows or [], teacher_rows or []])

    @contextmanager
    def fake_session():
        yield fake

    monkeypatch.setattr(bridge, "session", fake_session)
    monkeypatch.setattr(bridge, "_tid", lambda: 1001)
    monkeypatch.setattr(
        bridge,
        "build_affairs_context",
        lambda _user, db: security or SimpleNamespace(scope_type="TENANT_ALL", college_ids=set()),
    )
    return fake


def _college(college_id=17, status="ACTIVE"):
    return SimpleNamespace(id=college_id, status=status)


def _teacher(user_id=81, *, user_type="TEACHER", status="ACTIVE"):
    return SimpleNamespace(id=user_id, user_type=user_type, status=status)


def _course(
    *,
    course_id=1001,
    code="CS101",
    version=1,
    prev_version_id=None,
    status="ENABLED",
    name="课程CS101",
    prerequisite_json="[]",
):
    return SimpleNamespace(
        id=course_id,
        course_code=code,
        course_name=name,
        course_name_en=None,
        category="MAJOR_CORE",
        nature="REQUIRED",
        credit=3,
        hours_total=48,
        hours_theory=32,
        hours_practice=16,
        hours_experiment=None,
        hours_computer=None,
        exam_mode="EXAM",
        owner_college_id=17,
        owner_teacher_id=81,
        is_core=True,
        prerequisite_codes_json=prerequisite_json,
        description=None,
        version=version,
        prev_version_id=prev_version_id,
        status=status,
    )


def test_bridge_owns_no_file_job_or_confirm_lifecycle():
    source = inspect.getsource(_bridge())
    for forbidden in ("ImportJob(", "FileObject(", "load_workbook", "db.commit", "confirm_import"):
        assert forbidden not in source


def test_100_rows_use_fixed_three_batch_queries_not_per_row_sql(monkeypatch):
    rows = [_row(f"CS{100 + i}") for i in range(100)]
    fake = _install_fake_session(
        monkeypatch,
        college_rows=[_college()],
        teacher_rows=[_teacher()],
    )
    result = _bridge().course_catalog_dry_run(rows, {"currentRoleCode": "ACADEMIC_ADMIN"})
    assert fake.scalar_calls == 3
    assert result["totalRows"] == 100
    assert result["createRows"] == 100
    assert result["invalidRows"] == 0


def test_existing_course_snapshot_supplies_course_id_prev_pointer_and_reuses_exact_fact(monkeypatch):
    existing = _course()
    fake = _install_fake_session(
        monkeypatch,
        course_rows=[existing],
        college_rows=[_college()],
        teacher_rows=[_teacher()],
    )
    result = _bridge().course_catalog_dry_run([_row()], {"currentRoleCode": "ACADEMIC_ADMIN"})
    assert fake.scalar_calls == 3
    assert result["reuseRows"] == 1
    assert result["items"][0]["action"] == "REUSE"


def test_invalid_or_inactive_owner_college_is_row_reject(monkeypatch):
    _install_fake_session(
        monkeypatch,
        college_rows=[_college(status="DISABLED")],
        teacher_rows=[_teacher()],
    )
    result = _bridge().course_catalog_dry_run([_row()], {"currentRoleCode": "ACADEMIC_ADMIN"})
    assert result["rejectRows"] == 1
    assert result["items"][0]["code"] == "COURSE_OWNER_COLLEGE_INVALID"
    assert result["errors"][0]["field"] == "ownerCollegeId"


def test_invalid_non_teacher_or_inactive_owner_is_row_reject(monkeypatch):
    _install_fake_session(
        monkeypatch,
        college_rows=[_college()],
        teacher_rows=[_teacher(user_type="STUDENT")],
    )
    result = _bridge().course_catalog_dry_run([_row()], {"currentRoleCode": "ACADEMIC_ADMIN"})
    assert result["rejectRows"] == 1
    assert result["items"][0]["code"] == "COURSE_OWNER_TEACHER_INVALID"
    assert result["errors"][0]["field"] == "ownerTeacherId"


def test_college_admin_scope_is_fail_closed_and_cross_college_rejected(monkeypatch):
    _install_fake_session(
        monkeypatch,
        college_rows=[_college(18)],
        teacher_rows=[_teacher()],
        security=SimpleNamespace(scope_type="COLLEGE", college_ids={17}),
    )
    cross = _bridge().course_catalog_dry_run(
        [_row(college="18")],
        {"currentRoleCode": "COLLEGE_ADMIN"},
    )
    assert cross["rejectRows"] == 1
    assert cross["items"][0]["code"] == "COURSE_OWNER_OUT_OF_SCOPE"

    _install_fake_session(
        monkeypatch,
        college_rows=[_college(17)],
        teacher_rows=[_teacher()],
        security=SimpleNamespace(scope_type="NONE", college_ids=set()),
    )
    unconfigured = _bridge().course_catalog_dry_run(
        [_row(college="17")],
        {"currentRoleCode": "COLLEGE_ADMIN"},
    )
    assert unconfigured["rejectRows"] == 1
    assert unconfigured["items"][0]["code"] == "COURSE_OWNER_OUT_OF_SCOPE"


def test_bad_xlsx_row_is_aggregated_as_reject_without_aborting_other_rows(monkeypatch):
    _install_fake_session(
        monkeypatch,
        college_rows=[_college()],
        teacher_rows=[_teacher()],
    )
    result = _bridge().course_catalog_dry_run(
        [_row("bad-code"), _row("CS102")],
        {"currentRoleCode": "ACADEMIC_ADMIN"},
    )
    assert result["totalRows"] == 2
    assert result["createRows"] == 1
    assert result["rejectRows"] == 1
    assert result["invalidRows"] == 1
    assert result["errors"][0]["code"] == "COURSE_ROW_INVALID"


def test_corrupt_persisted_prerequisite_json_fails_closed_before_classification(monkeypatch):
    _install_fake_session(
        monkeypatch,
        course_rows=[_course(prerequisite_json="{broken")],
        college_rows=[_college()],
        teacher_rows=[_teacher()],
    )
    with pytest.raises(ValueError, match="corrupt prerequisiteCodes JSON"):
        _bridge().course_catalog_dry_run([_row()], {"currentRoleCode": "ACADEMIC_ADMIN"})


def test_bridge_does_not_add_prerequisite_existence_query(monkeypatch):
    rows = [_row(prerequisiteCodes="MATH101,ENG101")]
    fake = _install_fake_session(
        monkeypatch,
        college_rows=[_college()],
        teacher_rows=[_teacher()],
    )
    result = _bridge().course_catalog_dry_run(rows, {"currentRoleCode": "ACADEMIC_ADMIN"})
    assert fake.scalar_calls == 3
    assert result["createRows"] == 1


def test_missing_optional_owner_refs_skip_extra_queries(monkeypatch):
    bridge = _bridge()
    fake = _FakeDb([[]])

    @contextmanager
    def fake_session():
        yield fake

    monkeypatch.setattr(bridge, "session", fake_session)
    monkeypatch.setattr(bridge, "_tid", lambda: 1001)
    monkeypatch.setattr(
        bridge,
        "build_affairs_context",
        lambda _user, db: SimpleNamespace(scope_type="TENANT_ALL", college_ids=set()),
    )
    result = bridge.course_catalog_dry_run(
        [_row(college="", teacher="")],
        {"currentRoleCode": "ACADEMIC_ADMIN"},
    )
    assert fake.scalar_calls == 1
    assert result["createRows"] == 1
