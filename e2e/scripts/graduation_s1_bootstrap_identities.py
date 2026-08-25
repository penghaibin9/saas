"""S1 audit-only driver for canonical graduation identity bootstrap.

Product identity import is intentionally asynchronous in production: upload creates a
SCANNING job, FileObject malware scanning must finish first, and only then may the
explicit /process command advance normalized staging to VALIDATED.  This harness keeps
that product contract intact and only adds bounded orchestration around the existing
product E2E bootstrap helpers.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from scripts import e2e_bootstrap_graduation_accounts_ci as product_bootstrap  # noqa: E402

POLL_SECONDS = max(0.2, float(os.getenv("S1_IDENTITY_POLL_SECONDS", "1")))
TIMEOUT_SECONDS = max(10.0, float(os.getenv("S1_IDENTITY_TIMEOUT_SECONDS", "120")))
TRANSITIONAL = {"SCANNING", "PARSING", "WORKER_CLAIMED"}
FAILURE_TERMINAL = {"VALIDATION_FAILED", "FAILED", "CANCELLED", "EXPIRED"}


def _fail(kind: str, job_id: str, item: dict, message: str) -> None:
    raise SystemExit(
        f"S1 canonical {kind} identity {message}: "
        + json.dumps(
            {
                "jobId": job_id,
                "status": item.get("status"),
                "message": item.get("errorMessage") or item.get("message"),
                "invalidRows": item.get("invalidRows"),
                "version": item.get("version"),
            },
            ensure_ascii=False,
        )
    )


def _response_data(kind: str, job_id: str, action: str, response: dict) -> dict:
    if response.get("code") != 0:
        raise SystemExit(
            f"S1 canonical {kind} identity {action} failed for job {job_id}: "
            + json.dumps(response, ensure_ascii=False)
        )
    return dict(response.get("data") or {})


def _read_job(token: str, *, kind: str, job_id: str) -> dict:
    response = product_bootstrap._req(  # noqa: SLF001
        "GET",
        f"/data-exchange/imports/{job_id}",
        token=token,
    )
    return _response_data(kind, job_id, "detail read", response)


def _canonical_import(
    token: str,
    *,
    kind: str,
    content: bytes,
    idempotency_namespace: str = "e2e-graduation",
) -> dict:
    if kind not in {"teachers", "students"}:
        raise ValueError(f"unsupported canonical identity kind: {kind}")
    namespace = str(idempotency_namespace or "").strip()
    if not namespace:
        raise ValueError("idempotency_namespace is required")

    filename = f"e2e_interaction_{kind}.xlsx"
    body, boundary = product_bootstrap.multipart(content, filename)
    created = product_bootstrap._req(  # noqa: SLF001
        "POST",
        f"/data-exchange/imports/identity/{kind}/validate-file",
        token=token,
        raw=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Idempotency-Key": f"{namespace}-{kind}-canonical-v3",
        },
    )
    item = _response_data(kind, "pending", "upload", created)
    job_id = str(item.get("id") or item.get("jobId") or "").strip()
    if not job_id:
        raise SystemExit(f"S1 canonical {kind} identity upload returned no job id")

    deadline = time.monotonic() + TIMEOUT_SECONDS
    last_rendered = None
    while True:
        status = str(item.get("status") or "").upper()
        rendered = (status, item.get("version"), item.get("invalidRows"))
        if rendered != last_rendered:
            print(
                "[s1-identity]",
                json.dumps(
                    {
                        "kind": kind,
                        "jobId": job_id,
                        "status": status,
                        "version": item.get("version"),
                        "invalidRows": item.get("invalidRows"),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            last_rendered = rendered

        if status == "SUCCEEDED":
            print(f"[s1-identity] canonical {kind} replayed succeeded job {job_id}")
            return item

        if status in FAILURE_TERMINAL:
            _fail(kind, job_id, item, "reached failure terminal state")

        if status == "VALIDATED":
            expected_version = int(item.get("version") or 0)
            confirmed = product_bootstrap._req(  # noqa: SLF001
                "POST",
                f"/data-exchange/imports/{job_id}/confirm",
                token=token,
                body={"expectedVersion": expected_version},
                headers={"Idempotency-Key": f"{namespace}-{kind}-confirm-v3"},
            )
            receipt = _response_data(kind, job_id, "confirm", confirmed)
            print(
                f"[s1-identity] canonical {kind} confirmed",
                json.dumps(
                    {
                        "jobId": job_id,
                        "validatedVersion": expected_version,
                        "receiptKeys": sorted(receipt.keys()),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            return receipt

        if status not in TRANSITIONAL:
            _fail(kind, job_id, item, "returned unexpected non-success state")

        if time.monotonic() >= deadline:
            _fail(kind, job_id, item, f"timed out after {TIMEOUT_SECONDS:.0f}s")

        # GET is intentionally pure-read.  While SCANNING, explicitly ask the
        # product command to advance once; it will stay SCANNING until the real
        # FileObject scan worker has made the source CLEAN/AVAILABLE.
        if status == "SCANNING":
            processed = product_bootstrap._req(  # noqa: SLF001
                "POST",
                f"/data-exchange/imports/{job_id}/process",
                token=token,
            )
            item = _response_data(kind, job_id, "process", processed)
            processed_status = str(item.get("status") or "").upper()
            if processed_status in FAILURE_TERMINAL:
                _fail(kind, job_id, item, "process reached failure terminal state")
            if processed_status in {"VALIDATED", "SUCCEEDED"}:
                continue

        time.sleep(POLL_SECONDS)
        item = _read_job(token, kind=kind, job_id=job_id)


def main() -> int:
    # Patch only the audit process memory.  Product files on the exact checkout are
    # untouched; account workbooks, login/org bootstrap and confirmation paths remain
    # the product implementation.
    product_bootstrap._canonical_import = _canonical_import  # noqa: SLF001
    return product_bootstrap.main()


if __name__ == "__main__":
    raise SystemExit(main())
