"""Provenance hardening for Platform Product IAM releases.

The canonical Product IAM service remains the only owner of source snapshots,
storage, impact and publication. This facade makes deployment provenance
server-authoritative: a browser-provided SHA is only an optional expectation and
can never become the stored source truth by itself.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from app.core.exceptions import AppException
from app.modules.platform.services import platform_product_iam_service as _base

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _deployed_commit_sha() -> str:
    configured = str(os.getenv("DEPLOYED_COMMIT_SHA", "") or "").strip().lower()
    if configured:
        if _SHA_RE.fullmatch(configured):
            return configured
        raise AppException(
            "PRODUCT_IAM_PROVENANCE_UNAVAILABLE",
            "部署提交摘要已配置但格式无效，禁止创建或发布产品身份与权限版本",
            http_status=503,
        )

    marker_paths: list[Path] = []
    explicit_marker = str(os.getenv("DEPLOYED_COMMIT_FILE", "") or "").strip()
    if explicit_marker:
        marker_paths.append(Path(explicit_marker))
    try:
        marker_paths.append(Path(__file__).resolve().parents[5] / ".release-commit")
    except IndexError:
        pass

    for marker in marker_paths:
        try:
            value = marker.read_text(encoding="utf-8").strip().lower()
        except (OSError, UnicodeError):
            continue
        if _SHA_RE.fullmatch(value):
            return value

    raise AppException(
        "PRODUCT_IAM_PROVENANCE_UNAVAILABLE",
        "部署环境没有可验证的不可变发布提交摘要，禁止创建或发布产品身份与权限版本",
        http_status=503,
    )


def deployed_commit_sha() -> str:
    """Return the server-attested immutable deployment commit.

    Product IAM drafts and exact-head delivery evidence share this provenance
    boundary so a browser-supplied SHA can never become release truth.
    """
    return _deployed_commit_sha()


def _assert_expected_commit(expected: str, deployed: str) -> None:
    value = str(expected or "").strip().lower()
    if not value:
        return
    if not _SHA_RE.fullmatch(value):
        raise AppException("VALIDATION_ERROR", "sourceCommitSha 必须是 40 位 Git SHA", http_status=422)
    if value != deployed:
        raise AppException(
            "PRODUCT_IAM_SOURCE_COMMIT_MISMATCH",
            "客户端期望的代码提交与当前部署提交不一致，拒绝生成产品身份与权限草稿",
            http_status=409,
            details={"expectedSourceCommitSha": value, "deployedCommitSha": deployed},
        )


def create_release_draft(*, reason: str, source_commit_sha: str, actor: dict, request_id: str) -> dict:
    deployed = _deployed_commit_sha()
    _assert_expected_commit(source_commit_sha, deployed)
    return _base.create_release_draft(
        reason=reason,
        source_commit_sha=deployed,
        actor=actor,
        request_id=request_id,
    )


def publish_release(release_id: str, *, expected_version: int, actor: dict) -> dict:
    deployed = _deployed_commit_sha()
    target = next((item for item in _base.list_releases() if str(item.get("id")) == str(release_id)), None)
    if target is not None:
        stored = str(target.get("sourceCommitSha") or "").strip().lower()
        if stored != deployed:
            raise AppException(
                "PRODUCT_IAM_SOURCE_COMMIT_DRIFT",
                "产品身份与权限草稿对应的部署提交已不是当前部署提交，必须重新生成草稿",
                http_status=409,
                details={"draftCommitSha": stored, "deployedCommitSha": deployed},
            )
    # Canonical publish_release still re-computes sourceDigest under row lock and
    # rejects module/permission/template drift. Provenance is an additional gate.
    return _base.publish_release(release_id, expected_version=expected_version, actor=actor)


for _name in dir(_base):
    if _name.startswith("_") or _name in globals():
        continue
    globals()[_name] = getattr(_base, _name)


def source_snapshot() -> dict:
    snapshot = _base.source_snapshot()
    try:
        deployed = _deployed_commit_sha()
        provenance_status = "VERIFIED"
    except AppException:
        deployed = None
        provenance_status = "UNAVAILABLE"
    snapshot["provenance"] = {
        "deployedCommitSha": deployed,
        "status": provenance_status,
        "sourceDigest": snapshot.get("sourceDigest"),
        "navigationDigest": snapshot.get("navigationDigest"),
        "permissionCatalogDigest": _base._hash(snapshot.get("permissions") or []),
        "roleTemplateDigest": _base._hash(snapshot.get("roleTemplates") or []),
    }
    return snapshot


def __getattr__(name: str):
    return getattr(_base, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_base)))
