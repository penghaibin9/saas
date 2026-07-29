from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_leave_flow_tests_seed_real_assignees_and_org_relations():
    source = read("backend/tests/test_affairs_leave.py")
    for marker in (
        "AffairsCounselorAssignment",
        "College",
        "Major",
        "UserRole",
        "COLLEGE_ADMIN",
        "STUDENT_AFFAIRS_ADMIN",
        'scope_type="COLLEGE"',
    ):
        assert marker in source


def test_legacy_student_detail_no_longer_renders_leave_records():
    source = read("backend/app/services/affairs_student_ledger_guard.py")
    assert "service._leave_row" not in source
    assert "select(CsLeave)" not in source
    assert '"leaves":' not in source


def test_route_contract_tests_use_openapi_not_private_router_shape():
    matrix = read("backend/tests/test_affairs_four_end_core_flow_matrix.py")
    hardening = read("backend/tests/test_affairs_four_end_hardening.py")
    assert 'app.openapi().get("paths", {})' in matrix
    assert 'client.app.openapi().get("paths", {})' in hardening
