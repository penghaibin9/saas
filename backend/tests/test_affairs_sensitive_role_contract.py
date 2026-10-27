from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_risk_mental_detail_does_not_use_wildcard_permission(monkeypatch):
    from app.core import permissions
    from app.services.affairs_risk_service import _can_view_mental
    monkeypatch.setattr(permissions, "get_base_permission_patterns", lambda user: user.get("granted", set()))
    assert not _can_view_mental({"granted": {"studentAffairs.*", "studentAffairs.risk.*"}})
    assert _can_view_mental({"granted": {"studentAffairs.risk.psyDetail.view"}})


def test_formal_mental_service_keeps_sa_admin_out_of_raw_detail(monkeypatch):
    from app.core import permissions
    from app.services.affairs_mental_service import _can_view_detail
    source = read("backend/app/services/affairs_mental_service.py")
    guard = read("backend/app/services/affairs_sensitive_audit_guard.py")
    monkeypatch.setattr(permissions, "get_base_permission_patterns", lambda user: user.get("granted", set()))
    assert not _can_view_detail({"currentRoleCode": "STUDENT_AFFAIRS_ADMIN"}, 1, {1})
    assert not _can_view_detail({"currentRoleCode": "SCHOOL_ADMIN"}, 1, {1})
    authorized = {"granted": {"studentAffairs.risk.psyDetail.view"}}
    assert _can_view_detail(authorized, 1, {1})
    assert not _can_view_detail(authorized, 2, {1})
    assert "mental._can_view_detail =" not in guard
    assert "mental._sensitive_view_audit =" not in guard
    assert "fail closed" in source.lower() or "fail-closed" in source.lower()
    assert "get_audit_db_health" in source


def test_talk_sensitive_role_and_actions_live_in_formal_service():
    service = read("backend/app/services/affairs_talk_service.py")
    guard = read("backend/app/services/affairs_talk_guard.py")
    assert '_PSY_ROLES = {"SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN", "PSYCHOLOGY_TEACHER"}' in service
    assert '"allowedActions"' in service
    assert "talk._can_view_psy =" not in guard
    assert "talk._talk_row =" not in guard
