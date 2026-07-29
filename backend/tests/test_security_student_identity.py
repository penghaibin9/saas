"""稳定学生身份由 latest main 解析器提供，教务只保留薄兼容导入。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECURITY = (ROOT / "app/core/security.py").read_text(encoding="utf-8")
AUTH_SERVICE = (ROOT / "app/services/auth_service_db.py").read_text(encoding="utf-8")
RESOLVER = (ROOT / "app/services/mobile_student_service.py").read_text(encoding="utf-8")
FACADE = (ROOT / "app/services/mobile_student_identity_facade.py").read_text(encoding="utf-8")


def test_login_claims_keep_stable_student_identity_for_future_consumers():
    assert 'claims["studentId"] = str(student_id)' in AUTH_SERVICE


def test_main_student_resolution_prefers_stable_identity_and_account_binding():
    assert 'sid = u.get("studentId")' in RESOLVER
    assert "get_student_id_by_user" in RESOLVER
    assert "StudentProfile.id == int(sid)" in RESOLVER
    assert "len(rows) == 1" in RESOLVER


def test_academic_compatibility_facade_has_no_second_identity_implementation():
    assert "from app.services.mobile_student_service import resolve_student" in FACADE
    assert "select(" not in FACADE
    assert "StudentProfile" not in FACADE
    assert "get_student_id_by_user" not in FACADE


def test_auth_core_remains_byte_compatible_in_behavior_with_current_main():
    assert "validate_token_subject(user)" in SECURITY
    assert "user = validate_token_subject(user)" not in SECURITY
    assert '"studentId": claims.get("studentId")' not in SECURITY


def test_auth_hot_path_does_not_query_student_profile_again():
    assert "_refresh_current_student_identity" not in SECURITY
    assert "get_sessionmaker" not in SECURITY
    assert "StudentProfile" not in SECURITY
