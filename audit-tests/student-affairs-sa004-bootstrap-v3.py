from __future__ import annotations

import json

from app.services.identity_import_file_service import build_student_template, build_teacher_template
from scripts.e2e_bootstrap_graduation_accounts_ci import _canonical_import, _workbook_with_rows
from scripts.e2e_bootstrap_student_affairs_accounts import (
    CLASS_A,
    CLASS_B,
    COLLEGE,
    MAJOR,
    STABLE_PWD,
    TENANT,
    _req,
    ensure_org,
    list_users,
)


def main() -> None:
    admin = _req(
        "POST",
        "/auth/login",
        headers={"X-Forwarded-For": "10.254.0.250"},
        body={"loginName": "admin2", "password": "123456", "tenantCode": TENANT},
    )
    assert admin.get("code") == 0, admin
    token = admin["data"]["accessToken"]
    org = ensure_org(token)
    print("[sa004-bootstrap] org ready", json.dumps(org, ensure_ascii=False))

    teachers = _workbook_with_rows(
        build_teacher_template(),
        [
            ["e2e_sa_admin", "E2E学工处管理员", "学工处", "学工处管理员", "STUDENT_AFFAIRS_ADMIN", "", ""],
            ["e2e_college_admin", "E2E学院管理员", COLLEGE, "学院管理员", "COLLEGE_ADMIN", "COLLEGE", COLLEGE],
            ["e2e_counselor_a", "E2E辅导员A", COLLEGE, "辅导员", "COUNSELOR", "CLASS", CLASS_A],
            ["e2e_counselor_b", "E2E辅导员B", COLLEGE, "辅导员", "COUNSELOR", "CLASS", CLASS_B],
        ],
    )
    students = _workbook_with_rows(
        build_student_template(),
        [["E2E20260001", "E2E学生A", COLLEGE, MAJOR, CLASS_A, "2024", "男", ""]],
    )
    _canonical_import(token, kind="teachers", content=teachers, idempotency_namespace="e2e-sa004-v3-focused")
    _canonical_import(token, kind="students", content=students, idempotency_namespace="e2e-sa004-v3-focused")

    users = list_users(token)
    required = ["e2e_sa_admin", "e2e_college_admin", "e2e_counselor_a", "e2e_counselor_b", "E2E20260001"]
    missing = [name for name in required if name not in users]
    assert not missing, f"missing canonical SA-004 identities: {missing}"

    for index, login_name in enumerate(required, start=1):
        user = users[login_name]
        user_id = user.get("id") or user.get("userId")
        reset = _req("POST", f"/system/users/{user_id}/reset-password", token=token, body={})
        assert reset.get("code") == 0, (login_name, reset)
        reset_data = reset.get("data") or {}
        temp_password = reset_data.get("tempPassword") or reset_data.get("temporaryPassword") or reset_data.get("password")
        assert temp_password, f"{login_name}: reset returned no temporary password"
        login = _req(
            "POST",
            "/auth/login",
            headers={"X-Forwarded-For": f"10.254.0.{index}"},
            body={"loginName": login_name, "password": temp_password, "tenantCode": TENANT},
        )
        assert login.get("code") == 0, (login_name, login)
        changed = _req(
            "POST",
            "/auth/change-password",
            token=login["data"]["accessToken"],
            body={"oldPassword": temp_password, "newPassword": STABLE_PWD},
        )
        assert changed.get("code") == 0, (login_name, changed)

    users = list_users(token)

    def ensure_primary_counselor(class_name: str, login_name: str):
        class_id = int(org["classIds"][class_name])
        counselor_id = int(users[login_name].get("id") or users[login_name].get("userId"))
        listed = _req(
            "GET",
            "/student-affairs/counselor-assignments",
            token=token,
            params={"classId": class_id, "pageSize": 100},
        )
        assert listed.get("code") == 0, (class_name, listed)
        rows = (listed.get("data") or {}).get("items") or []
        active = next(
            (
                row
                for row in rows
                if row.get("status") == "ACTIVE"
                and row.get("dutyType") == "PRIMARY"
                and int(row.get("userId") or 0) == counselor_id
            ),
            None,
        )
        if active:
            return active.get("assignmentId") or active.get("id")
        created = _req(
            "POST",
            "/student-affairs/counselor-assignments",
            token=token,
            body={
                "classId": class_id,
                "userId": counselor_id,
                "dutyType": "PRIMARY",
                "reason": "SA-004 V3 focused exact-head Browser First fixture",
            },
        )
        assert created.get("code") == 0, (class_name, login_name, created)
        return (created.get("data") or {}).get("assignmentId") or (created.get("data") or {}).get("id")

    relation_a = ensure_primary_counselor(CLASS_A, "e2e_counselor_a")
    relation_b = ensure_primary_counselor(CLASS_B, "e2e_counselor_b")
    print(
        "[sa004-bootstrap] canonical identities/passwords/relations ready",
        {"accounts": required, "classAPrimary": relation_a, "classBPrimary": relation_b},
    )


if __name__ == "__main__":
    main()
