"""普通教师课堂考勤必须绑定当前学期本人已确认的真实教学任务。"""
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
    def __init__(self, *, term, task=None, batch=None, students=None):
        self.term = term
        self.task = task
        self.batch = batch
        self.students = list(students or [])
        self.added = []

    def scalars(self, query):
        text = str(query)
        if "t_aa_term" in text:
            return _ScalarResult(first=self.term)
        if "student_profile" in text:
            return _ScalarResult(rows=self.students)
        raise AssertionError(text)

    def get(self, model, identity):
        name = getattr(model, "__name__", "")
        if name == "AaTeachingTask":
            return self.task if self.task and int(self.task.id) == int(identity) else None
        if name == "AaTeachingTaskBatch":
            return self.batch if self.batch and int(self.batch.id) == int(identity) else None
        return None

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        if self.added and getattr(self.added[-1], "id", None) is None:
            self.added[-1].id = 100

    def commit(self):
        pass

    def refresh(self, _obj):
        pass


@contextmanager
def _session(db):
    yield db


def _term(term_id=9):
    return SimpleNamespace(
        id=term_id,
        tenant_id=1,
        year_code="2025-2026",
        term_no=2,
        is_current=True,
        is_deleted=False,
    )


def _task(*, teacher="T001", class_id=10, batch_id=20, status="APPROVED"):
    return SimpleNamespace(
        id=30,
        tenant_id=1,
        is_deleted=False,
        teacher_key=teacher,
        class_id=class_id,
        batch_id=batch_id,
        status=status,
        course_name="数据库原理",
    )


def _batch(*, term_id=9):
    return SimpleNamespace(id=20, tenant_id=1, is_deleted=False, term_id=term_id)


def _user(teacher="T001"):
    return {
        "currentRoleCode": "ACADEMIC_TEACHER",
        "loginName": teacher,
        "userId": f"u_{teacher}",
    }


def _prepare(monkeypatch, db):
    from app.modules.academic_affairs.services import academic_affairs_attendance_facade as service

    monkeypatch.setattr(service._legacy, "session", lambda: _session(db))
    monkeypatch.setattr(service._legacy, "_tid", lambda: 1)
    monkeypatch.setattr(service._legacy, "_audit", lambda *_args, **_kwargs: None)
    return service


def test_teacher_must_supply_teaching_task(monkeypatch):
    from app.core.exceptions import AppException

    service = _prepare(monkeypatch, _Db(term=_term()))
    with pytest.raises(AppException) as exc:
        service.create_session(_user(), {"classId": 10, "sessionDate": "2026-03-02"})

    assert "请选择当前学期本人教学任务" in exc.value.message


def test_assigned_but_unconfirmed_task_is_rejected(monkeypatch):
    from app.core.exceptions import AppException

    db = _Db(term=_term(), task=_task(status="ASSIGNED"), batch=_batch())
    service = _prepare(monkeypatch, db)
    with pytest.raises(AppException) as exc:
        service.create_session(_user(), {
            "teachingTaskId": 30,
            "classId": 10,
            "sessionDate": "2026-03-02",
        })

    assert "须经教师确认" in exc.value.message


def test_other_teacher_task_is_rejected(monkeypatch):
    from app.core.exceptions import AppException

    db = _Db(term=_term(), task=_task(teacher="T002"), batch=_batch())
    service = _prepare(monkeypatch, db)
    with pytest.raises(AppException) as exc:
        service.create_session(_user("T001"), {
            "teachingTaskId": 30,
            "classId": 10,
            "sessionDate": "2026-03-02",
        })

    assert exc.value.http_status == 403


def test_old_term_task_is_rejected(monkeypatch):
    from app.core.exceptions import AppException

    db = _Db(term=_term(9), task=_task(), batch=_batch(term_id=8))
    service = _prepare(monkeypatch, db)
    with pytest.raises(AppException) as exc:
        service.create_session(_user(), {
            "teachingTaskId": 30,
            "classId": 10,
            "sessionDate": "2026-03-02",
        })

    assert "只能为当前学期" in exc.value.message


def test_client_cannot_replace_task_class(monkeypatch):
    from app.core.exceptions import AppException

    db = _Db(term=_term(), task=_task(class_id=10), batch=_batch())
    service = _prepare(monkeypatch, db)
    with pytest.raises(AppException) as exc:
        service.create_session(_user(), {
            "teachingTaskId": 30,
            "classId": 99,
            "sessionDate": "2026-03-02",
        })

    assert "教学任务与行政班不一致" in exc.value.message


def test_public_attendance_service_points_to_task_binding_facade():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_attendance_service.create_session.__module__.endswith(
        "academic_affairs_attendance_facade"
    )
