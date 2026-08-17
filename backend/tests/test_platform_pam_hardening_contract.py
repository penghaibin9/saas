import pytest

from app.core.exceptions import AppException
from app.modules.platform.services import platform_access_governance_hardening as pam


def test_review_close_rejects_missing_and_unknown_decisions(monkeypatch):
    review = {
        "id": "review-1",
        "status": "OPEN",
        "items": [
            {"itemKey": "A:0:1"},
            {"itemKey": "S:7:2"},
        ],
    }
    monkeypatch.setattr(pam._runtime, "list_records", lambda *_args, **_kwargs: [review])
    monkeypatch.setattr(
        pam._runtime,
        "close_access_review",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not reach writer")),
    )

    with pytest.raises(AppException) as exc:
        pam.close_access_review(
            "review-1",
            {"decisions": [{"itemKey": "A:0:1", "decision": "KEEP"}]},
            actor={"userId": "p-1"},
        )
    assert getattr(exc.value, "biz_code", getattr(exc.value, "code", "")) == "ACCESS_REVIEW_DECISION_SET_MISMATCH"

    with pytest.raises(AppException):
        pam.close_access_review(
            "review-1",
            {
                "decisions": [
                    {"itemKey": "A:0:1", "decision": "KEEP"},
                    {"itemKey": "S:7:2", "decision": "REVOKE"},
                    {"itemKey": "UNKNOWN", "decision": "KEEP"},
                ]
            },
            actor={"userId": "p-1"},
        )


def test_review_close_rejects_duplicate_item_key(monkeypatch):
    monkeypatch.setattr(pam._runtime, "list_records", lambda *_args, **_kwargs: [])
    with pytest.raises(AppException):
        pam.close_access_review(
            "review-1",
            {
                "decisions": [
                    {"itemKey": "A:0:1", "decision": "KEEP"},
                    {"itemKey": "A:0:1", "decision": "REVOKE"},
                ]
            },
            actor={"userId": "p-1"},
        )


def test_review_close_forwards_exact_decision_set(monkeypatch):
    review = {
        "id": "review-1",
        "status": "OPEN",
        "items": [{"itemKey": "A:0:1"}, {"itemKey": "S:7:2"}],
    }
    monkeypatch.setattr(pam._runtime, "list_records", lambda *_args, **_kwargs: [review])
    seen = {}

    def close(review_id, payload, *, actor):
        seen.update(review_id=review_id, payload=payload, actor=actor)
        return {"id": review_id, "status": "CLOSED"}

    monkeypatch.setattr(pam._runtime, "close_access_review", close)
    out = pam.close_access_review(
        "review-1",
        {
            "expectedVersion": 3,
            "reason": "quarterly review complete",
            "decisions": [
                {"itemKey": "A:0:1", "decision": "KEEP"},
                {"itemKey": "S:7:2", "decision": "REVOKE"},
            ],
        },
        actor={"userId": "p-1"},
    )
    assert out["status"] == "CLOSED"
    assert seen["payload"]["expectedVersion"] == 3


def test_cross_operator_support_termination_requires_access_manage(monkeypatch):
    monkeypatch.setattr(
        pam._runtime,
        "list_records",
        lambda *_args, **_kwargs: [{"id": "s-1", "operatorUserId": "p-owner"}],
    )
    called = []
    monkeypatch.setattr(
        pam._runtime,
        "assert_platform_capability",
        lambda actor, cap: called.append((actor["userId"], cap)),
    )
    monkeypatch.setattr(
        pam._runtime,
        "terminate_record",
        lambda *_args, **_kwargs: {"status": "TERMINATED"},
    )

    out = pam.terminate_record(
        pam.SUPPORT,
        "s-1",
        tenant_id=7,
        expected_version=2,
        reason="security stop",
        actor={"userId": "p-admin"},
    )
    assert out["status"] == "TERMINATED"
    assert called == [("p-admin", "access.manage")]


def test_owner_can_terminate_own_support_without_extra_access_manage(monkeypatch):
    monkeypatch.setattr(
        pam._runtime,
        "list_records",
        lambda *_args, **_kwargs: [{"id": "s-1", "operatorUserId": "p-owner"}],
    )
    monkeypatch.setattr(
        pam._runtime,
        "assert_platform_capability",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("owner termination must not require access.manage")),
    )
    monkeypatch.setattr(
        pam._runtime,
        "terminate_record",
        lambda *_args, **_kwargs: {"status": "TERMINATED"},
    )

    out = pam.terminate_record(
        pam.SUPPORT,
        "s-1",
        tenant_id=7,
        expected_version=2,
        reason="work complete",
        actor={"userId": "p-owner"},
    )
    assert out["status"] == "TERMINATED"
