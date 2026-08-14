"""D4-U 开课差异批量查询与结果等价合同。"""
from contextlib import contextmanager
from types import SimpleNamespace


class _Query:
    def __init__(self, db, models):
        self.db = db
        self.models = models

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def join(self, *_args, **_kwargs):
        return self

    def _rows(self):
        from app.models import (
            AaCourse,
            AaProgram,
            AaProgramBinding,
            AaProgramCourse,
            AaTeachingTask,
            AaTeachingTaskBatch,
            AaTerm,
            SchoolClass,
        )

        if len(self.models) == 1 and self.models[0] is AaTerm:
            return [self.db.term]
        if len(self.models) == 1 and self.models[0] is AaProgram:
            return list(self.db.programs)
        if len(self.models) == 1 and self.models[0] is AaProgramBinding:
            return list(self.db.bindings)
        if len(self.models) == 1 and self.models[0] is AaProgramCourse:
            return list(self.db.program_courses)
        if len(self.models) == 1 and self.models[0] is AaTeachingTask:
            return list(self.db.tasks)
        if len(self.models) == 1 and self.models[0] is SchoolClass:
            return list(self.db.classes)
        if len(self.models) == 1 and self.models[0] is AaCourse:
            return list(self.db.catalog)
        if len(self.models) == 1 and getattr(self.models[0], "key", None) == "id":
            owner = getattr(self.models[0], "class_", None)
            if owner is AaTeachingTaskBatch:
                return [(value,) for value in self.db.batch_ids]
        return []

    def all(self):
        return self._rows()

    def first(self):
        rows = self._rows()
        return rows[0] if rows else None


class _Db:
    def __init__(self, *, programs, bindings, program_courses=None, tasks=None, classes=None, catalog=None, batch_ids=None):
        self.query_calls = 0
        self.term = SimpleNamespace(id=9, year_code="2026-2027", term_no=1)
        self.programs = list(programs)
        self.bindings = list(bindings)
        self.program_courses = list(program_courses or [])
        self.tasks = list(tasks or [])
        self.classes = list(classes or [])
        self.catalog = list(catalog or [])
        self.batch_ids = list(batch_ids or [])

    def query(self, *models):
        self.query_calls += 1
        return _Query(self, models)


def _program(index: int):
    return SimpleNamespace(
        id=index,
        tenant_id=1,
        is_deleted=False,
        program_name=f"软件技术2026级-{index}",
        major_id=10,
        grade_year="2026",
        status="PUBLISHED",
    )


def _binding(index: int):
    return SimpleNamespace(
        id=1000 + index,
        tenant_id=1,
        program_id=index,
        major_id=10,
        grade_year="2026",
        class_id=None,
        status="ACTIVE",
        is_deleted=False,
    )


def _run(monkeypatch, db, *, status=None):
    from app.modules.academic_affairs.services import academic_affairs_program_governance_service as service

    @contextmanager
    def _session():
        yield db

    monkeypatch.setattr(service, "session", _session)
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(service, "_scope", lambda _user, _db: SimpleNamespace(scope_type="TENANT_ALL"))
    monkeypatch.setattr(service, "_allowed_major_ids", lambda _db, _scope: set())
    return service.opening_differences(SimpleNamespace(), 9, status=status)


def test_opening_differences_source_query_count_does_not_scale_with_program_count(monkeypatch):
    one = _Db(programs=[_program(1)], bindings=[_binding(1)])
    many = _Db(
        programs=[_program(index) for index in range(1, 51)],
        bindings=[_binding(index) for index in range(1, 51)],
    )

    one_result = _run(monkeypatch, one)
    many_result = _run(monkeypatch, many)

    assert one.query_calls == many.query_calls
    assert one_result["summary"]["total"] == 1
    assert many_result["summary"]["total"] == 50
    assert many_result["summary"]["unresolved"] == 50
    assert {row["status"] for row in many_result["items"]} == {"NO_CLASS"}


def test_opening_differences_keeps_full_summary_before_status_filter(monkeypatch):
    program = _program(1)
    binding = SimpleNamespace(**{**_binding(1).__dict__, "class_id": 7})
    program_course = SimpleNamespace(
        id=31,
        tenant_id=1,
        program_id=1,
        course_id=101,
        course_name="Python程序设计",
        open_term_no=1,
        credit_snapshot=3,
        is_deleted=False,
    )
    clazz = SimpleNamespace(
        id=7,
        tenant_id=1,
        major_id=10,
        grade="2026",
        class_name="软件2601",
        class_status="NORMAL",
        is_deleted=False,
    )
    catalog = SimpleNamespace(
        id=101,
        tenant_id=1,
        course_code="PY101",
        course_name="Python程序设计",
        credit=3,
        hours_total=48,
        is_deleted=False,
    )
    ready_task = SimpleNamespace(
        id=51,
        tenant_id=1,
        batch_id=5,
        course_id=101,
        class_id=7,
        status="DRAFT",
        is_deleted=False,
        teacher_key="T001",
        teacher_name="张老师",
        total_hours=48,
        course_code="PY101",
        course_name="Python程序设计",
        teaching_class_name="软件2601",
    )
    extra_task = SimpleNamespace(
        id=52,
        tenant_id=1,
        batch_id=5,
        course_id=202,
        class_id=7,
        status="DRAFT",
        is_deleted=False,
        teacher_key="T002",
        teacher_name="李老师",
        total_hours=32,
        course_code="WEB202",
        course_name="Web开发",
        teaching_class_name="软件2601",
    )
    db = _Db(
        programs=[program],
        bindings=[binding],
        program_courses=[program_course],
        tasks=[ready_task, extra_task],
        classes=[clazz],
        catalog=[catalog],
        batch_ids=[5],
    )

    result = _run(monkeypatch, db, status="READY")

    assert result["activeFilter"] == "READY"
    assert result["filteredTotal"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["status"] == "READY"
    assert result["items"][0]["responsibility"] == "PROGRAM_COURSE"
    assert result["summary"]["total"] == 2
    assert result["summary"]["ready"] == 1
    assert result["summary"]["overOpened"] == 1
    assert result["summary"]["blockerCount"] == 1
