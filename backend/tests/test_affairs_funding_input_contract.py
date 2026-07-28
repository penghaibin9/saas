from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_funding_tests_do_not_send_full_bank_numbers():
    for name in ("test_affairs_funding_ext.py", "test_affairs_funding_disbursement.py"):
        text = read("backend/tests/" + name)
        assert "6222000012346411" not in text
        assert "6222888888886411" not in text
        assert '"bankLast4": "6411"' in text


def test_disbursement_fixture_uses_real_students():
    text = read("backend/tests/test_affairs_funding_disbursement.py")
    assert "900000 + i" not in text
    assert "StudentProfile(" in text
    assert "student_ids" in text


def test_monthly_work_study_inputs_include_hours():
    text = read("backend/tests/test_affairs_funding_ext.py")
    assert '"monthCode": "2025-11"' in text and '"workHours": 48' in text
    assert '"monthCode": "2025-12"' in text and '"workHours": 32' in text
