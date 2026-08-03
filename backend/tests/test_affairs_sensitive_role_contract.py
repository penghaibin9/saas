from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_risk_mental_detail_does_not_use_wildcard_permission():
    source = read("backend/app/services/affairs_risk_service.py")
    block = source.split("_MENTAL_DETAIL_ROLES", 1)[1].split("def _sensitive_view_audit", 1)[0]
    assert '{"PSYCHOLOGY_TEACHER", "SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN"}' in block
    assert 'has_permission(user or {}, "studentAffairs.risk.psyDetail.view")' not in block


def test_formal_mental_service_keeps_sa_admin_out_of_raw_detail():
    source = read("backend/app/services/affairs_mental_service.py")
    guard = read("backend/app/services/affairs_sensitive_audit_guard.py")
    assert '_PSY_DETAIL_ROLES = {"PSYCHOLOGY_TEACHER", "SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN"}' in source
    assert "STUDENT_AFFAIRS_ADMIN 不在此列" in source
    assert "mental._can_view_detail =" not in guard
    assert "mental._sensitive_view_audit =" not in guard
    assert "fail closed" in source.lower() or "fail-closed" in source.lower()
    assert "audit_health" in source


def test_talk_sensitive_role_and_actions_live_in_formal_service():
    service = read("backend/app/services/affairs_talk_service.py")
    guard = read("backend/app/services/affairs_talk_guard.py")
    assert '_PSY_ROLES = {"SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN", "PSYCHOLOGY_TEACHER"}' in service
    assert '"allowedActions"' in service
    assert "talk._can_view_psy =" not in guard
    assert "talk._talk_row =" not in guard
