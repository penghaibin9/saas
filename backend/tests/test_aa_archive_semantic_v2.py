"""P0-10：十三域语义归档结构化合同。"""
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
    assert "当前不可归档" in source
    assert "去处理" in source
    assert "按业务完成状态判断能否归档" in source


def test_global_force_button_is_not_reintroduced():
    root = Path(__file__).resolve().parents[2]
    core = (
        root / "backend/app/modules/academic_affairs/services/academic_affairs_archive_core_service.py"
    ).read_text(encoding="utf-8")

    assert "整体强制归档已停用" in core
    assert "仅语义完整性检查通过（READY）的批次可确认归档" in core
