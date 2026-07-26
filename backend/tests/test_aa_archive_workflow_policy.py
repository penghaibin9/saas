"""课表、考务、成绩工作流归档语义回归。"""
from types import SimpleNamespace


def _batch(row_id, status):
    return SimpleNamespace(id=row_id, status=status)


def test_schedule_published_and_formal_archived_are_valid_final_versions():
    from app.modules.academic_affairs.services.academic_affairs_archive_policy_facade import (
        _schedule_gate_result,
    )

    result = _schedule_gate_result([
        _batch(1, "PUBLISHED"),
        _batch(2, "ARCHIVED"),
    ])

    assert result["present"] is True
    assert "正式发布 1 个" in result["remark"]
    assert "正式归档 1 个" in result["remark"]


def test_schedule_pre_published_always_blocks_even_with_old_published_version():
    from app.modules.academic_affairs.services.academic_affairs_archive_policy_facade import (
        _schedule_gate_result,
    )

    result = _schedule_gate_result([
        _batch(1, "PUBLISHED"),
        _batch(2, "PRE_PUBLISHED"),
    ])

    assert result["present"] is False
    assert "预发布批次 1 个" in result["remark"]


def test_schedule_only_drafts_block_but_historical_draft_does_not_override_final():
    from app.modules.academic_affairs.services.academic_affairs_archive_policy_facade import (
        _schedule_gate_result,
    )

    only_draft = _schedule_gate_result([_batch(1, "DRAFT")])
    with_final = _schedule_gate_result([
        _batch(1, "DRAFT"),
        _batch(2, "PUBLISHED"),
    ])

    assert only_draft["present"] is False
    assert "仅有草稿批次" in only_draft["remark"]
    assert with_final["present"] is True
    assert "历史草稿 1 个" in with_final["remark"]


def test_schedule_only_voided_requires_replacement_but_voided_history_is_allowed_after_reissue():
    from app.modules.academic_affairs.services.academic_affairs_archive_policy_facade import (
        _schedule_gate_result,
    )

    only_voided = _schedule_gate_result(
        [_batch(1, "ARCHIVED")],
        voided_batch_ids={1},
    )
    reissued = _schedule_gate_result(
        [_batch(1, "ARCHIVED"), _batch(2, "PUBLISHED")],
        voided_batch_ids={1},
    )

    assert only_voided["present"] is False
    assert "必须先发布替代课表" in only_voided["remark"]
    assert reissued["present"] is True
    assert "作废批次 1 个" in reissued["remark"]


def test_schedule_inflight_change_blocks_archive():
    from app.modules.academic_affairs.services.academic_affairs_archive_policy_facade import (
        _schedule_gate_result,
    )

    result = _schedule_gate_result([_batch(1, "PUBLISHED")], active_changes=2)

    assert result["present"] is False
    assert "在途调停课 2 条" in result["remark"]


def test_exam_gate_requires_terminal_batch_attendance_defer_and_incident_closure():
    from app.modules.academic_affairs.services.academic_affairs_archive_policy_facade import (
        _exam_gate_result,
    )

    result = _exam_gate_result(
        [_batch(1, "FINISHED")],
        active_defers=1,
        pending_courses=2,
        not_started_seats=3,
        unresolved_incidents=4,
        active_course_count=5,
    )

    assert result["present"] is False
    assert "待确认考试课程 2 门" in result["remark"]
    assert "未登记到考状态考生 3 人" in result["remark"]
    assert "在途缓考申请 1 条" in result["remark"]
    assert "未闭环考场异常 4 条" in result["remark"]


def test_exam_finished_or_archived_is_valid_only_after_all_details_close():
    from app.modules.academic_affairs.services.academic_affairs_archive_policy_facade import (
        _exam_gate_result,
    )

    result = _exam_gate_result(
        [_batch(1, "FINISHED"), _batch(2, "ARCHIVED")],
        active_course_count=6,
    )

    assert result["present"] is True


def test_grade_change_running_blocks_even_when_tasks_published():
    from app.modules.academic_affairs.services.academic_affairs_archive_policy_facade import (
        _grade_gate_result,
    )

    result = _grade_gate_result(
        [_batch(1, "PUBLISHED")],
        active_changes=1,
    )

    assert result["present"] is False
    assert "在途成绩更正 1 条" in result["remark"]


def test_public_archive_service_points_to_policy_facade():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_archive_service.__name__.endswith(
        "academic_affairs_archive_policy_facade"
    )
