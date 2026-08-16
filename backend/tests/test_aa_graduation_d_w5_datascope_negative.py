"""D-W5 public Graduation DataScope negatives.

COLLEGE_ADMIN has academicAffairs.* permission, so this suite proves data scope is an
independent authority: without an ACTIVE TeacherStudentScope row, a permission-authorized
college administrator must see zero Graduation data instead of silently falling back to
tenant-wide visibility.
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"


def _login(client, login_name: str, user_type: str) -> tuple[dict[str, str], dict]:
    response = client.post(
        "/api/v1/auth/mock-login",
        json={
            "tenantCode": "demo",
            "loginName": login_name,
            "userType": user_type,
            "clientType": "PC",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}, data


def _items(payload: dict) -> list[dict]:
    data = payload.get("data") or {}
    return list(data.get("list") or data.get("items") or [])


def test_permission_authorized_college_admin_without_scope_cannot_see_tenant_graduation_batch(client, db_mode):
    del db_mode
    school_headers, school_login = _login(client, "school_admin01", "ADMIN")
    assert school_login["currentRole"]["roleCode"] == "SCHOOL_ADMIN"

    created = client.post(
        f"{BASE}/graduation-audit-batches",
        headers=school_headers,
        json={"batchName": "D-W5-datascope-sentinel", "gradeYear": "2026"},
    )
    assert created.status_code == 200, created.text
    batch_id = str(created.json()["data"]["batchId"])

    school_list = client.get(f"{BASE}/graduation-audit-batches?page=1&pageSize=50", headers=school_headers)
    assert school_list.status_code == 200, school_list.text
    assert batch_id in {str(item.get("batchId")) for item in _items(school_list.json())}

    college_headers, college_login = _login(client, "college_admin01", "ADMIN")
    assert college_login["currentRole"]["roleCode"] == "COLLEGE_ADMIN"
    # Permission is intentionally broad on this canonical role; scope must still fail closed.
    assert college_login["dataScope"]["scope"] == "COLLEGE"

    college_list = client.get(f"{BASE}/graduation-audit-batches?page=1&pageSize=50", headers=college_headers)
    assert college_list.status_code == 200, college_list.text
    payload = college_list.json()
    assert payload.get("code") == 0, payload
    assert batch_id not in {str(item.get("batchId")) for item in _items(payload)}
    assert int((payload.get("data") or {}).get("total") or 0) == 0, payload


def test_scope_empty_college_admin_cannot_infer_known_batch_from_results_endpoint(client, db_mode):
    del db_mode
    school_headers, _ = _login(client, "school_admin01", "ADMIN")
    created = client.post(
        f"{BASE}/graduation-audit-batches",
        headers=school_headers,
        json={"batchName": "D-W5-datascope-detail-sentinel", "gradeYear": "2026"},
    )
    assert created.status_code == 200, created.text
    batch_id = str(created.json()["data"]["batchId"])

    college_headers, _ = _login(client, "college_admin01", "ADMIN")
    results = client.get(
        f"{BASE}/graduation-audit-batches/{batch_id}/results?page=1&pageSize=20",
        headers=college_headers,
    )
    assert results.status_code == 200, results.text
    payload = results.json()
    assert payload.get("code") == 0, payload
    # The service deliberately returns an empty page for a scope-empty authorized caller,
    # preventing existence/row-count disclosure for a tenant-wide batch id the caller learned elsewhere.
    assert _items(payload) == []
    assert int((payload.get("data") or {}).get("total") or 0) == 0, payload
