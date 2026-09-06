"""Four-role Academic V8.1 Browser actors must preserve the exact 20K topology."""
from pathlib import Path

from scripts import audit_academic_v81_browser_fixtures as preflight


def test_four_surfaces_use_canonical_existing_20k_identities():
    assert preflight.ACTORS == {
        "staffPc": {
            "loginName": "admin2",
            "requiredRole": "SCHOOL_ADMIN",
            "requiredPermissions": [
                "academicAffairs.schedule.view",
                "academicAffairs.scheduleChange.view",
                "academicAffairs.scheduleChange.collegeReview",
                "academicAffairs.scheduleChange.academicReview",
            ],
        },
        "teacherMini": {"loginName": "sbx_t0257", "requiredRole": "ACADEMIC_TEACHER"},
        "studentPc": {"loginName": "2024S0002", "requiredRole": "STUDENT"},
        "studentMini": {"loginName": "2024S0002", "requiredRole": "STUDENT"},
    }
    root = Path(__file__).resolve().parents[1]
    activation_source = (root / "scripts/e2e_set_academic_passwords_db.py").read_text(encoding="utf-8")
    assert '"sbx_aa001": "COLLEGE_ADMIN"' in activation_source
    assert '"sbx_t0257": "ACADEMIC_TEACHER"' in activation_source
    assert '"2024S0002": "STUDENT"' in activation_source
    assert '"2025S0001": "STUDENT"' in activation_source
    assert 'values != ["sbx_aa001", "sbx_t0257", "2024S0002", "2025S0001"]' in activation_source


def test_preflight_is_read_only_and_never_emits_passwords():
    root = Path(__file__).resolve().parents[1]
    source = (root / "scripts/audit_academic_v81_browser_fixtures.py").read_text(encoding="utf-8")
    assert "SET SESSION TRANSACTION READ ONLY" in source
    assert "START TRANSACTION READ ONLY" in source
    assert '"containsPasswords": False' in source
    assert "db.commit()" not in source
    assert "password_hash" not in source


def test_activation_updates_only_allowlisted_existing_password_hashes():
    root = Path(__file__).resolve().parents[1]
    source = (root / "scripts/e2e_set_academic_passwords_db.py").read_text(encoding="utf-8")
    assert '"plannedEntityCreates": 0' in source
    assert "user.password_hash = password_hash" in source
    assert "db.add(" not in source
    assert "db.delete(" not in source
    assert "_target_logins()" in source
