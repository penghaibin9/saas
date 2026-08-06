"""Bootstrap dedicated graduation/internship/student-affairs E2E identities without persisting credentials.

The official identity-import API may return an initial-password receipt. CI deliberately
keeps that response in memory only; passwords are normalized by the official reset/change
endpoints and are never written to disk or uploaded as an artifact.
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


def _add_interaction_roles(content: bytes) -> bytes:
    """Give the existing E2E advisor all real roles used by browser interaction chains."""
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
        for code in ("GD_MENTOR", "INTERN_MENTOR", "COUNSELOR"):
            if code not in roles:
                roles.append(code)
        ws.cell(row, role_col).value = ",".join(roles)
        found = True
        break
    if not found:
        raise SystemExit("e2e_advisor_a is missing from identity workbook")
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def import_accounts_without_receipt_file(token: str) -> dict:
    content = _add_interaction_roles(build_xlsx(token))
    body, boundary = multipart(content, "e2e_interaction_identity.xlsx")
    validated = _req(
        "POST",
        "/system/identity-import/validate-file",
        token=token,
        raw=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    if validated.get("code") != 0:
        raise SystemExit("identity validation failed: " + json.dumps(validated, ensure_ascii=False))
    data = validated.get("data") or {}
    batch_no = data.get("batchNo")
    if not batch_no:
        raise SystemExit("identity validation returned no batchNo")
    confirmed = _req(
        "POST",
        "/system/identity-import/confirm-batch",
        token=token,
        body={"batchNo": batch_no},
    )
    if confirmed.get("code") != 0:
        raise SystemExit("identity import failed: " + json.dumps(confirmed, ensure_ascii=False))
    receipt = confirmed.get("data") or {}
    print(
        "[e2e-bootstrap] identity import confirmed",
        json.dumps(
            {
                "batchNo": batch_no,
                "receiptKeys": sorted(receipt.keys()) if isinstance(receipt, dict) else [],
            },
            ensure_ascii=False,
        ),
    )
    return {"batchNo": batch_no, "confirmed": True}


def main() -> int:
    token = login()
    org = ensure_org(token)
    print("org:", json.dumps(org, ensure_ascii=False))
    imported = import_accounts_without_receipt_file(token)
    print("[e2e-bootstrap] ready:", imported["batchNo"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
