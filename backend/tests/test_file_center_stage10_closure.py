from __future__ import annotations

import inspect
from pathlib import Path

from app.api.v1 import file as session_router
from app.api.v1 import files as authoritative_router
from app.services.storage import _config_cache_key
from app.services.storage import production

ROOT = Path(__file__).resolve().parents[2]


def _route_signatures(router):
    return {
        (route.path, frozenset((route.methods or set()) - {"HEAD", "OPTIONS"}))
        for route in router.routes
        if hasattr(route, "path") and hasattr(route, "methods")
    }


def test_zero_call_legacy_aliases_are_not_registered():
    legacy = _route_signatures(session_router.router)
    assert ("/upload", frozenset({"POST"})) not in legacy
    assert ("/meta/{file_id}", frozenset({"GET"})) not in legacy
    assert ("/download/{file_id}", frozenset({"GET"})) not in legacy

    authoritative = _route_signatures(authoritative_router.router)
    assert ("/files", frozenset({"POST"})) in authoritative
    assert ("/files/{file_id}", frozenset({"GET"})) in authoritative
    assert ("/files/download/{file_id}", frozenset({"GET"})) in authoritative


def test_upload_session_and_scan_routes_remain_available():
    routes = _route_signatures(session_router.router)
    assert ("/upload-sessions", frozenset({"POST"})) in routes
    assert ("/upload-sessions/{session_id}/complete", frozenset({"POST"})) in routes
    assert ("/scan/health", frozenset({"GET"})) in routes
    assert ("/{file_id}/scan-status", frozenset({"GET"})) in routes


def test_sts_is_exact_key_and_never_returns_permanent_credentials():
    source = inspect.getsource(production._credential_for_exact_key)
    assert '"allow_prefix": [object_key]' in source
    assert '"allow_prefix": ["*"]' not in source
    create_source = inspect.getsource(production.create_upload_session)
    assert "credentials" not in create_source.lower() or "_credential_for_exact_key" in create_source


def test_storage_cache_isolated_without_exposing_secret():
    a = {"backend": "cos", "cosRegion": "ap-guangzhou", "cosBucket": "a", "cosSecretId": "id", "cosSecretKey": "secret-a"}
    b = {**a, "cosBucket": "b", "cosSecretKey": "secret-b"}
    key_a = _config_cache_key(a)
    key_b = _config_cache_key(b)
    assert key_a != key_b
    assert "secret-a" not in repr(key_a)
    assert "secret-b" not in repr(key_b)


def test_no_stage_trigger_or_patch_scripts_are_tracked():
    offenders = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix().lower()
        if ("stage" in path.name.lower() and "trigger" in path.name.lower()) or path.name.lower().startswith("patch_phase"):
            offenders.append(rel)
    assert offenders == []


def test_stage10_closure_ledger_exists_and_names_external_proofs():
    ledger = ROOT / "docs/architecture/file-center-stage10-closure.md"
    text = ledger.read_text(encoding="utf-8")
    assert "真实 COS 端到端" in text
    assert "大文件跨会话续传" in text
    assert "教务剩余迁移范围" in text
    assert "PR 仍为 Draft" in text
