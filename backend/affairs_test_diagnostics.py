"""Temporary diagnostics for student-affairs integration test failures."""
from __future__ import annotations

import json

import pytest


@pytest.fixture(scope="session", autouse=True)
def _install_affairs_diagnostics(_install_affairs_legacy_adapter):
    import conftest

    client_cls = conftest.GraduationBatchAwareClient
    if getattr(client_cls, "_affairs_diagnostics_installed", False):
        yield
        return

    original = client_cls.request

    def request(self, method, url, **kwargs):
        response = original(self, method, url, **kwargs)
        path, _query = self._path_and_query(url)
        if "/student-affairs/" in path and int(getattr(response, "status_code", 0) or 0) >= 400:
            try:
                payload = response.json()
            except Exception:
                payload = {"text": str(getattr(response, "text", ""))[:500]}
            print(
                "AFFAIRS_TEST_RESPONSE",
                str(method).upper(),
                path,
                response.status_code,
                json.dumps(payload, ensure_ascii=False, default=str),
                flush=True,
            )
        return response

    client_cls.request = request
    client_cls._affairs_diagnostics_installed = True
    yield
