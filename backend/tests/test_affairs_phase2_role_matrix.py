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
    "COUNSELOR": (("dashboard", "studentAffairs.dashboard.view", True), ("workbench", "workbench.home.view", True), ("list", "studentAffairs.risk.view", True), ("detail", "studentAffairs.leave.view", True), ("status_write", "studentAffairs.risk.handle", True), ("funding_first_review", "studentAffairs.funding.approve", True), ("stats", "studentAffairs.stats.view", True), ("sensitive", "studentAffairs.mental.manage", False)),
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


def test_funding_school_review_assignee_override_is_domain_specific(monkeypatch):
    """Funding 校审使用业务角色池；共享 SCHOOL_REVIEW 与 Funding 其他节点都不得被连带改写。"""
    from app.services import affairs_assignee_service as shared
    from app.services import affairs_funding_scan_guard as guard

    # 共享节点仍保持历史语义，避免影响困难认定/处分等其他业务。
    assert shared._NODE_ROLES["SCHOOL_REVIEW"] == {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN"}
    assert set(guard._FUNDING_SCHOOL_REVIEW_ROLES) == {
        "STUDENT_AFFAIRS",
        "STUDENT_AFFAIRS_ADMIN",
        "SA_ADMIN",
        "FUNDING_TEACHER",
    }
    assert "SCHOOL_ADMIN" not in guard._FUNDING_SCHOOL_REVIEW_ROLES

    captured = {}

    def fake_require_assignee_id(db, node, *, student_id=None, role_codes=None):
        captured.update({"db": db, "node": node, "studentId": student_id, "roleCodes": set(role_codes or ())})
        return 88001

    monkeypatch.setattr(shared, "require_assignee_id", fake_require_assignee_id)
    monkeypatch.setattr(guard, "_ORIGINAL_ASSIGNEE_FOR", lambda db, node, student_id: 77001)

    marker_db = object()
    assert guard._assignee_for(marker_db, "SCHOOL_REVIEW", 901) == 88001
    assert captured == {
        "db": marker_db,
        "node": "SCHOOL_REVIEW",
        "studentId": 901,
        "roleCodes": set(guard._FUNDING_SCHOOL_REVIEW_ROLES),
    }
    # 辅导员/学院节点仍交回原 Funding resolver，修复只命中校级资助受理人。
    assert guard._assignee_for(marker_db, "COLLEGE_REVIEW", 901) == 77001


def test_counselor_discipline_removal_permission_is_narrow():
    """辅导员仅获得处分解除初审，不得顺带获得正式处分审批或申诉复核。"""
    user = {"currentRoleCode": "COUNSELOR", "userType": "TEACHER", "userId": "matrix"}
    assert has_permission(user, "studentAffairs.discipline.remove.approve") is True
    assert has_permission(user, "studentAffairs.discipline.approve") is False
    assert has_permission(user, "studentAffairs.discipline.appeal.review") is False


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
