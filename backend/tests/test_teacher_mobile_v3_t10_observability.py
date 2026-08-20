import inspect

from app.services import mobile_observability_service as mobile_obs
from app.services import teacher_mobile_observability_v3_service as teacher_obs


def setup_function():
    mobile_obs.reset_for_tests()


def teardown_function():
    mobile_obs.reset_for_tests()


def test_t10_teacher_page_observability_is_bucketed_and_anonymous(monkeypatch):
    monkeypatch.setattr(teacher_obs, "perf_counter", lambda: 10.150)
    teacher_obs.record_page_read(
        route_key="teacher_messages",
        scope_mode="MESSAGE_CONTEXT",
        started=10.0,
    )
    metrics = mobile_obs.snapshot()["metrics"]
    assert metrics["pageLatency"] == {"<300ms": 1}
    assert metrics["scopeMode"] == {"teacher_messages:MESSAGE_CONTEXT": 1}


def test_t10_unknown_labels_fail_closed_to_fixed_tokens(monkeypatch):
    monkeypatch.setattr(teacher_obs, "perf_counter", lambda: 1.010)
    teacher_obs.record_page_read(
        route_key="张三-13800138000",
        scope_mode="studentNo=20260001",
        started=1.0,
    )
    labels = mobile_obs.snapshot()["metrics"]["scopeMode"]
    assert labels == {"unknown:UNKNOWN": 1}


def test_t10_helper_accepts_no_free_text_payload_fields():
    signature = inspect.signature(teacher_obs.record_page_read)
    assert list(signature.parameters) == ["route_key", "scope_mode", "started"]
    source = inspect.getsource(teacher_obs)
    for forbidden in ("message_content", "student_no", "real_name", "phone", "sql_params"):
        assert forbidden not in source.lower()
