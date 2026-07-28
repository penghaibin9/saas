"""鉴权上下文保留稳定学生身份，同时避免改变主线认证热路径。"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app/core/security.py").read_text(encoding="utf-8")
AUTH_SERVICE = (ROOT / "app/services/auth_service_db.py").read_text(encoding="utf-8")


def test_login_claims_include_stable_student_identity():
    assert 'claims["studentId"] = str(student_id)' in AUTH_SERVICE
    assert '"studentId": claims.get("studentId")' in SOURCE


def test_auth_core_preserves_current_main_subject_validation_flow():
    assert "validate_token_subject(user)" in SOURCE
    assert "user = validate_token_subject(user)" not in SOURCE


def test_auth_hot_path_does_not_query_student_profile_again():
    assert "_refresh_current_student_identity" not in SOURCE
    assert "get_sessionmaker" not in SOURCE
    assert "StudentProfile" not in SOURCE
