"""P0-10：十三域语义归档结构化合同。"""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


def _schedule_item(item_id, *, parity="ALL", teacher="T001", class_id=1, room=1,
                   start=1, end=16, batch=1, weekday=1, slot=1):
    return SimpleNamespace(
        id=item_id,
        batch_id=batch,
        weekday=weekday,
        slot_no=slot,
        start_week=start,
        end_week=end,
        week_parity=parity,
        teacher_key=teacher,
        class_id=class_id,
        classroom_id=room,
        classroom_text=None,
    )


def test_hard_conflict_detects_teacher_class_and_room_collision():
    from app.modules.academic_affairs.services.academic_affairs_archive_rule_evaluator import (
        hard_schedule_conflicts,
    )

    conflicts = hard_schedule_conflicts([
        _schedule_item(1),
        _schedule_item(2),
    ])

    assert len(conflicts) == 1
    assert set(conflicts[0]["kinds"]) == {"TEACHER", "CLASS", "CLASSROOM"}
    assert conflicts[0]["itemIds"] == ["1", "2"]


def test_odd_and_even_week_items_do_not_conflict():
    from app.modules.academic_affairs.services.academic_affairs_archive_rule_evaluator import (
        hard_schedule_conflicts,
    )

    conflicts = hard_schedule_conflicts([
        _schedule_item(1, parity="ODD"),
        _schedule_item(2, parity="EVEN"),
    ])

    assert conflicts == []


class _OpeningQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self.rows)


class _OpeningDb:
    def __init__(self, classes, courses):
        self.classes = classes
        self.courses = courses
        self.query_counts = {}

    def query(self, model):
        self.query_counts[model.__name__] = self.query_counts.get(model.__name__, 0) + 1
        if model.__name__ in {"SchoolClass", "StudentProfile"}:
            return _OpeningQuery(self.classes)
        if model.__name__ == "AaProgramCourse":
            return _OpeningQuery(self.courses)
        raise AssertionError(f"unexpected model: {model.__name__}")


def test_historical_opening_projection_uses_one_canonical_program_per_class(monkeypatch):
    from app.core.context import set_tenant
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as policy

    cutoff = datetime(2026, 7, 12, 23, 59)
    term = SimpleNamespace(year_code="2025-2026", term_no=2, end_date=cutoff)
    classes = [
        SimpleNamespace(id=1, major_id=10, grade="2024", college_id=2),
        SimpleNamespace(id=2, major_id=10, grade="2024", college_id=2),
    ]
    courses = [SimpleNamespace(id=91, course_id=501)]
    calls = []

    def resolve(_db, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status="RESOLVED",
            program=SimpleNamespace(id=70),
            rule="MAJOR_GRADE_HISTORICAL_EFFECTIVE",
            message="历史方案已解析",
        )

    monkeypatch.setattr(policy, "resolve_program_for_scope", resolve)
    set_tenant({"tenantId": "1"})
    opening_db = _OpeningDb(classes, courses)
    try:
        expected, structural = policy._expected_opening(
            opening_db, term
        )
    finally:
        set_tenant(None)

    assert structural == []
    assert [row["key"] for row in expected] == [(501, 1), (501, 2)]
    assert [call["class_id"] for call in calls] == [1, 2]
    assert all(call["as_of"] == cutoff for call in calls)
    assert opening_db.query_counts["AaProgramCourse"] == 1


def test_historical_program_coverage_replays_binding_at_term_end(monkeypatch):
    from app.core.context import set_tenant
    from app.modules.academic_affairs.services import academic_affairs_archive_rule_evaluator as policy

    cutoff = datetime(2026, 7, 12, 23, 59)
    student = SimpleNamespace(
        id=1, student_no="2024S0001", major_id=10, class_id=1,
        grade="2024", college_id=2, student_status="REGISTERED",
    )
    classmate = SimpleNamespace(
        id=2, student_no="2024S0002", major_id=10, class_id=1,
        grade="2024", college_id=2, student_status="REGISTERED",
    )
    captured = []

    def resolve(_db, _student, **kwargs):
        captured.append(kwargs)
        return SimpleNamespace(
            status="RESOLVED", program=SimpleNamespace(id=70),
            rule="MAJOR_GRADE_HISTORICAL_EFFECTIVE", message="历史方案已解析",
        )

    monkeypatch.setattr(policy, "resolve_student_program", resolve)
    monkeypatch.setattr(policy, "validate_program_db", lambda _db, _pid: {"issues": []})
    set_tenant({"tenantId": "1"})
    try:
        result = policy.evaluate_program(
            _OpeningDb([student, classmate], []),
            SimpleNamespace(
                id=4, year_code="2025-2026", term_no=2, end_date=cutoff,
            ),
        )
    finally:
        set_tenant(None)

    assert result["result"] == "PASS"
    assert result["recordCount"] == 2
    assert captured == [{"tenant_id": 1, "as_of": cutoff}]


def test_persisted_rule_summary_fits_existing_varchar_300_and_round_trips():
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    encoded = service._persisted_remark("GRADE", {
        "recordCount": 326,
        "present": False,
        "result": "BLOCKED",
        "ruleCode": "GRADE_TASK_UNPUBLISHED",
        "summary": "未发布成绩任务" * 100,
        "blockingCount": 8,
        "route": "/admin/academic-affairs/grade-tasks?filter=pending",
        "evidence": [{"taskId": str(i)} for i in range(100)],
    })
    parsed = service.parse_persisted_remark(
        "GRADE", encoded, present=False, record_count=326,
    )

    assert len(encoded) <= 300
    assert parsed["result"] == "BLOCKED"
    assert parsed["ruleCode"] == "GRADE_TASK_UNPUBLISHED"
    assert parsed["blockingCount"] == 8
    assert parsed["recordCount"] == 326
    assert parsed["evidence"] == []


def test_public_archive_service_is_single_explicit_entry():
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    assert service.__name__.endswith("academic_affairs_archive_service")
    assert len(service._DOMAINS) == 13
    assert {code for code, _label in service._DOMAINS} == {
        "STUDENT_STATUS", "REGISTRATION", "STATUS_CHANGE", "PROGRAM",
        "TEACHING_TASK", "SCHEDULE", "SELECTION", "EXAM", "GRADE",
        "MAKEUP", "EVALUATION", "TEXTBOOK", "GRADUATION",
    }
    assert callable(service._evaluate_domains)
    assert callable(service.run_check)
    assert callable(service.precheck)


def test_archive_precheck_page_shows_semantic_status_and_drill_route():
    root = Path(__file__).resolve().parents[2]
    source = (
        root / "frontend/src/modules/academicAffairs/views/ArchivePrecheckView.vue"
    ).read_text(encoding="utf-8")

    for field in ("blockingCount", "blockedDomains", "ruleCode", "evidence", "domain.route"):
        assert field in source
    assert "当前仍有业务阻断，暂不可归档" in source
    assert "去处理" in source
    assert "按业务完成状态判断能否归档" in source


def test_global_force_button_is_not_reintroduced():
    root = Path(__file__).resolve().parents[2]
    core = (
        root / "backend/app/modules/academic_affairs/services/academic_affairs_archive_core_service.py"
    ).read_text(encoding="utf-8")

    assert "整体强制归档已停用" in core
    assert "仅语义完整性检查通过（READY）的批次可确认归档" in core
