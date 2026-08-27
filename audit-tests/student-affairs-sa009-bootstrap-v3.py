from __future__ import annotations

import json

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import DormBuilding
from app.services.identity_import_file_service import build_student_template, build_teacher_template
from scripts.e2e_bootstrap_graduation_accounts_ci import _canonical_import, _workbook_with_rows
from scripts.e2e_bootstrap_student_affairs_accounts import (
    CLASS_A,
    COLLEGE,
    MAJOR,
    STABLE_PWD,
    TENANT,
    _req,
    ensure_org,
    list_users,
)

SA_ADMIN_LOGIN = "e2e_sa_admin"
COUNSELOR_LOGIN = "e2e_sa009_counselor"
DORM_MANAGER_LOGIN = "e2e_sa009_dorm"
STUDENT_NO = "E2E20260911"
STUDENT_NAME = "SA009宿舍学生"


def _reset_password(token: str, login_name: str, user: dict, forwarded_for: str) -> None:
    user_id = user.get("id") or user.get("userId")
    reset = _req("POST", f"/system/users/{user_id}/reset-password", token=token, body={})
    assert reset.get("code") == 0, (login_name, reset)
    data = reset.get("data") or {}
    temp = data.get("tempPassword") or data.get("temporaryPassword") or data.get("password")
    assert temp, f"{login_name}: reset returned no temporary password"
    login = _req(
        "POST",
        "/auth/login",
        headers={"X-Forwarded-For": forwarded_for},
        body={"loginName": login_name, "password": temp, "tenantCode": TENANT},
    )
    assert login.get("code") == 0, (login_name, login)
    changed = _req(
        "POST",
        "/auth/change-password",
        token=login["data"]["accessToken"],
        body={"oldPassword": temp, "newPassword": STABLE_PWD, "confirmPassword": STABLE_PWD},
    )
    if changed.get("code") != 0:
        changed = _req(
            "POST",
            "/auth/password/change",
            token=login["data"]["accessToken"],
            body={"oldPassword": temp, "newPassword": STABLE_PWD},
        )
    assert changed.get("code") == 0, (login_name, changed)


def _ensure_primary_counselor(token: str, org: dict, users: dict[str, dict]) -> int:
    class_id = int(org["classIds"][CLASS_A])
    counselor_id = int(users[COUNSELOR_LOGIN].get("id") or users[COUNSELOR_LOGIN].get("userId"))
    listed = _req(
        "GET",
        "/student-affairs/counselor-assignments",
        token=token,
        params={"classId": class_id, "pageSize": 100},
    )
    assert listed.get("code") == 0, listed
    rows = (listed.get("data") or {}).get("items") or []
    active = next(
        (
            row for row in rows
            if row.get("status") == "ACTIVE"
            and row.get("dutyType") == "PRIMARY"
            and int(row.get("userId") or 0) == counselor_id
        ),
        None,
    )
    if active:
        return int(active.get("assignmentId") or active.get("id"))
    created = _req(
        "POST",
        "/student-affairs/counselor-assignments",
        token=token,
        body={
            "classId": class_id,
            "userId": counselor_id,
            "dutyType": "PRIMARY",
            "reason": "SA-009 V3 Browser First canonical counselor relation",
        },
    )
    assert created.get("code") == 0, created
    return int((created.get("data") or {}).get("assignmentId") or (created.get("data") or {}).get("id"))


def _assert_no_prebound_dorm(manager_user_id: int) -> None:
    with get_sessionmaker()() as db:
        rows = db.scalars(select(DormBuilding).where(
            DormBuilding.is_deleted.is_(False),
            DormBuilding.manager_teacher_key.in_((str(manager_user_id), DORM_MANAGER_LOGIN)),
        )).all()
        assert not rows, {
            "message": "SA-009 fixture must not pre-bind a dorm manager; Browser UI is authoritative",
            "managerUserId": manager_user_id,
            "managerLogin": DORM_MANAGER_LOGIN,
            "preboundBuildingIds": [int(row.id) for row in rows],
        }


def main() -> None:
    admin = _req(
        "POST",
        "/auth/login",
        headers={"X-Forwarded-For": "10.254.9.240"},
        body={"loginName": "admin2", "password": "123456", "tenantCode": TENANT},
    )
    assert admin.get("code") == 0, admin
    token = admin["data"]["accessToken"]
    org = ensure_org(token)

    teachers = _workbook_with_rows(
        build_teacher_template(),
        [
            [SA_ADMIN_LOGIN, "SA009学工处管理员", "学工处", "学工处管理员", "STUDENT_AFFAIRS_ADMIN", "", ""],
            [COUNSELOR_LOGIN, "SA009辅导员", COLLEGE, "辅导员", "COUNSELOR", "CLASS", CLASS_A],
            # Do not pre-bind any dorm building. Browser-created managerTeacherKey is the authority.
            [DORM_MANAGER_LOGIN, "SA009宿管", "后勤处", "宿管", "DORM_MANAGER", "", ""],
        ],
    )
    students = _workbook_with_rows(
        build_student_template(),
        [[STUDENT_NO, STUDENT_NAME, COLLEGE, MAJOR, CLASS_A, "2024", "男", ""]],
    )
    _canonical_import(token, kind="teachers", content=teachers, idempotency_namespace="e2e-sa009-v3-browser")
    _canonical_import(token, kind="students", content=students, idempotency_namespace="e2e-sa009-v3-browser")

    users = list_users(token)
    required = [SA_ADMIN_LOGIN, COUNSELOR_LOGIN, DORM_MANAGER_LOGIN, STUDENT_NO]
    missing = [name for name in required if name not in users]
    assert not missing, f"missing canonical SA-009 identities: {missing}"

    for index, login_name in enumerate(required, start=1):
        _reset_password(token, login_name, users[login_name], f"10.254.9.{240 + index}")

    users = list_users(token)
    assignment_id = _ensure_primary_counselor(token, org, users)
    dorm_manager_user_id = int(users[DORM_MANAGER_LOGIN].get("id") or users[DORM_MANAGER_LOGIN].get("userId"))
    _assert_no_prebound_dorm(dorm_manager_user_id)
    result = {
        "saAdminLogin": SA_ADMIN_LOGIN,
        "saAdminUserId": int(users[SA_ADMIN_LOGIN].get("id") or users[SA_ADMIN_LOGIN].get("userId")),
        "studentNo": STUDENT_NO,
        "studentUserId": int(users[STUDENT_NO].get("id") or users[STUDENT_NO].get("userId")),
        "counselorLogin": COUNSELOR_LOGIN,
        "counselorUserId": int(users[COUNSELOR_LOGIN].get("id") or users[COUNSELOR_LOGIN].get("userId")),
        "dormManagerLogin": DORM_MANAGER_LOGIN,
        "dormManagerUserId": dorm_manager_user_id,
        "counselorAssignmentId": assignment_id,
        "dormPrebound": False,
    }
    print("[sa009-bootstrap] " + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
