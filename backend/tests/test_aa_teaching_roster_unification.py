"""教学任务官方名单优先级与四域入口回归。"""
from types import SimpleNamespace


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


def _course():
    return SimpleNamespace(
        id=50, tenant_id=1, is_deleted=False, teaching_task_id=30,
        batch_id=40, status="OPEN",
    )


def _selection_batch(status):
    return SimpleNamespace(
        id=40, tenant_id=1, is_deleted=False, term_id=9, status=status,
    )


def _student(student_id=1, student_no="S001", class_id=10):
    return SimpleNamespace(
        id=student_id, tenant_id=1, is_deleted=False, student_no=student_no,
        real_name=f"学生{student_id}", class_id=class_id,
    )


def test_selection_relation_without_locked_batch_fails_closed(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_teaching_roster_service as service

    monkeypatch.setattr(service, "_tid", lambda: 1)
    db = _Db(
        task=_task(), task_batch=_task_batch(),
        selection_courses=[_course()], selection_batches=[_selection_batch("CLOSED")],
        profiles=[_student()],
    )

    result = service.resolve_teaching_task_roster(db, 30)

    assert result["ready"] is False
    assert result["source"] == "SELECTION_PENDING"
    assert "尚未锁定" in result["note"]


def test_locked_selection_roster_overrides_administrative_class(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_teaching_roster_service as service

    monkeypatch.setattr(service, "_tid", lambda: 1)
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


def test_administrative_class_is_used_only_when_no_selection_relation(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_teaching_roster_service as service

    monkeypatch.setattr(service, "_tid", lambda: 1)
    db = _Db(
        task=_task(), task_batch=_task_batch(), profiles=[_student(1), _student(2, "S002")],
    )

    result = service.resolve_teaching_task_roster(db, 30)

    assert result["ready"] is True
    assert result["source"] == "ADMIN_CLASS"
    assert result["studentIds"] == [1, 2]


def test_public_services_share_roster_aware_facades():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_selection_service.lock_batch.__module__.endswith(
        "academic_affairs_selection_facade"
    )
    assert services.academic_affairs_attendance_service.create_session.__module__.endswith(
        "academic_affairs_attendance_facade"
    )
    assert services.academic_affairs_grade_service.roster.__module__.endswith(
        "academic_affairs_grade_roster_facade"
    )
    assert services.academic_affairs_exam_service.assign_seats.__module__.endswith(
        "academic_affairs_exam_facade"
    )
