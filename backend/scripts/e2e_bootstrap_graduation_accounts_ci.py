"""Bootstrap dedicated graduation/internship E2E identities without persisting credentials.

The official identity-import API may return an initial-password receipt. CI deliberately
keeps that response in memory only; passwords are normalized by the official reset/change
endpoints and are never written to disk or uploaded as an artifact.

For student-affairs authorization testing, the CI-only workbook also places the existing
E2E student B in a second administrative class. This gives Playwright a real cross-class
negative control without mutating production/staging data or pre-creating business facts.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.e2e_bootstrap_graduation_accounts import (  # noqa: E402
    COLLEGE,
    MAJOR,
    _req,
    build_xlsx,
    ensure_org,
    login,
    multipart,
)

OUTSIDE_CLASS = "E2E机器人2402班"
OUTSIDE_CLASS_CODE = "E2E-CLS-AFFAIRS-OUT"
OUTSIDE_STUDENT_NO = "E2E20260002"


def ensure_outside_class(token: str) -> dict:
    """Create the CI-only second class through the formal organization API."""
    tree = _req("GET", "/system/org-tree", token=token)
    if tree.get("code") != 0:
        raise SystemExit("unable to load organization tree for outside-class fixture")
    nodes = tree.get("data") or []
    college = next((item for item in nodes if item.get("name") == COLLEGE), None)
    if college is None:
        raise SystemExit(f"college {COLLEGE} is missing after ensure_org")
    major = next((item for item in college.get("children") or [] if item.get("name") == MAJOR), None)
    if major is None:
        raise SystemExit(f"major {MAJOR} is missing after ensure_org")
    school_class = next(
        (item for item in major.get("children") or [] if item.get("name") == OUTSIDE_CLASS),
        None,
    )
    if school_class is not None:
        return {"classId": school_class["id"], "created": False}

    created = _req(
        "POST",
        "/system/org-nodes",
        token=token,
        body={
            "type": "CLASS",
            "name": OUTSIDE_CLASS,
            "code": OUTSIDE_CLASS_CODE,
            "parentId": major["id"],
        },
    )
    if created.get("code") != 0:
        raise SystemExit("outside-class creation failed: " + json.dumps(created, ensure_ascii=False))
    return {"classId": created["data"]["id"], "created": True}


def _prepare_interaction_workbook(content: bytes) -> bytes:
    """Keep existing roles and move only student B to the cross-class fixture."""
    wb = load_workbook(io.BytesIO(content))
    ws = wb["导入模板"]
    headers = {str(cell.value or "").strip(): idx for idx, cell in enumerate(ws[1], start=1)}
    login_col = headers.get("工号/学号") or headers.get("账号") or 2
    role_col = headers.get("角色编码") or headers.get("角色") or 11
    class_col = headers.get("行政班") or headers.get("班级") or 6
    mentor_found = False
    outside_student_found = False

    for row in range(2, ws.max_row + 1):
        login_name = str(ws.cell(row, login_col).value or "").strip()
        if login_name == "e2e_advisor_a":
            roles = [part.strip() for part in str(ws.cell(row, role_col).value or "").split(",") if part.strip()]
            for code in ("GD_MENTOR", "INTERN_MENTOR"):
                if code not in roles:
                    roles.append(code)
            ws.cell(row, role_col).value = ",".join(roles)
            mentor_found = True
        elif login_name == OUTSIDE_STUDENT_NO:
            ws.cell(row, class_col).value = OUTSIDE_CLASS
            outside_student_found = True

    if not mentor_found:
        raise SystemExit("e2e_advisor_a is missing from identity workbook")
    if not outside_student_found:
        raise SystemExit(f"{OUTSIDE_STUDENT_NO} is missing from identity workbook")

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def import_accounts_without_receipt_file(token: str) -> dict:
    content = _prepare_interaction_workbook(build_xlsx(token))
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
    outside_class = ensure_outside_class(token)
    print("org:", json.dumps(org, ensure_ascii=False))
    print("outsideClass:", json.dumps(outside_class, ensure_ascii=False))
    imported = import_accounts_without_receipt_file(token)
    print("[e2e-bootstrap] ready:", imported["batchNo"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
