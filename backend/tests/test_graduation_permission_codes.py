"""毕业设计中心 permissionCode 门禁回归。

这组测试不依赖业务数据：只验证路由在进入服务层前已经按当前角色收敛。
"""
from __future__ import annotations

from app.core.permissions import has_permission
from app.core.graduation_permissions import graduation_permission_for
from app.core.security import create_access_token


def _headers(role: str, user_type: str = "TEACHER") -> dict[str, str]:
    token = create_access_token({
        "userId": f"test-{role}",
        "realName": role,
        "userType": user_type,
        "tid": "demo",
        "tenantId": "1000000000000000001",
        "activeContextId": "ctx",
        "currentRoleCode": role,
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def test_graduation_role_permission_templates_are_least_privilege():
    mentor = {"currentRoleCode": "GD_MENTOR", "userType": "TEACHER"}
    assert has_permission(mentor, "graduationDesign.dashboard.view")
    assert has_permission(mentor, "graduationDesign.proposal.review")
    assert not has_permission(mentor, "graduationDesign.grade.publish")
    assert not has_permission(mentor, "graduationDesign.archive.file")

    expert = {"currentRoleCode": "GD_DEFENSE_EXPERT", "userType": "TEACHER"}
    assert has_permission(expert, "graduationDesign.defense.score")
    assert not has_permission(expert, "graduationDesign.defense.publish")


def test_request_permission_resolver_is_fail_closed_for_writes():
    assert graduation_permission_for("GET", "/api/v1/graduation/dashboard") == "graduationDesign.dashboard.view"
    assert graduation_permission_for("POST", "/api/v1/graduation/batches") == "graduationDesign.batch.create"
    assert graduation_permission_for("DELETE", "/api/v1/graduation/unknown/new-endpoint") is None
    assert graduation_permission_for(
        "POST", "/api/v1/graduation/proposals/123/review"
    ) == "graduationDesign.proposal.review"
    assert graduation_permission_for(
        "POST", "/api/v1/graduation/defense-groups/123/publish"
    ) == "graduationDesign.defense.publish"
    assert graduation_permission_for(
        "POST", "/api/v1/graduation/gd-grades/123/publish"
    ) == "graduationDesign.grade.publish"
    assert graduation_permission_for(
        "POST", "/api/v1/graduation/proposals/export"
    ) == "graduationDesign.proposal.export"
    assert graduation_permission_for(
        "POST", "/api/v1/graduation/gd-taskbooks/123/export-pdf"
    ) == "graduationDesign.taskbook.export"
    assert graduation_permission_for(
        "POST", "/api/v1/graduation/gd-plagiarism/123/result"
    ) == "graduationDesign.plagiarism.result"
    assert graduation_permission_for(
        "POST", "/api/v1/graduation/gd-plagiarism/123/dispute/review"
    ) == "graduationDesign.plagiarism.disputeReview"


def test_unassigned_staff_is_denied_graduation_center(client):
    response = client.get("/api/v1/graduation/dashboard", headers=_headers("STAFF"))
    assert response.status_code == 403


def test_mentor_can_view_but_cannot_publish_defense(client):
    headers = _headers("GD_MENTOR")
    assert has_permission(
        {"currentRoleCode": "GD_MENTOR", "userType": "TEACHER"},
        "graduationDesign.dashboard.view",
    )

    response = client.post(
        "/api/v1/graduation/defense-groups/nonexistent/publish",
        headers=headers,
        json={},
    )
    assert response.status_code == 403


def test_mentor_cannot_call_unclassified_management_write(client):
    response = client.post(
        "/api/v1/graduation/batches",
        headers=_headers("GD_MENTOR"),
        json={},
    )
    assert response.status_code == 403


def test_mentor_cannot_read_graduation_configuration_ledgers(client):
    headers = _headers("GD_MENTOR")
    assert client.get("/api/v1/graduation/batches", headers=headers).status_code == 403
    assert client.get("/api/v1/graduation/gd-mentors", headers=headers).status_code == 403
    assert client.get("/api/v1/graduation/gd-defense-experts", headers=headers).status_code == 403


def test_organization_admin_without_verified_scope_claim_is_denied(client):
    response = client.get(
        "/api/v1/graduation/dashboard",
        headers=_headers("GD_COLLEGE_ADMIN"),
    )
    assert response.status_code == 403


def test_organization_admin_context_allows_missing_claim_with_hint(client):
    response = client.get(
        "/api/v1/graduation/context",
        headers=_headers("GD_COLLEGE_ADMIN"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("code") == 0
    data = body.get("data") or {}
    assert data.get("roleNeedsOrgScope") is True
    assert data.get("scopeConfigured") is False
    assert "学院" in (data.get("scopeHint") or "")


def test_organization_admin_with_verified_scope_claim_passes_gate(client):
    """有 collegeId claim 时不再被组织范围门禁挡下；/context 不依赖业务库。"""
    token = create_access_token({
        "userId": "test-GD_COLLEGE_ADMIN",
        "realName": "GD_COLLEGE_ADMIN",
        "userType": "TEACHER",
        "tid": "demo",
        "tenantId": "1000000000000000001",
        "activeContextId": "ctx",
        "currentRoleCode": "GD_COLLEGE_ADMIN",
        "clientType": "PC",
        "collegeId": "1001",
        "collegeIds": ["1001"],
    })
    response = client.get(
        "/api/v1/graduation/context",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = (response.json() or {}).get("data") or {}
    assert data.get("scopeConfigured") is True
    assert data.get("collegeId") == "1001"
    assert not (data.get("scopeHint") or "").strip()


def test_school_admin_retains_tenant_scoped_full_access(client):
    admin = {"currentRoleCode": "SCHOOL_ADMIN", "userType": "ADMIN"}
    assert has_permission(admin, "graduationDesign.dashboard.view")
    assert has_permission(admin, "graduationDesign.grade.publish")
    assert has_permission(admin, "graduationDesign.archive.file")
