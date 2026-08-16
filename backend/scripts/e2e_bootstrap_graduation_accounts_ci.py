"""Bootstrap dedicated graduation/internship E2E identities through canonical Data Exchange.

The retired mixed identity parser is intentionally not used.  CI splits the historical
combined workbook into the canonical TEACHER and STUDENT contracts, runs each file through
FileObject -> explicit process/staging -> canonical confirm, and keeps any credential
receipt in memory only.  Passwords are normalized by the official reset/change endpoints
in the following workflow step and are never written to an artifact.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.e2e_bootstrap_graduation_accounts import (  # noqa: E402
    _req,
    build_xlsx,
    ensure_org,
    login,
    multipart,
)


def _add_internship_mentor_role(content: bytes) -> bytes:
    """Give the existing E2E advisor the real internship-mentor role as well."""
    wb = load_workbook(io.BytesIO(content))
    ws = wb["导入模板"]
    headers = {str(cell.value or "").strip(): idx for idx, cell in enumerate(ws[1], start=1)}
    login_col = headers.get("工号/学号") or headers.get("账号") or 2
    role_col = headers.get("角色编码") or headers.get("角色") or 11
    found = False
    for row in range(2, ws.max_row + 1):
        if str(ws.cell(row, login_col).value or "").strip() != "e2e_advisor_a":
            continue
        roles = [part.strip() for part in str(ws.cell(row, role_col).value or "").split(",") if part.strip()]
        for code in ("GD_MENTOR", "INTERN_MENTOR"):
            if code not in roles:
                roles.append(code)
        ws.cell(row, role_col).value = ",".join(roles)
        found = True
        break
    if not found:
        raise SystemExit("e2e_advisor_a is missing from identity workbook")
    out = io.BytesIO()
    wb.save(out)
    wb.close()
    return out.getvalue()


def _split_identity_workbook(content: bytes, identity_type: str) -> bytes:
    """Keep the official template but retain rows for exactly one canonical identity kind."""
    expected = str(identity_type or "").strip().upper()
    if expected not in {"TEACHER", "STUDENT"}:
        raise ValueError(f"unsupported identity type: {identity_type}")
    wb = load_workbook(io.BytesIO(content))
    ws = wb["导入模板"]
    headers = {str(cell.value or "").strip(): idx for idx, cell in enumerate(ws[1], start=1)}
    type_col = headers.get("类型") or headers.get("身份类型") or 1
    kept = 0
    for row in range(ws.max_row, 1, -1):
        actual = str(ws.cell(row, type_col).value or "").strip().upper()
        if actual != expected:
            ws.delete_rows(row, 1)
        else:
            kept += 1
    if kept <= 0:
        wb.close()
        raise SystemExit(f"canonical {expected} workbook contains no data rows")
    out = io.BytesIO()
    wb.save(out)
    wb.close()
    return out.getvalue()


def _canonical_import(token: str, *, kind: str, content: bytes) -> dict:
    """Run upload -> explicit worker process -> canonical job confirmation."""
    if kind not in {"teachers", "students"}:
        raise ValueError(f"unsupported canonical identity kind: {kind}")
    filename = f"e2e_interaction_{kind}.xlsx"
    body, boundary = multipart(content, filename)
    upload_key = f"e2e-graduation-{kind}-canonical-v2"
    created = _req(
        "POST",
        f"/data-exchange/imports/identity/{kind}/validate-file",
        token=token,
        raw=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Idempotency-Key": upload_key,
        },
    )
    if created.get("code") != 0:
        raise SystemExit(
            f"canonical {kind} identity upload failed: "
            + json.dumps(created, ensure_ascii=False)
        )
    item = dict(created.get("data") or {})
    job_id = str(item.get("id") or item.get("jobId") or "").strip()
    if not job_id:
        raise SystemExit(f"canonical {kind} identity upload returned no job id")

    status = str(item.get("status") or "").upper()
    if status == "SUCCEEDED":
        print(f"[e2e-bootstrap] canonical {kind} import replayed succeeded job {job_id}")
        return item
    if status != "VALIDATED":
        processed = _req(
            "POST",
            f"/data-exchange/imports/{job_id}/process",
            token=token,
        )
        if processed.get("code") != 0:
            raise SystemExit(
                f"canonical {kind} identity process failed: "
                + json.dumps(processed, ensure_ascii=False)
            )
        item = dict(processed.get("data") or {})
        status = str(item.get("status") or "").upper()
    if status != "VALIDATED":
        raise SystemExit(
            f"canonical {kind} identity job did not validate: "
            + json.dumps(
                {
                    "jobId": job_id,
                    "status": item.get("status"),
                    "message": item.get("errorMessage") or item.get("message"),
                    "invalidRows": item.get("invalidRows"),
                },
                ensure_ascii=False,
            )
        )

    expected_version = int(item.get("version") or 0)
    confirmed = _req(
        "POST",
        f"/data-exchange/imports/{job_id}/confirm",
        token=token,
        body={"expectedVersion": expected_version},
        headers={"Idempotency-Key": f"e2e-graduation-{kind}-confirm-v2"},
    )
    if confirmed.get("code") != 0:
        raise SystemExit(
            f"canonical {kind} identity confirm failed: "
            + json.dumps(confirmed, ensure_ascii=False)
        )
    receipt = dict(confirmed.get("data") or {})
    print(
        f"[e2e-bootstrap] canonical {kind} identity import confirmed",
        json.dumps(
            {
                "jobId": job_id,
                "receiptKeys": sorted(receipt.keys()),
            },
            ensure_ascii=False,
        ),
    )
    return receipt


def import_accounts_without_receipt_file(token: str) -> dict:
    combined = _add_internship_mentor_role(build_xlsx(token))
    teachers = _split_identity_workbook(combined, "TEACHER")
    students = _split_identity_workbook(combined, "STUDENT")
    teacher_receipt = _canonical_import(token, kind="teachers", content=teachers)
    student_receipt = _canonical_import(token, kind="students", content=students)
    return {
        "teachers": str(teacher_receipt.get("id") or teacher_receipt.get("jobId") or "confirmed"),
        "students": str(student_receipt.get("id") or student_receipt.get("jobId") or "confirmed"),
    }


def main() -> int:
    token = login()
    org = ensure_org(token)
    print("org:", json.dumps(org, ensure_ascii=False))
    imported = import_accounts_without_receipt_file(token)
    print("[e2e-bootstrap] ready:", json.dumps(imported, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
