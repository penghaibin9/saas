from app.modules.platform.services import platform_access_governance_runtime as pam


def test_stable_replay_comparison_accepts_same_client_command():
    existing = {
        "requestId": "req-12345678",
        "userId": "u1",
        "durationMinutes": 30,
        "reason": "incident support",
        "capabilities": ["support.request", "tenant.view"],
        "startsAt": "volatile",
    }
    expected = {
        "requestId": "req-12345678",
        "userId": "u1",
        "durationMinutes": 30,
        "reason": "incident support",
        "capabilities": ["tenant.view", "support.request"],
    }
    assert pam._same_or_conflict(
        existing, expected,
        fields=("requestId", "userId", "durationMinutes", "reason", "capabilities"),
    ) == existing


def test_stable_replay_comparison_rejects_request_id_reuse_for_different_command():
    existing = {"requestId": "req-12345678", "userId": "u1", "durationMinutes": 30}
    expected = {"requestId": "req-12345678", "userId": "u2", "durationMinutes": 30}
    try:
        pam._same_or_conflict(existing, expected, fields=("requestId", "userId", "durationMinutes"))
    except Exception as exc:
        assert getattr(exc, "code", "IDEMPOTENCY_CONFLICT") == "IDEMPOTENCY_CONFLICT" or "requestId" in str(exc)
    else:
        raise AssertionError("requestId reuse with changed payload must fail closed")
