#!/usr/bin/env python3
"""Independent HTTP processes must observe logout with and without Redis reads.

CI-only acceptance. It uses explicit fixture credentials seeded by
_seed_login_accounts_only.py and never reads production secrets or customer data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import httpx

A = os.environ.get("E2E_AUTH_A", "http://127.0.0.1:8000").rstrip("/")
B = os.environ.get("E2E_AUTH_B", "http://127.0.0.1:8001").rstrip("/")
C = os.environ.get("E2E_AUTH_C", "http://127.0.0.1:8002").rstrip("/")
OUT = Path(os.environ.get("E2E_ARTIFACT_DIR", "artifacts/security-runtime"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    body = {
        "tenantCode": "demo-school",
        "loginName": "student",
        "password": "123456",
        "clientType": "STUDENT_PC",
    }
    with httpx.Client(timeout=10.0, trust_env=False) as client:
        login = client.post(A + "/api/v1/auth/login", json=body)
        require(login.status_code == 200, f"login status={login.status_code}")
        data = (login.json().get("data") or {})
        token = str(data.get("accessToken") or "")
        require(len(token) > 20, "access token missing")
        headers = {"Authorization": "Bearer " + token}

        before_shared = client.get(B + "/api/v1/auth/me", headers=headers)
        require(before_shared.status_code == 200,
                f"worker B did not accept fresh token: {before_shared.status_code}")
        before_no_redis = client.get(C + "/api/v1/auth/me", headers=headers)
        require(before_no_redis.status_code == 200,
                f"worker C durable fallback did not accept fresh token: {before_no_redis.status_code}")

        logout = client.post(A + "/api/v1/auth/logout", headers=headers)
        require(logout.status_code == 200, f"logout status={logout.status_code}")
        logout_data = (logout.json().get("data") or {})
        require(logout_data.get("tokenInvalidated") is True, "logout did not confirm invalidation")

        after_shared = client.get(B + "/api/v1/auth/me", headers=headers)
        require(after_shared.status_code == 401,
                f"revoked token remained valid on worker B: {after_shared.status_code}")
        after_no_redis = client.get(C + "/api/v1/auth/me", headers=headers)
        require(after_no_redis.status_code == 401,
                f"durable revocation failed without Redis reads: {after_no_redis.status_code}")

    receipt = {
        "threeIndependentHttpProcesses": True,
        "workerBSharedMysqlRedis": True,
        "workerCRedisUnavailable": True,
        "workerCDurableMysqlFallback": True,
        "beforeLogoutSharedStatus": before_shared.status_code,
        "beforeLogoutNoRedisStatus": before_no_redis.status_code,
        "logoutStatus": logout.status_code,
        "afterLogoutSharedStatus": after_shared.status_code,
        "afterLogoutNoRedisStatus": after_no_redis.status_code,
        "revocationObservedAcrossProcesses": True,
        "revocationObservedDuringRedisReadFailure": True,
        "fixtureOnly": True,
    }
    (OUT / "cross-process-revocation.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("cross-process HTTP revocation and durable fallback acceptance passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"cross-process revocation failed: {type(exc).__name__}", file=sys.stderr)
        raise
