"""学生毕设“当前要做”统一派生：纯函数行为测试（不依赖数据库）。"""
from app.modules.graduation.services.graduation_student_journey import build_journey


def _keys_by_state(result, state):
    return [s["key"] for s in result["steps"] if s["state"] == state]


def test_no_record_returns_empty_journey():
    result = build_journey(my={"hasData": False, "message": "你暂无毕设记录"})
    assert result["hasData"] is False
    assert result["current"] is None


def test_open_round_without_topic_asks_student_to_choose():
    result = build_journey(my={"hasData": True, "stage": "TOPIC_SELECTING"},
                           round_={"roundName": "第一轮", "myChoices": []})
    assert result["current"]["key"] == "topic"
    assert result["current"]["state"] == "todo"
    assert result["current"]["actionLabel"] == "去选题"


def test_approved_proposal_in_guiding_waits_for_midterm_not_resubmit():
    """回归：小程序曾在 GUIDING 阶段永远提示“提交开题报告”。"""
    result = build_journey(
        my={"hasData": True, "stage": "GUIDING", "hasTopic": True, "topicTitle": "课题A"},
        taskbook={"hasData": True, "status": "CONFIRMED"},
        proposal={"canSubmit": False, "latest": {"status": "APPROVED", "version": "v1"}},
        midterm={"hasData": True, "status": "PENDING"},
        final={"canSubmitDraft": False, "items": []},
    )
    assert result["current"]["key"] == "midterm"
    assert result["current"]["state"] == "waiting"
    assert "proposal" in _keys_by_state(result, "done")


def test_rejected_proposal_is_todo_with_comment():
    result = build_journey(
        my={"hasData": True, "stage": "GUIDING", "hasTopic": True},
        taskbook={"hasData": True, "status": "CONFIRMED"},
        proposal={"canSubmit": True, "latest": {"status": "REJECTED", "reviewComment": "研究方案不具体"}},
    )
    current = result["current"]
    assert current["key"] == "proposal" and current["state"] == "todo"
    assert current["returned"] is True and current["tone"] == "danger"
    assert current["comment"] == "研究方案不具体"


def test_midterm_rectify_is_todo():
    result = build_journey(
        my={"hasData": True, "stage": "MIDTERM", "hasTopic": True},
        proposal={"latest": {"status": "APPROVED"}},
        midterm={"status": "RECTIFYING", "checkComment": "进度滞后"},
    )
    assert result["current"]["key"] == "midterm"
    assert result["current"]["actionLabel"] == "去提交整改"


def test_can_submit_draft_is_current_task():
    result = build_journey(
        my={"hasData": True, "stage": "FINAL_CHECK", "hasTopic": True},
        proposal={"latest": {"status": "APPROVED"}},
        midterm={"status": "CHECKED_PASS"},
        final={"canSubmitDraft": True, "items": []},
    )
    assert result["current"]["key"] == "final"
    assert result["current"]["actionLabel"] == "去提交初稿"


def test_imported_later_stage_marks_earlier_steps_done():
    result = build_journey(my={"hasData": True, "stage": "DEFENSE", "hasTopic": True},
                           defense={"published": True, "date": "2026-05-20", "location": "A101"})
    assert _keys_by_state(result, "done")[:6] == ["topic", "taskbook", "proposal", "guidance", "midterm", "final"]
    assert result["current"]["key"] == "defense"


def test_published_grade_finishes_journey():
    result = build_journey(my={"hasData": True, "stage": "COMPLETED", "hasTopic": True},
                           grade={"published": True, "totalScore": 86, "gradeLevel": "良好"},
                           archive={"status": "FILED"})
    assert result["doneCount"] == result["total"] == 8
    assert result["current"]["key"] == "grade"


def test_midterm_fail_is_blocked_and_surfaces():
    result = build_journey(
        my={"hasData": True, "stage": "MIDTERM", "hasTopic": True},
        proposal={"latest": {"status": "APPROVED"}},
        midterm={"status": "CHECKED_FAIL", "checkComment": "未按计划完成"},
    )
    assert result["current"]["key"] == "midterm"
    assert result["current"]["state"] == "blocked"
    assert result["current"]["actionLabel"] == ""


def test_failed_section_is_reported_instead_of_a_fake_waiting_state():
    """回归：环节读取失败时不能用空数据推出“等待导师检查”等假状态。"""
    result = build_journey(
        my={"hasData": True, "stage": "MIDTERM", "hasTopic": True},
        taskbook={"hasData": True, "status": "CONFIRMED"},
        proposal={"canSubmit": False, "latest": {"status": "APPROVED"}},
        midterm=None,
        final={"items": []},
        failed=["midterm"],
    )
    midterm = next(s for s in result["steps"] if s["key"] == "midterm")
    assert midterm["loadFailed"] is True
    assert midterm["statusText"] == "暂时无法读取"
    assert midterm["actionLabel"] == ""
    assert result["current"]["key"] == "midterm"


def test_failed_round_does_not_hide_an_already_confirmed_topic():
    result = build_journey(
        my={"hasData": True, "stage": "TASKBOOK_CONFIRM", "hasTopic": True, "topicTitle": "课题A"},
        taskbook={"hasData": True, "status": "PENDING_CONFIRM"},
        failed=["round"],
    )
    topic = result["steps"][0]
    assert topic["state"] == "done" and not topic.get("loadFailed")
    assert result["current"]["key"] == "taskbook"


def test_failed_section_for_a_stage_already_passed_stays_done():
    result = build_journey(
        my={"hasData": True, "stage": "DEFENSE", "hasTopic": True},
        final={"finalApproved": True, "items": [{"status": "APPROVED"}]},
        failed=["proposal"],
    )
    proposal = next(s for s in result["steps"] if s["key"] == "proposal")
    assert proposal["state"] == "done"
