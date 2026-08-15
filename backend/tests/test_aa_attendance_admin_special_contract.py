"""C-W1：管理员特殊考勤旁路必须与普通教学场次显式隔离。"""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest


class _ScalarResult:
    def __init__(self, *, first=None, rows=None):
        self._first = first
        self._rows = list(rows or [])

    def first(self):
        return self._first

    def all(self):
        return list(self._rows)


class _Db:
    def __init__(self, *, term, students=None):
        self.term = term
        self.students = list(students or [])
        self.added = []

    def scalars(self, query):
        text = str(query)
        if "t_aa_term" in text:
            return _ScalarResult(first=self.term)
        if "student_profile" in text:
            return _ScalarResult(rows=self.students)
        raise AssertionError(text)

    def get(self, _model, _identity):
        return None

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = 700 + self.added.index(obj)

    def commit(self):
        pass

    def refresh(self, _obj):
        pass


@contextmanager
def _session(db):
    yield db


def _term():
    return SimpleNamespace(
        id=9,
        tenant_id=1,
        year_code="2025-2026",
        term_no=2,
        is_current=True,
        is_deleted=False,
    )


def _admin():
    return {
        "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "STAFF",
        "loginName": "school_admin01",
        "userId": "u_school_admin01",
    }


def _teacher():
    return {
        "currentRoleCode": "ACADEMIC_TEACHER",
        "userType": "STAFF",
        "loginName": "T001",
        "userId": "u_T001",
    }


def test_normal_teacher_can_never_request_admin_special():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service

    with pytest.raises(AppException) as exc:
        service._admin_special_contract(
            "ACADEMIC_TEACHER",
            {
                "sessionType": "ADMIN_SPECIAL",
                "specialReason": "历史数据纠错补录",
                "evidence": "file-1",
            },
            task_id=30,
        )

    assert exc.value.http_status == 403
    assert "普通教师不能创建" in exc.value.message


def test_admin_without_teaching_task_must_explicitly_choose_admin_special():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service

    with pytest.raises(AppException) as exc:
        service._admin_special_contract(
            "SCHOOL_ADMIN",
            {"sessionType": "其他"},
            task_id=None,
        )

    assert "必须显式选择 ADMIN_SPECIAL" in exc.value.message


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            {"sessionType": "ADMIN_SPECIAL", "specialReason": "短", "evidence": "file-1"},
            "原因必填且不少于5字",
        ),
        (
            {"sessionType": "ADMIN_SPECIAL", "specialReason": "历史数据纠错补录"},
            "必须提供可审计 evidence",
        ),
    ],
)
def test_admin_special_requires_reason_and_evidence(body, message):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service

    with pytest.raises(AppException) as exc:
        service._admin_special_contract("SCHOOL_ADMIN", body, task_id=None)

    assert message in exc.value.message


def test_admin_special_with_task_is_allowed_but_stays_explicit_special():
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service

    special, reason, evidence = service._admin_special_contract(
        "ACADEMIC_ADMIN",
        {
            "sessionType": "admin_special",
            "specialReason": "迁移后补录课堂事实",
            "specialEvidence": {"fileId": "f-10", "ticket": "AA-1"},
        },
        task_id=30,
    )

    assert special is True
    assert reason == "迁移后补录课堂事实"
    assert '"fileId":"f-10"' in evidence
    assert '"ticket":"AA-1"' in evidence


def test_admin_special_without_task_persists_marker_and_audit(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_archive_service as archive
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service

    db = _Db(
        term=_term(),
        students=[SimpleNamespace(id=101, student_no="S001", real_name="学生甲")],
    )
    audits = []
    monkeypatch.setattr(service, "session", lambda: _session(db))
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(service, "_audit", lambda _db, biz_id, action, detail="": audits.append(
        (biz_id, action, detail)
    ))
    monkeypatch.setattr(service, "_primary_teacher_key", lambda _user: "school_admin01")
    monkeypatch.setattr(archive, "guard_term_writable", lambda *_args, **_kwargs: None)

    result = service.create_session(
        _admin(),
        {
            "classId": 10,
            "sessionDate": "2026-03-02",
            "slotNo": 3,
            "sessionType": "ADMIN_SPECIAL",
            "specialReason": "历史迁移数据人工补录",
            "evidence": {"fileId": "proof-1"},
            "courseName": "特殊活动考勤",
        },
    )

    assert result["sessionType"] == "ADMIN_SPECIAL"
    assert result["sourceType"] == "ADMIN_SPECIAL"
    assert result["teachingTaskId"] is None
    assert result["rosterIdentity"] is None
    assert audits and audits[-1][1] == "CREATE"
    assert "source=ADMIN_SPECIAL" in audits[-1][2]
    assert "reason=历史迁移数据人工补录" in audits[-1][2]
    assert "proof-1" in audits[-1][2]


def test_default_stats_condition_excludes_admin_special():
    from app.models import AaAttendanceSession
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service

    condition = service._stats_session_type_condition(AaAttendanceSession)
    sql = str(condition.compile(compile_kwargs={"literal_binds": True}))
    assert "IS NULL" in sql
    assert "ADMIN_SPECIAL" in sql
    assert "!=" in sql


def test_explicit_admin_special_stats_condition_is_exact_match():
    from app.models import AaAttendanceSession
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service

    condition = service._stats_session_type_condition(AaAttendanceSession, "ADMIN_SPECIAL")
    sql = str(condition.compile(compile_kwargs={"literal_binds": True}))
    assert "ADMIN_SPECIAL" in sql
    assert " = " in sql
    assert "IS NULL" not in sql


def test_normal_teacher_contract_remains_task_first():
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service

    special, reason, evidence = service._admin_special_contract(
        "ACADEMIC_TEACHER",
        {"sessionType": "实训"},
        task_id=30,
    )
    assert special is False
    assert reason == ""
    assert evidence == ""
    assert _teacher()["currentRoleCode"] == "ACADEMIC_TEACHER"