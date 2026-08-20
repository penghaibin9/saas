"""V3 §13 可观测性门禁（深审 P1-13）：指标齐全、只记匿名维度、真实链路会打点。"""
from __future__ import annotations

import pytest

from app.services import mobile_action_service as actions
from app.services import mobile_observability_service as obs


@pytest.fixture(autouse=True)
def _reset():
    obs.reset_for_tests()
    yield
    obs.reset_for_tests()


def test_every_metric_the_manual_requires_is_registered():
    required = {
        "packageBytes", "firstReady", "cacheHit", "queryCount", "unknownAction",
        "focusFail", "conflict409", "pageLatency", "fileScanBind", "wechatDelivery", "scopeMode",
    }
    assert required <= set(obs.REQUIRED_METRICS)
    assert required <= set(obs.snapshot()["metrics"])


def test_unregistered_metric_fails_loudly():
    with pytest.raises(ValueError):
        obs.record("not_a_metric", "x")


def test_labels_are_reduced_to_short_anonymous_tokens():
    """标签里绝不能带进姓名、手机号、正文这类东西。"""
    obs.record("scopeMode", "张三 13800138000 <script>alert(1)</script>")
    labels = list(obs.snapshot()["metrics"]["scopeMode"])
    assert len(labels) == 1
    label = labels[0]
    assert len(label) <= 64
    for forbidden in ("张", "<", ">", " ", "(", ")"):
        assert forbidden not in label, f"标签泄漏了 {forbidden!r}"


def test_latency_is_bucketed_not_recorded_precisely():
    obs.record_latency("pageLatency", 123.456)
    obs.record_latency("pageLatency", 4999)
    obs.record_latency("pageLatency", 60000)
    buckets = obs.snapshot()["metrics"]["pageLatency"]
    assert set(buckets) == {"<300ms", "<5000ms", ">=5000ms"}
    assert "123" not in "".join(buckets), "不得记录精确耗时"


def test_query_count_is_bucketed_against_the_home_budget():
    for count, expected in [(0, "0"), (3, "<=5"), (12, "<=15"), (18, "<=20"), (25, ">20")]:
        obs.reset_for_tests()
        obs.record_home_read(cache_hit=False, query_count=count, duration_ms=10)
        assert expected in obs.snapshot()["metrics"]["queryCount"]


def test_cache_hit_path_records_zero_queries():
    obs.record_home_read(cache_hit=True, query_count=0, duration_ms=5)
    metrics = obs.snapshot()["metrics"]
    assert metrics["cacheHit"] == {"hit": 1}
    assert metrics["queryCount"] == {"0": 1}


# ── 真实链路会打点 ──

def test_unresolvable_action_is_counted_per_client():
    actions.build_message_action("totally.unknown", {"x": 1}, client=actions.CLIENT_STUDENT_MINI)
    actions.build_message_action("teacher.internship.risk", {"riskId": "9"},
                                 client=actions.CLIENT_STUDENT_MINI)
    counted = obs.snapshot()["metrics"]["unknownAction"]
    assert counted, "未解析的 action 必须留痕，否则 P0-02 复发只能靠用户投诉发现"
    assert all(key.startswith("studentMini:") for key in counted), "必须能按端归因"


def test_focus_outcome_is_counted_for_object_level_targets():
    actions.build_todo_action(
        {"todoType": "LEAVE_APPROVAL", "recordId": "1", "allowedActions": ["OPEN"]},
        client=actions.CLIENT_STUDENT_MINI,
    )
    counted = obs.snapshot()["metrics"]["focusFail"]
    assert any(key.endswith(":ok") for key in counted)

    obs.reset_for_tests()
    # 目标页没有聚焦能力时必须记成 miss —— 这就是 P0-03 的早期信号
    actions.build_todo_action(
        {"todoType": "INTERN_WEEKLY_REVIEW", "recordId": "1", "allowedActions": ["OPEN"]},
        client=actions.CLIENT_STUDENT_MINI,
    )
    counted = obs.snapshot()["metrics"]["focusFail"]
    assert any(key.endswith(":miss") for key in counted)


def test_snapshot_is_safe_to_export():
    obs.record_wechat_delivery(scene="CASE_RESULT", outcome="WECHAT_NOT_CONFIGURED")
    obs.record_file_binding(purpose="CAMPUS_SERVICE_WORKORDER", outcome="bound")
    snapshot = obs.snapshot()
    assert snapshot["schema"] == "miniapp-v3-observability/1"
    serialised = str(snapshot)
    for forbidden in ("openid", "phone", "idCard", "password"):
        assert forbidden not in serialised
