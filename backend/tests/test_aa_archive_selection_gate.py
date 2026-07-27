"""选课名单作为第10归档域的纯规则与真实执行器绑定回归。"""
from types import SimpleNamespace


def _batch(status):
    return SimpleNamespace(status=status)


def _round(status, mode):
    return SimpleNamespace(status=status, mode=mode)


def test_no_selection_batch_is_optional_and_does_not_block_archive():
    from app.modules.academic_affairs.services.academic_affairs_archive_selection_facade import (
        _selection_gate_result,
    )

    result = _selection_gate_result([])

    assert result["present"] is True
    assert "未启用选课" in result["remark"]


def test_open_or_closed_selection_batch_blocks_term_archive():
    from app.modules.academic_affairs.services.academic_affairs_archive_selection_facade import (
        _selection_gate_result,
    )

    result = _selection_gate_result([_batch("OPEN"), _batch("CLOSED")])

    assert result["present"] is False
    assert "未锁定/未归档选课批次 2 个" in result["remark"]


def test_closed_fcfs_round_is_terminal_but_closed_lottery_waits_for_draw():
    from app.modules.academic_affairs.services.academic_affairs_archive_selection_facade import (
        _active_round_count,
    )

    assert _active_round_count([
        _round("CLOSED", "FCFS"),
        _round("DRAWN", "LOTTERY"),
    ]) == 0
    assert _active_round_count([
        _round("DRAFT", "FCFS"),
        _round("OPEN", "FCFS"),
        _round("CLOSED", "LOTTERY"),
    ]) == 3


def test_locked_selection_still_blocks_when_round_or_roster_is_unfinished():
    from app.modules.academic_affairs.services.academic_affairs_archive_selection_facade import (
        _selection_gate_result,
    )

    result = _selection_gate_result(
        [_batch("LOCKED")],
        active_rounds=1,
        pending_records=2,
        count_mismatches=3,
        missing_task_courses=4,
    )

    assert result["present"] is False
    assert "未终结选课轮次 1 个" in result["remark"]
    assert "未转正式名单记录 2 条" in result["remark"]
    assert "不一致 3 门" in result["remark"]
    assert "未关联教学任务的有效课程 4 门" in result["remark"]


def test_locked_or_archived_selection_with_consistent_roster_passes():
    from app.modules.academic_affairs.services.academic_affairs_archive_selection_facade import (
        _selection_gate_result,
    )

    result = _selection_gate_result([_batch("LOCKED"), _batch("ARCHIVED")])

    assert result["present"] is True


def test_selection_domain_is_bound_to_canonical_archive_executor():
    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    assert service.__name__.endswith("academic_affairs_archive_service")
    assert any(code == "SELECTION" for code, _label in service._DOMAINS)
    assert any(code == "SELECTION" for code, _label in service._policy.DOMAINS)
    assert callable(service._evaluate_domains)
