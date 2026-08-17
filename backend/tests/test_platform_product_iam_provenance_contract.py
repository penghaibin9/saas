import pytest

from app.core.exceptions import AppException
from app.modules.platform.services import platform_product_iam_hardening as iam


DEPLOYED = "a" * 40
OTHER = "b" * 40


def test_product_iam_draft_stores_server_deployed_sha(monkeypatch):
    monkeypatch.setenv("DEPLOYED_COMMIT_SHA", DEPLOYED)
    seen = {}

    def create(**kwargs):
        seen.update(kwargs)
        return {"sourceCommitSha": kwargs["source_commit_sha"]}

    monkeypatch.setattr(iam._base, "create_release_draft", create)
    out = iam.create_release_draft(
        reason="release governance",
        source_commit_sha="",
        request_id="request-0001",
        actor={"userId": "root-1"},
    )
    assert out["sourceCommitSha"] == DEPLOYED
    assert seen["source_commit_sha"] == DEPLOYED


def test_product_iam_draft_rejects_client_commit_mismatch_before_writer(monkeypatch):
    monkeypatch.setenv("DEPLOYED_COMMIT_SHA", DEPLOYED)
    monkeypatch.setattr(
        iam._base,
        "create_release_draft",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("mismatch must not reach canonical writer")),
    )
    with pytest.raises(AppException) as exc:
        iam.create_release_draft(
            reason="release governance",
            source_commit_sha=OTHER,
            request_id="request-0002",
            actor={"userId": "root-1"},
        )
    assert getattr(exc.value, "biz_code", getattr(exc.value, "code", "")) == "PRODUCT_IAM_SOURCE_COMMIT_MISMATCH"


def test_product_iam_publish_rejects_deployment_commit_drift_before_publish(monkeypatch):
    monkeypatch.setenv("DEPLOYED_COMMIT_SHA", DEPLOYED)
    monkeypatch.setattr(iam._base, "list_releases", lambda: [{"id": "release-1", "sourceCommitSha": OTHER}])
    monkeypatch.setattr(
        iam._base,
        "publish_release",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("stale draft must not publish")),
    )
    with pytest.raises(AppException) as exc:
        iam.publish_release("release-1", expected_version=3, actor={"userId": "root-1"})
    assert getattr(exc.value, "biz_code", getattr(exc.value, "code", "")) == "PRODUCT_IAM_SOURCE_COMMIT_DRIFT"


def test_product_iam_publish_keeps_canonical_digest_gate(monkeypatch):
    monkeypatch.setenv("DEPLOYED_COMMIT_SHA", DEPLOYED)
    monkeypatch.setattr(iam._base, "list_releases", lambda: [{"id": "release-1", "sourceCommitSha": DEPLOYED}])
    seen = {}

    def publish(release_id, *, expected_version, actor):
        seen.update(release_id=release_id, expected_version=expected_version, actor=actor)
        return {"id": release_id, "status": "PUBLISHED"}

    monkeypatch.setattr(iam._base, "publish_release", publish)
    out = iam.publish_release("release-1", expected_version=3, actor={"userId": "root-1"})
    assert out["status"] == "PUBLISHED"
    assert seen == {"release_id": "release-1", "expected_version": 3, "actor": {"userId": "root-1"}}


def test_product_iam_provenance_fails_closed_when_deployed_sha_missing(monkeypatch):
    monkeypatch.delenv("DEPLOYED_COMMIT_SHA", raising=False)
    with pytest.raises(AppException) as exc:
        iam.create_release_draft(
            reason="release governance",
            source_commit_sha="",
            request_id="request-0003",
            actor={"userId": "root-1"},
        )
    assert getattr(exc.value, "biz_code", getattr(exc.value, "code", "")) == "PRODUCT_IAM_PROVENANCE_UNAVAILABLE"
