"""按真实周窗核验计划课时；替身仅验证计算，不冒充 MySQL 或页面验收。"""
from types import SimpleNamespace as Row

import pytest

from app.modules.academic_affairs.services import academic_affairs_schedule_gate_service as gate


def task(**values):
    return Row(**{"id": 1, "course_id": 10, "course_name": "周次测试课",
                 "weekly_hours": 2, "total_hours": 36, "start_week": 1,
                 "end_week": 18, **values})


def item(start=1, end=18, parity="ALL", **values):
    return Row(**{"id": 1, "task_id": 1, "weekday": 1, "slot_no": 1,
                 "start_week": start, "end_week": end, "week_parity": parity,
                 "classroom_id": None, **values})


class Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_):
        return self

    join = order_by = filter

    def populate_existing(self):
        return self

    with_for_update = populate_existing

    def all(self):
        return self.rows


def evaluate(monkeypatch, tasks, items):
    from app.models import AaTeachingTaskBatch, AaTeachingTask, AaScheduleItem, AaCourse, AaClassroom

    rows = {AaTeachingTaskBatch: [Row(id=1)], AaTeachingTask: tasks,
            AaScheduleItem: items, AaCourse: [Row(id=t.course_id) for t in tasks],
            AaClassroom: []}
    db = Row(query=lambda model: Query(rows[model]))
    monkeypatch.setattr(gate, "_tid", lambda: 1)
    monkeypatch.setattr(gate.policy, "term_bounds", lambda *_: (Row(id=1), 18))
    monkeypatch.setattr(gate.policy, "task_scope_condition", lambda *_args, **_kwargs: True)
    # 本夹具只核周次计算；承接与责任 SQL 由真实 MySQL 用例覆盖。
    monkeypatch.setattr(gate, "load_execution_handoffs", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(gate, "_responsible_task_ids", lambda _db, ids, *_args, **_kwargs: set(ids))
    monkeypatch.setattr(gate.scheduling_service, "conflict_report_in_session", lambda *_: {
        "hardCount": 0, "softCount": 0, "hardConflicts": [], "softConflicts": []})
    return gate.evaluate(db, Row(id=1, term_id=1, college_id=12, status="DRAFT"))


def test_two_future_rows_do_not_cover_full_term(monkeypatch):
    result = evaluate(monkeypatch, [task()], [item(6, 18), item(6, 18, id=2, slot_no=2)])
    assert result["complete"] is False
    assert result["scheduledContactHours"] == 26
    assert result["missingContactHours"] == 10


@pytest.mark.parametrize("authoritative_count", [0, 1])
def test_duplicate_task_gate_reuses_opening_reconciliation(monkeypatch, authoritative_count):
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as evaluator

    group = {"courseId": "10", "classId": "9", "taskIds": ["1", "2"]}
    monkeypatch.setattr(evaluator, "evaluate_teaching_task", lambda *_args, **_kwargs: {
        "duplicateTaskGroupCount": authoritative_count,
        "duplicateTaskGroups": [group] if authoritative_count else [],
    })
    rows = [item(id=1), item(id=2, slot_no=2),
            item(id=3, task_id=2, weekday=2), item(id=4, task_id=2, weekday=2, slot_no=2)]
    result = evaluate(monkeypatch, [task(class_id=9), task(id=2, class_id=9)], rows)
    assert result["scheduledContactHours"] == result["expectedContactHours"] == 72
    assert result["missingContactHours"] == 0
    assert result["complete"] is (authoritative_count == 0)
    assert result["duplicateTaskGroupCount"] == authoritative_count
    assert result["canPrePublish"] is (authoritative_count == 0)
    assert {row["taskId"] for row in result["duplicateTasks"]} == ({"1", "2"} if authoritative_count else set())


def test_same_course_in_different_classes_does_not_require_duplicate_reconciliation(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as evaluator

    def unexpected(*_args, **_kwargs):
        pytest.fail("不同班级不应作为同班重复任务核对")

    monkeypatch.setattr(evaluator, "evaluate_teaching_task", unexpected)
    rows = [item(id=1), item(id=2, slot_no=2),
            item(id=3, task_id=2, weekday=2), item(id=4, task_id=2, weekday=2, slot_no=2)]
    result = evaluate(monkeypatch, [task(class_id=9), task(id=2, class_id=10)], rows)
    assert result["complete"] is True
    assert result["duplicateTaskGroupCount"] == 0


@pytest.mark.parametrize("rows", [
    [item(1, 9), item(10, 18, id=2), item(1, 9, id=3, slot_no=2), item(10, 18, id=4, slot_no=2)],
    [item(1, 18, "ODD"), item(1, 18, "EVEN", id=2),
     item(1, 18, "ODD", id=3, slot_no=2), item(1, 18, "EVEN", id=4, slot_no=2)],
], ids=["split-weeks", "complementary-parity"])
def test_complementary_rows_cover_same_task_without_exceeding_weekly_limit(monkeypatch, rows):
    result = evaluate(monkeypatch, [task()], rows)
    assert result["complete"] is True
    assert result["scheduledContactHours"] == 36
    assert result["weeklyOverloadCount"] == 0
    assert result["scheduledItemCount"] == 4


def test_short_task_window_and_rounded_weekly_hours_are_valid(monkeypatch):
    result = evaluate(monkeypatch, [task(start_week=3, end_week=8, total_hours=11)],
                      [item(3, 8), item(3, 7, id=2, slot_no=2)])
    assert result["complete"] is True
    assert result["expectedContactHours"] == result["scheduledContactHours"] == 11


@pytest.mark.parametrize("bad_item", [item(2, 2, "ODD"), item(1, 18, "BROKEN"), item(1, 18)],
                         ids=["no-active-week", "invalid-parity", "outside-task-window"])
def test_invalid_coordinates_cannot_publish_even_with_one_row(monkeypatch, bad_item):
    result = evaluate(monkeypatch, [task(weekly_hours=1, total_hours=9, end_week=9)], [bad_item])
    assert result["complete"] is False
    assert result["invalidCoordinateItemCount"] == 1


@pytest.mark.parametrize("total", [0, -1, 37])
def test_explicit_invalid_or_unreachable_total_does_not_use_legacy_fallback(monkeypatch, total):
    result = evaluate(monkeypatch, [task(total_hours=total)], [item(), item(id=2, slot_no=2)])
    assert result["complete"] is False
    assert result["invalidTaskCount"] == 1


def test_nullable_legacy_total_has_explicit_derivation_basis(monkeypatch):
    result = evaluate(monkeypatch, [task(total_hours=None)], [item(), item(id=2, slot_no=2)])
    assert result["complete"] is True
    assert result["derivedTotalTaskCount"] == 1
    assert result["expectedContactHours"] == 36


def test_week_overload_blocks_even_when_total_is_exact(monkeypatch):
    rows = [item(1, 6, id=i, slot_no=i) for i in range(1, 4)]
    result = evaluate(monkeypatch, [task(total_hours=18)], rows)
    assert result["complete"] is False
    assert result["excessContactHours"] == 0
    assert result["missingContactHours"] == 0
    assert result["weeklyOverloadCount"] == 6


def test_missing_and_excess_are_summed_per_task_without_cancellation(monkeypatch):
    tasks = [task(id=1), task(id=2, course_id=11), task(id=3, course_id=12)]
    rows = [item(task_id=3, id=i, slot_no=i) for i in range(1, 4)]
    result = evaluate(monkeypatch, tasks, rows)
    assert result["missingTaskCount"] == 2
    assert result["missingContactHours"] == 72
    assert result["excessContactHours"] == 18
    assert result["weeklyOverloadCount"] == 18
    assert result["complete"] is False


def test_correction_receipt_does_not_offset_missing_rows_with_excess(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as final

    monkeypatch.setattr(final.gate_service, "evaluate", lambda *_: {
        "expectedSessions": 10, "scheduledSessions": 9,
        "missingTasks": [{"expectedSessions": 2, "scheduledSessions": 0},
                         {"expectedSessions": 2, "scheduledSessions": 0}],
        "expectedContactHours": 180, "scheduledContactHours": 162,
        "missingContactHours": 72, "excessContactHours": 54,
        "weeklyOverloadCount": 18, "scheduledItemCount": 9,
    })
    result = final._correction_result(None, Row(id=1, status="DRAFT"), 2)
    assert result["remainingSessions"] == 4
    assert result["missingContactHours"] == 72
    assert result["scheduledItemCount"] == 9


@pytest.mark.parametrize("total,rows", [
    (35, []), (36, [item(6, 18), item(6, 18, id=2, slot_no=2)]),
    (18, [item(1, 18, "ODD")]),
])
def test_auto_segments_fill_exact_remaining_hours_without_weekly_overload(total, rows):
    from app.modules.academic_affairs.services import academic_affairs_schedule_policy as policy

    target = task(total_hours=total, weekly_hours=1 if total == 18 else 2)
    before = policy.task_coverage(target, rows, 18)
    segments = policy.missing_week_segments(target, before)
    candidates = [item(start, end, id=100 + index, slot_no=index + 1)
                  for index, (count, start, end) in enumerate(segments) for _ in range(count)]
    after = policy.task_coverage(target, [*rows, *candidates], 18)
    assert after["scheduledContactHours"] == total
    assert after["missingContactHours"] == after["excessContactHours"] == 0
    assert after["weeklyOverloadCount"] == 0


def test_mysql_segmented_import_is_atomic_and_uses_contact_hour_gate(client, db_mode):
    from tests.test_aa_schedule_import_batch_queries import _seed, _ctx, _clear_ctx
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, College, AaScheduleItem, AaScheduleBatch
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as final

    ids = _seed(weekly_hours=1)
    user = _ctx()
    try:
        with get_sessionmaker()() as db:
            college = College(tenant_id=1000000000000000001, college_name="周次测试学院", status="ACTIVE")
            db.add(college); db.flush()
            db.add(AaCourse(id=99101, tenant_id=1000000000000000001, course_code="WEEK99101",
                           course_name="周次测试课", owner_college_id=college.id))
            db.commit()
        rows = [{"taskId": str(ids["task_id"]), "weekday": 1, "slotNo": 1,
                 "startWeek": 1, "endWeek": 18, "weekParity": parity,
                 "classroom": "D5U-A101"} for parity in ("ODD", "EVEN")]
        excess = {**rows[0], "weekday": 2, "weekParity": "ALL"}
        preview = final.import_dry_run(ids["batch_id"], user, [*rows, excess])
        assert preview["validRows"] == 2 and preview["invalidRows"] == 1
        assert preview["errors"][0]["code"] == "DATA_CONFLICT"
        assert preview["errors"][0]["details"]["excessContactHours"] == 18
        assert preview["errors"][0]["details"]["weeklyOverloadCount"] == 18
        with get_sessionmaker()() as db:
            assert db.query(AaScheduleItem).filter(AaScheduleItem.batch_id == ids["batch_id"]).count() == 0
        final.import_items(ids["batch_id"], user, rows)
        with get_sessionmaker()() as db:
            batch = db.get(AaScheduleBatch, ids["batch_id"])
            result = gate.evaluate(db, batch)
            assert result["complete"] is True
            assert result["scheduledContactHours"] == 18
            items = db.query(AaScheduleItem).filter(AaScheduleItem.batch_id == batch.id).all()
            original_id = items[0].id
        from app.core.exceptions import AppException
        with pytest.raises(AppException) as rejected:
            final.adjust_item(ids["batch_id"], original_id, user, 2, 1, "D5U-A101", "ALL")
        assert rejected.value.code == "DATA_CONFLICT"
        assert rejected.value.http_status == 409
        assert rejected.value.details["excessContactHours"] == 9
        assert rejected.value.details["weeklyOverloadCount"] == 9
        with get_sessionmaker()() as db:
            assert db.get(AaScheduleItem, original_id).week_parity == "ODD"
        result = final.pre_publish(ids["batch_id"], user)
        assert result["status"] == "PRE_PUBLISHED"
    finally:
        _clear_ctx()


def test_disjoint_weeks_do_not_accumulate_daily_limit_but_same_week_does():
    from app.modules.academic_affairs.services import academic_affairs_autoschedule_final_service as auto

    grid = auto._base._Grid()
    target = task(teacher_key="week_teacher", class_id=9, required_room_type="LECTURE")
    room = Row(id=1, room_type="LECTURE")
    params = {"weekdays": [1], "slots": [1, 2], "teacherMaxPerDay": 1,
              "classMaxPerDay": 1, "respectAvail": False, "roomTypeMatch": True}
    grid.occupy(target.teacher_key, target.class_id, room.id, 1, 1, 1, 18, "ODD")
    for week in range(2, 19, 2):
        placed, reason = auto._base._place_task(target, 1, week, week, "ALL", params,
                                               set(), grid, [room], [room], set())
        assert len(placed) == 1 and reason == ""
    placed, reason = auto._base._place_task(target, 1, 2, 2, "ALL", params,
                                           set(), grid, [room], [room], set())
    assert placed == [] and reason == "DAY_LIMIT"


@pytest.mark.parametrize("complete_manual_segments", [False, True])
def test_optimizer_context_reports_remaining_hours_instead_of_row_count_completion(monkeypatch, complete_manual_segments):
    from contextlib import contextmanager
    from app.modules.academic_affairs.services import schedule_optimizer_jobs_service as jobs

    @contextmanager
    def session():
        yield None

    target = vars(task(weekly_hours=1, total_hours=18) if complete_manual_segments else task())
    target["expected_students"] = 1
    segments = [(1, 9), (10, 18)] if complete_manual_segments else [(6, 18), (6, 18)]
    rows = [{**vars(item(start, end, id=i, slot_no=i)), "batch_id": 1, "source": "MANUAL"}
            for i, (start, end) in enumerate(segments, 1)]
    facts = {"targetTaskIds": ["1"], "tasks": [target], "existingItems": rows,
             "term": {"teaching_weeks": 18}, "scope": {}, "batch": {"status": "DRAFT"},
             "teachers": {"1": ["teacher1"]}, "rosters": {"1": {"teachingClassId": "9"}},
             "rooms": [], "slots": [], "events": []}
    monkeypatch.setattr(jobs, "session", session)
    monkeypatch.setattr(jobs, "_authorize", lambda *_: "DRAFT")
    monkeypatch.setattr(jobs, "_enabled", lambda: True)
    monkeypatch.setattr(jobs, "capture_source", lambda *_: (facts, "revision"))
    result = jobs.context({}, 1)
    assert result["tasks"][0]["remainingPeriods"] == 0
    assert result["tasks"][0]["missingContactHours"] == (0 if complete_manual_segments else 10)
    assert result["tasks"][0]["excessContactHours"] == 0
    assert result["tasks"][0]["weeklyOverloadCount"] == 0
    assert result["tasks"][0]["autoPeriods"] == 0
    assert result["tasks"][0]["optimizerSupported"] is False
    assert result["canGenerate"] is False
    assert result["blockers"][0]["message"]


def test_mysql_auto_schedule_obeys_non_divisible_total_and_is_idempotent(client, db_mode):
    from tests.test_aa_schedule_import_batch_queries import _seed, _ctx, _clear_ctx
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaScheduleItem
    from app.modules.academic_affairs.services import academic_affairs_autoschedule_final_service as auto
    from app.modules.academic_affairs.services import academic_affairs_schedule_policy as policy

    ids = _seed(weekly_hours=2)
    user = _ctx()
    try:
        with get_sessionmaker()() as db:
            db.get(AaTeachingTask, ids["task_id"]).total_hours = 35
            db.commit()
        preview = auto.auto_schedule(user, ids["batch_id"], dry_run=True)
        assert preview["placedSessions"] == 2 and preview["placedTasks"] == 1
        with get_sessionmaker()() as db:
            assert db.query(AaScheduleItem).filter(AaScheduleItem.batch_id == ids["batch_id"]).count() == 0
        result = auto.auto_schedule(user, ids["batch_id"])
        assert result["placedSessions"] == 2
        with get_sessionmaker()() as db:
            target = db.get(AaTeachingTask, ids["task_id"])
            rows = db.query(AaScheduleItem).filter(AaScheduleItem.batch_id == ids["batch_id"]).all()
            coverage = policy.task_coverage(target, rows, 18)
            assert coverage["scheduledContactHours"] == 35
            assert coverage["weeklyOverloadCount"] == 0
        again = auto.auto_schedule(user, ids["batch_id"])
        assert again["placedSessions"] == 0
    finally:
        _clear_ctx()


def test_mysql_concurrent_adds_cannot_both_consume_last_weekly_capacity(db_mode):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from tests.test_aa_schedule_import_batch_queries import _seed, _ctx, _clear_ctx
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem, AaTeachingTask
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as final
    from app.modules.academic_affairs.services import academic_affairs_schedule_policy as policy

    ids = _seed(weekly_hours=1)
    start = Barrier(2)

    def add(weekday):
        user = _ctx()
        try:
            start.wait(timeout=10)
            try:
                final.add_item(ids["batch_id"], user, {
                    "taskId": str(ids["task_id"]), "weekday": weekday, "slotNo": 1,
                    "startWeek": 1, "endWeek": 18, "weekParity": "ALL", "classroom": "D5U-A101",
                })
                return "ADDED"
            except AppException as exc:
                assert exc.code == "DATA_CONFLICT" and exc.http_status == 409
                assert exc.details["excessContactHours"] == 18
                assert exc.details["weeklyOverloadCount"] == 18
                return "REJECTED"
        finally:
            _clear_ctx()

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(add, (1, 2)))
    assert sorted(results) == ["ADDED", "REJECTED"]
    with get_sessionmaker()() as db:
        target = db.get(AaTeachingTask, ids["task_id"])
        rows = db.query(AaScheduleItem).filter(AaScheduleItem.batch_id == ids["batch_id"]).all()
        assert len(rows) == 1
        coverage = policy.task_coverage(target, rows, 18)
        assert coverage["scheduledContactHours"] == 18
        assert coverage["missingContactHours"] == coverage["excessContactHours"] == 0
        assert coverage["weeklyOverloadCount"] == 0
