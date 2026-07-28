"""教学任务官方名单优先级与四域入口回归。"""
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _tenant_context():
    """教学名单解析始终运行在显式租户请求上下文中。"""
    from app.core.context import set_tenant

    set_tenant({"tenantId": "1"})
    try:
        yield
    finally:
        set_tenant(None)


class _Query:
    def __init__(self, rows):
        self.rows = list(rows or [])

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self.rows)


class _Db:
    def __init__(self, *, task, task_batch, selection_courses=None, selection_batches=None,
                 selection_records=None, profiles=None):
        self.task = task
        self.task_batch = task_batch
        self.selection_courses = list(selection_courses or [])
        self.selection_batches = list(selection_batches or [])
        self.selection_records = list(selection_records or [])
        self.profiles = list(profiles or [])

    def get(self, model, identity):
        name = getattr(model, "__name__", "")
        if name == "AaTeachingTask":
            return self.task if int(self.task.id) == int(identity) else None
        if name == "AaTeachingTaskBatch":
            return self.task_batch if int(self.task_batch.id) == int(identity) else None
        return None

    def query(self, model):
        name = getattr(model, "__name__", "")
        mapping = {
            "AaSelectionCourse": self.selection_courses,
            "AaSelectionBatch": self.selection_batches,
            "AaSelectionRecord": self.selection_records,
            "StudentProfile": self.profiles,
            "AaTeachingTask": [],
        }
        return _Query(mapping.get(name, []))


def _task():
    return SimpleNamespace(
        id=30, tenant_id=1, is_deleted=False, batch_id=20, class_id=10,
        is_merged=False, merge_snapshot_json=None,
    )


def _task_batch():
    return SimpleNamespace(id=20, tenant_id=1, is_deleted=False, term_id=9, status="APPROVED")


def _course(batch_id=40, course_id=50):
    return SimpleNamespace(
        id=course_id, tenant_id=1, is_deleted=False, teaching_task_id=30,
        batch_id=batch_id, status="OPEN",
    )


def _selection_batch(status, batch_id=40):
    return SimpleNamespace(
        id=batch_id, tenant_id=1, is_deleted=False, term_id=9, status=status,
    )


def _student(student_id=1, student_no="S001", class_id=10):
    return SimpleNamespace(
        id=student_id, tenant_id=1, is_deleted=False, student_no=student_no,
        real_name=f"学生{student_id}", class_id=class_id,
    )


def _patch_tid(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_teaching_roster_policy as policy
    from app.modules.academic_affairs.services import academic_affairs_teaching_roster_service as service

    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(policy, "_tid", lambda: 1)
    return service


def test_selection_relation_without_locked_batch_fails_closed(monkeypatch):
    service = _patch_tid(monkeypatch)
    db = _Db(
        task=_task(), task_batch=_task_batch(),
        selection_courses=[_course()], selection_batches=[_selection_batch("CLOSED")],
        profiles=[_student()],
    )

    result = service.resolve_teaching_task_roster(db, 30)

    assert result["ready"] is False
    assert result["source"] == "SELECTION_PENDING"
    assert "尚未锁定" in result["note"]


def test_latest_pending_batch_overrides_old_locked_roster(monkeypatch):
    service = _patch_tid(monkeypatch)
    db = _Db(
        task=_task(), task_batch=_task_batch(),
        selection_courses=[_course(40, 50), _course(41, 51)],
        selection_batches=[_selection_batch("LOCKED", 40), _selection_batch("CLOSED", 41)],
        profiles=[_student()],
    )

    result = service.resolve_teaching_task_roster(db, 30)

    assert result["ready"] is False
    assert result["source"] == "SELECTION_PENDING"
    assert result["batchIds"] == ["41"]
    assert "旧批次名单不再作为当前事实" in result["note"]


def test_locked_selection_roster_overrides_administrative_class(monkeypatch):
    service = _patch_tid(monkeypatch)
    selected = _student(2, "S002", class_id=99)
    administrative = _student(1, "S001", class_id=10)
    record = SimpleNamespace(
        id=70, tenant_id=1, is_deleted=False, selection_course_id=50,
        student_id=2, status="LOCKED",
    )
    db = _Db(
        task=_task(), task_batch=_task_batch(),
        selection_courses=[_course()], selection_batches=[_selection_batch("LOCKED")],
        selection_records=[record], profiles=[selected, administrative],
    )

    result = service.resolve_teaching_task_roster(db, 30)

    assert result["ready"] is True
    assert result["source"] == "SELECTION_LOCKED"
    assert result["studentIds"] == [2]
    assert result["items"][0]["studentNo"] == "S002"


def test_locked_selection_with_empty_roster_is_not_ready(monkeypatch):
    service = _patch_tid(monkeypatch)
    db = _Db(
        task=_task(), task_batch=_task_batch(),
        selection_courses=[_course()], selection_batches=[_selection_batch("LOCKED")],
        selection_records=[], profiles=[_student()],
    )

    result = service.resolve_teaching_task_roster(db, 30)

    assert result["ready"] is False
    assert result["source"] == "SELECTION_EMPTY"


def test_administrative_class_is_used_only_when_no_selection_relation(monkeypatch):
    service = _patch_tid(monkeypatch)
    db = _Db(
        task=_task(), task_batch=_task_batch(), profiles=[_student(1), _student(2, "S002")],
    )

    result = service.resolve_teaching_task_roster(db, 30)

    assert result["ready"] is True
    assert result["source"] == "ADMIN_CLASS"
    assert result["studentIds"] == [1, 2]


def test_public_services_share_one_roster_aware_entry_per_domain():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_selection_service.lock_batch.__module__.endswith(
        "academic_affairs_selection_service"
    )
    assert services.academic_affairs_attendance_service.create_session.__module__.endswith(
        "academic_affairs_attendance_public_service"
    )
    assert services.academic_affairs_grade_service.roster.__module__.endswith(
        "academic_affairs_grade_service"
    )
    assert services.academic_affairs_exam_service.assign_seats.__module__.endswith(
        "academic_affairs_exam_facade"
    )
