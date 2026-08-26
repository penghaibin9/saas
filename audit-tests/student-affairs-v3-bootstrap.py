"""Runner-only Student Affairs V3 actor bootstrap for an immutable product checkout.

The Student Affairs business audit is not an identity-import acceptance test.  This
fixture therefore prepares its canonical actors without reviving the retired mixed
teacher/student parser and without burning the real /auth/login rate limit before
business testing starts.

Product contracts are reused directly from the checked-out exact SHA:
- dedicated TEACHER and STUDENT production templates;
- canonical Data Exchange upload -> process/staging -> confirm;
- the existing E2E DB password helper, which uses the application's hash_password;
- real Student Affairs organization and dorm APIs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Workflow executes this file with cwd=app/backend while the file itself lives in
# the sibling runner checkout.  Put the immutable product backend on sys.path.
PRODUCT_BACKEND = Path.cwd().resolve()
if not (PRODUCT_BACKEND / "app").is_dir():
    raise SystemExit(f"expected product backend cwd, got {PRODUCT_BACKEND}")
sys.path.insert(0, str(PRODUCT_BACKEND))

from app.services.identity_import_file_service import (  # noqa: E402
    build_student_template,
    build_teacher_template,
)
from scripts.e2e_bootstrap_graduation_accounts_ci import (  # noqa: E402
    _canonical_import,
    _workbook_with_rows,
)
from scripts.e2e_bootstrap_student_affairs_accounts import (  # noqa: E402
    ALL_LOGINS,
    CLASS_A,
    CLASS_B,
    COLLEGE,
    CRED_PATH,
    DORM_NAME,
    MAJOR,
    STATE_PATH,
    STUDENT_ORG,
    STUDENTS,
    TEACHERS,
    TENANT,
    _req,
    ensure_counselor_assignment,
    ensure_dorm,
    ensure_org,
    login_admin,
)
from scripts.e2e_sa_set_passwords_db import STABLE_PWD, set_passwords  # noqa: E402


def teacher_workbook() -> bytes:
    rows: list[list[str]] = []
    for login_name, display_name, roles, scope_type, scope_ref, department in TEACHERS:
        rows.append([
            login_name,
            display_name,
            department,
            display_name,
            roles,
            scope_type,
            scope_ref,
        ])
    return _workbook_with_rows(build_teacher_template(), rows)


def student_workbook() -> bytes:
    rows = [
        [student_no, name, COLLEGE, MAJOR, class_name, "2024", gender, ""]
        for student_no, name, class_name, gender in STUDENTS
    ]
    return _workbook_with_rows(build_student_template(), rows)


def import_accounts(token: str) -> dict:
    teachers = _canonical_import(
        token,
        kind="teachers",
        content=teacher_workbook(),
        idempotency_namespace="e2e-student-affairs-v3",
    )
    students = _canonical_import(
        token,
        kind="students",
        content=student_workbook(),
        idempotency_namespace="e2e-student-affairs-v3",
    )
    return {
        "teachers": str(teachers.get("id") or teachers.get("jobId") or "confirmed"),
        "students": str(students.get("id") or students.get("jobId") or "confirmed"),
        "confirmed": True,
    }


def ensure_student_org(token: str) -> dict:
    listed = _req("GET", "/student-affairs/organizations?pageSize=100", token=token)
    if listed.get("code") != 0:
        raise SystemExit("list student organizations failed: " + json.dumps(listed, ensure_ascii=False))
    data = listed.get("data") or {}
    items = data.get("list") or data.get("items") or []
    for item in items:
        if (item.get("orgName") or item.get("name")) == STUDENT_ORG:
            return {
                "orgId": item.get("orgId") or item.get("id"),
                "created": False,
                "orgType": item.get("orgType"),
            }

    created = _req(
        "POST",
        "/student-affairs/organizations",
        token=token,
        body={
            "orgName": STUDENT_ORG,
            "orgType": "STUDENT_UNION",
            "level": "SCHOOL",
        },
    )
    if created.get("code") != 0:
        raise SystemExit("create student organization failed: " + json.dumps(created, ensure_ascii=False))
    payload = created.get("data") or {}
    return {
        "orgId": payload.get("orgId") or payload.get("id"),
        "created": True,
        "orgType": "STUDENT_UNION",
    }


def write_fixture_files(
    *,
    org: dict,
    dorm: dict,
    student_org: dict,
    imported: dict,
    counselor: dict,
) -> None:
    passwords = set_passwords()
    missing = [login_name for login_name in ALL_LOGINS if login_name not in passwords]
    if missing:
        raise SystemExit("canonical actor import missing users: " + ", ".join(missing))

    CRED_PATH.write_text(
        json.dumps(
            {
                "tenantCode": TENANT,
                "schoolName": "E2E测试职业学院(sandbox-school租户内E2E组织)",
                "passwords": passwords,
                "loginResults": [],
                "note": (
                    "V3 runner fixture: credentials were prepared with the product's "
                    "hash_password helper; real login verification is intentionally deferred "
                    "to Browser/API business tests so bootstrap does not consume login quota."
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    state = {
        "org": org,
        "dorm": {key: value for key, value in dorm.items() if key != "rooms"},
        "studentOrg": student_org,
        "counselor": counselor,
        "import": imported,
        "accounts": ALL_LOGINS,
        "passwordFile": str(CRED_PATH),
        "loginOk": sorted(passwords.keys()),
        "bootstrapLoginVerificationDeferred": True,
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"credentials -> {CRED_PATH}")
    print(f"state -> {STATE_PATH}")
    print(f"actors_ready={len(passwords)}/{len(ALL_LOGINS)}")


def main() -> int:
    # One real admin login is enough for the whole setup.  Do not login again here.
    token = login_admin()
    org = ensure_org(token)
    print("org:", json.dumps(org, ensure_ascii=False))

    dorm = ensure_dorm(token)
    print(
        "dorm:",
        json.dumps({key: value for key, value in dorm.items() if key != "rooms"}, ensure_ascii=False),
    )

    imported = import_accounts(token)
    print("identity_import:", json.dumps(imported, ensure_ascii=False))

    counselor = ensure_counselor_assignment(token, int(org["classIds"][CLASS_A]))
    if not counselor.get("configured"):
        raise SystemExit(
            "formal counselor assignment missing: " + json.dumps(counselor, ensure_ascii=False)
        )
    print("counselor:", json.dumps(counselor, ensure_ascii=False))

    student_org = ensure_student_org(token)
    print("student_org:", json.dumps(student_org, ensure_ascii=False))

    write_fixture_files(
        org=org,
        dorm=dorm,
        student_org=student_org,
        imported=imported,
        counselor=counselor,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
