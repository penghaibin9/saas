"""学工第二阶段八角色验收矩阵：8 角色 × 8 项权限断言 = 至少 64 条。"""
from __future__ import annotations

import pytest

from app.core.permissions import has_permission

BASE = "/api/v1/student-affairs"

ROLE_CODES = {
    "COUNSELOR": "COUNSELOR",
    "COLLEGE_SA": "COLLEGE_ADMIN",
    "STUDENT_AFFAIRS_ADMIN": "STUDENT_AFFAIRS_ADMIN",
    "PSYCHOLOGY_TEACHER": "PSYCHOLOGY_TEACHER",
    "FUNDING_TEACHER": "FUNDING_TEACHER",
    "DORM_MANAGER": "DORM_MANAGER",
    "YOUTH_LEAGUE": "YOUTH_LEAGUE",
    "SCHOOL_LEADER": "LEADER",
}

MATRIX = {
    "COUNSELOR": (("dashboard", "studentAffairs.dashboard.view", True), ("workbench", "workbench.home.view", True), ("list", "studentAffairs.risk.view", True), ("detail", "studentAffairs.leave.view", True), ("status_write", "studentAffairs.risk.handle", True), ("cross_write", "studentAffairs.funding.approve", False), ("stats", "studentAffairs.stats.view", True), ("sensitive", "studentAffairs.mental.manage", False)),
    "COLLEGE_SA": (("dashboard", "studentAffairs.dashboard.view", True), ("workbench", "workbench.home.view", True), ("list", "studentAffairs.risk.view", True), ("detail", "studentAffairs.leave.view", True), ("status_write", "studentAffairs.risk.handle", True), ("cross_write", "systemAdmin.user.manage", False), ("stats", "studentAffairs.stats.view", True), ("sensitive", "studentAffairs.mental.manage", True)),
    "STUDENT_AFFAIRS_ADMIN": (("dashboard", "studentAffairs.dashboard.view", True), ("workbench", "workbench.home.view", True), ("list", "studentAffairs.risk.view", True), ("detail", "studentAffairs.leave.view", True), ("status_write", "studentAffairs.risk.handle", True), ("cross_write", "academicAffairs.grade.publish", False), ("stats", "studentAffairs.stats.view", True), ("sensitive", "studentAffairs.mental.manage", True)),
    "PSYCHOLOGY_TEACHER": (("dashboard", "studentAffairs.dashboard.view", False), ("workbench", "workbench.home.view", True), ("list", "studentAffairs.risk.view", True), ("detail", "studentAffairs.talk.view", True), ("status_write", "studentAffairs.risk.handle", True), ("cross_write", "studentAffairs.funding.approve", False), ("stats", "studentAffairs.stats.view", True), ("sensitive", "studentAffairs.mental.manage", True)),
    "FUNDING_TEACHER": (("dashboard", "studentAffairs.dashboard.view", True), ("workbench", "workbench.home.view", True), ("list", "studentAffairs.funding.view", True), ("detail", "studentAffairs.aid.view", True), ("status_write", "studentAffairs.funding.approve", True), ("cross_write", "studentAffairs.risk.handle", False), ("stats", "studentAffairs.stats.view", True), ("sensitive", "studentAffairs.aid.view", True)),
    "DORM_MANAGER": (("dashboard", "studentAffairs.dashboard.view", False), ("workbench", "workbench.home.view", True), ("list", "studentAffairs.dorm.view", True), ("detail", "studentAffairs.dorm.view", True), ("status_write", "studentAffairs.dorm.checkin", True), ("cross_write", "studentAffairs.risk.handle", False), ("stats", "studentAffairs.stats.view", False), ("sensitive", "studentAffairs.mental.manage", False)),
    "YOUTH_LEAGUE": (("dashboard", "studentAffairs.dashboard.view", True), ("workbench", "workbench.home.view", True), ("list", "studentAffairs.club.view", True), ("detail", "studentAffairs.org.view", True), ("status_write", "studentAffairs.club.manage", True), ("cross_write", "studentAffairs.funding.approve", False), ("stats", "studentAffairs.stats.view", True), ("sensitive", "studentAffairs.mental.manage", False)),
    "SCHOOL_LEADER": (("dashboard", "studentAffairs.dashboard.view", True), ("workbench", "workbench.home.view", True), ("list", "studentAffairs.risk.view", True), ("detail", "studentAffairs.leave.view", True), ("status_write", "studentAffairs.risk.handle", False), ("cross_write", "studentAffairs.funding.approve", False), ("stats", "studentAffairs.stats.view", True), ("sensitive", "studentAffairs.mental.manage", False)),
}


@pytest.mark.parametrize(
    "role_name,permission,expected",
    [(role, code, expected) for role, checks in MATRIX.items() for _item, code, expected in checks],
    ids=[f"{role}-{item}" for role, checks in MATRIX.items() for item, _code, _expected in checks],
)
def test_eight_role_permission_matrix(role_name, permission, expected):
    """64 条：每角色恰好八项，角色码与当前 ROLE_PERMISSIONS 同源。"""
    user = {"currentRoleCode": ROLE_CODES[role_name], "userType": "TEACHER", "userId": "matrix"}
    assert has_permission(user, permission) is expected


def _headers_or_skip(client, login_name, expected_role):
    response = client.post("/api/v1/auth/mock-login", json={"loginName": login_name, "password": "any"})
    data = response.json().get("data") if response.headers.get("content-type", "").startswith("application/json") else None
    if response.status_code != 200 or not isinstance(data, dict) or not data.get("accessToken"):
        pytest.skip(f"mock account {login_name} unavailable")
    if (data.get("currentRole") or {}).get("roleCode") != expected_role:
        pytest.skip(f"mock account {login_name} does not provide {expected_role}")
    return {"Authorization": f"Bearer {data['accessToken']}"}


@pytest.mark.parametrize("login_name,role_code,path", [
    ("counselor01", "COUNSELOR", "/risk/records"),
    ("funding01", "FUNDING_TEACHER", "/funding/projects"),
    ("dorm01", "DORM_MANAGER", "/dorm/buildings"),
    ("youth01", "YOUTH_LEAGUE", "/clubs"),
])
def test_role_domain_endpoint_smoke(client, db_mode, login_name, role_code, path):
    """账号未预置时跳过；预置后本职列表不得被权限网关拒绝。"""
    response = client.get(f"{BASE}{path}", headers=_headers_or_skip(client, login_name, role_code))
    assert response.status_code != 403, response.text
