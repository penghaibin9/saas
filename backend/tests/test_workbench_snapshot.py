from __future__ import annotations

from app.core.security import create_access_token

TENANT_ID = 1000000000000000001


def _headers(user_type: str, role: str) -> dict:
    token = create_access_token({
        "userId": "u-teacher" if user_type != "STUDENT" else "u-student",
        "realName": "王老师" if user_type != "STUDENT" else "学生甲",
        "userType": user_type,
        "tenantId": str(TENANT_ID),
        "tid": "demo",
        "activeContextId": "ctx",
        "currentRoleCode": role,
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def test_admin_workbench_snapshot_contract(client, db_mode):
    response = client.get(
        "/api/v1/admin/workbench-snapshot?pageSize=8",
        headers=_headers("TEACHER", "COUNSELOR"),
    )
    payload = response.json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert set(data) == {"summary", "count", "todos", "messages"}
    assert data["summary"]["role"] == "COUNSELOR"
    assert data["todos"]["page"] == 1
    assert data["todos"]["pageSize"] == 8
    assert isinstance(data["todos"]["items"], list)
    assert isinstance(data["count"]["byType"], dict)
    assert data["messages"]["unread"] >= 0


def test_student_cannot_access_admin_workbench_snapshot(client, db_mode):
    payload = client.get(
        "/api/v1/admin/workbench-snapshot",
        headers=_headers("STUDENT", "STUDENT"),
    ).json()
    assert payload["code"] == 403001
    assert payload["bizCode"] == "NO_PERMISSION"
