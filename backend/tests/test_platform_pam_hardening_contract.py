import pytest

from app.core.exceptions import AppException
from app.modules.platform.services import platform_access_governance_hardening as pam


def test_review_create_rejects_client_snapshot_injection_before_reads(monkeypatch):
    monkeypatch.setattr(
        pam,
        "_bounded_review_records",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must reject before authority reads")),
    )
    with pytest.raises(AppException) as exc:
        pam.create_access_review(
            {"requestId": "review-0001", "items": [{"itemKey": "fake"}]},
            actor={"userId": "p-1"},
        )
    assert getattr(exc.value, "biz_code", getattr(exc.value, "code", "")) == "ACCESS_REVIEW_SCOPE_INVALID"


def test_review_create_filters_server_snapshot_by_exact_scope(monkeypatch):
    monkeypatch.setenv("PLATFORM_ACCESS_REVIEW_MAX_ITEMS", "5")
    monkeypatch.setattr(pam._runtime, "assert_recent_platform_auth", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(pam._runtime, "_existing", lambda *_args, **_kwargs: None)
    rows = {
        pam._runtime.ASSIGNMENT: [{"id": "a-1", "tenantId": 0, "status": "ACTIVE", "version": 1}],
        pam._runtime.ELEVATION: [{"id": "e-1", "tenantId": 0, "status": "ACTIVE", "version": 2}],
        pam._runtime.SUPPORT: [
            {"id": "s-7", "tenantId": 7, "status": "ACTIVE", "version": 3},
            {"id": "s-8", "tenantId": 8, "status": "ACTIVE", "version": 4},
            {"id": "s-old", "tenantId": 7, "status": "TERMINATED", "version": 5},
        ],
    }
    seen = {}
    reads = []

    def bounded(config_type, *, tenant_ids, limit):
        reads.append((config_type, list(tenant_ids), limit))
        return list(rows[config_type])

    monkeypatch.setattr(pam, "_bounded_review_records", bounded)

    def save(config_type, data, **kwargs):
        seen.update(config_type=config_type, data=data, kwargs=kwargs)
        return data

    monkeypatch.setattr(pam._runtime._base, "_save_atomic", save)
    out = pam.create_access_review(
        {
            "requestId": "review-0002",
            "name": "tenant 7 support review",
            "scope": {"configTypes": [pam._runtime.SUPPORT], "tenantIds": [7]},
        },
        actor={"userId": "p-1"},
    )
    assert [item["recordId"] for item in out["items"]] == ["s-7"]
    assert out["scope"] == {"configTypes": [pam._runtime.SUPPORT], "tenantIds": [7]}
    assert out["maxItemsAtCreate"] == 5
    assert reads == [(pam._runtime.SUPPORT, [7], 6)]
    assert seen["kwargs"]["create_idempotent"] is True


def test_review_create_rejects_over_limit_before_campaign_write(monkeypatch):
    monkeypatch.setenv("PLATFORM_ACCESS_REVIEW_MAX_ITEMS", "1")
    monkeypatch.setattr(pam._runtime, "assert_recent_platform_auth", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(pam._runtime, "_existing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        pam,
        "_bounded_review_records",
        lambda config_type, **_kwargs: [
            {"id": "s-1", "tenantId": 7, "status": "ACTIVE", "version": 1},
            {"id": "s-2", "tenantId": 7, "status": "ACTIVE", "version": 1},
        ] if config_type == pam._runtime.SUPPORT else [],
    )
    monkeypatch.setattr(
        pam._runtime._base,
        "_save_atomic",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("oversized campaign must not be written")),
    )
    with pytest.raises(AppException) as exc:
        pam.create_access_review(
            {
                "requestId": "review-0003",
                "scope": {"configTypes": [pam._runtime.SUPPORT], "tenantIds": [7]},
            },
            actor={"userId": "p-1"},
        )
    assert getattr(exc.value, "biz_code", getattr(exc.value, "code", "")) == "ACCESS_REVIEW_SCOPE_TOO_LARGE"


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
