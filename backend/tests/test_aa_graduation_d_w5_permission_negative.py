"""D-W5 runtime permission negatives for Graduation public routes.

These tests intentionally use the canonical mock ACADEMIC_TEACHER identity. The teacher
has a narrow explicit academic permission set but does not own graduation view/manage/
final permissions. Public route dependencies must reject the request before any domain
lookup or mutation, including when the supplied resource id does not exist.
"""
from __future__ import annotations

import pytest

BASE = "/api/v1/academic-affairs"


def _token(client, login_name: str) -> str:
    response = client.post(
        "/api/v1/auth/mock-login",
        json={
            "tenantCode": "demo",
            "loginName": login_name,
            "userType": "TEACHER",
            "clientType": "PC",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["currentRole"]["roleCode"] == "ACADEMIC_TEACHER"
    return str(payload["accessToken"])


def _headers(client) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(client, 'academic01')}"}


def _assert_no_permission(response, *, label: str) -> None:
    assert response.status_code == 403, f"{label}: {response.status_code} {response.text}"
    body = response.json()
    assert body.get("code") == "NO_PERMISSION", f"{label}: {body}"


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("GET", f"{BASE}/graduation-audit-batches", None),
        ("POST", f"{BASE}/graduation-audit-batches", {"batchName": "forbidden", "gradeYear": "2026"}),
        ("GET", f"{BASE}/graduation-audit-batches/987654321/results?page=1&pageSize=20", None),
        ("POST", f"{BASE}/graduation-audit-batches/987654321/precheck", None),
        ("GET", f"{BASE}/graduation-audit-results/987654321", None),
        ("POST", f"{BASE}/graduation-audit-results/987654321/final", {"decision": "GRADUATED"}),
    ],
)
def test_academic_teacher_cannot_cross_graduation_permission_boundary(
    client,
    method: str,
    path: str,
    json_body: dict | None,
):
    kwargs = {"headers": _headers(client)}
    if json_body is not None:
        kwargs["json"] = json_body
    response = client.request(method, path, **kwargs)
    _assert_no_permission(response, label=f"{method} {path}")


def test_graduation_permission_denial_happens_before_missing_resource_lookup(client):
    headers = _headers(client)
    denied = client.post(
        f"{BASE}/graduation-audit-batches/9223372036854775000/precheck",
        headers=headers,
    )
    _assert_no_permission(denied, label="missing batch precheck")
    assert "不存在" not in str(denied.json().get("message") or "")


def test_student_identity_cannot_use_staff_graduation_route_even_with_valid_token(client):
    login = client.post(
        "/api/v1/auth/mock-login",
        json={
            "tenantCode": "demo",
            "loginName": "student01",
            "userType": "STUDENT",
            "clientType": "PC",
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["accessToken"]
    response = client.get(
        f"{BASE}/graduation-audit-batches",
        headers={"Authorization": f"Bearer {token}"},
    )
    _assert_no_permission(response, label="student graduation batch list")
