from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_work_order_detail_exposes_current_version():
    source = read("backend/app/services/campus_service_service.py")
    block = source.split("def _wo_row", 1)[1].split("def list_work_orders", 1)[0]
    assert '"version": int(x.version or 0)' in block


def test_mental_mobile_routes_use_stable_referral_id_parameter():
    source = read("backend/app/api/v1/mobile.py")
    for route in (
        '/teacher/mental/{referral_id}',
        '/teacher/mental/{referral_id}/follow',
        '/teacher/mental/{referral_id}/escalate',
        '/teacher/mental/{referral_id}/close',
    ):
        assert route in source
    mental_lines = "\n".join(line for line in source.splitlines() if "/teacher/mental/" in line)
    assert "{ref_id}" not in mental_lines


def test_missing_leave_version_contract_is_explicit_validation_error():
    source = read("backend/tests/test_affairs_four_end_hardening.py")
    assert 'missing.status_code == 400' in source
    assert 'missing.json()["bizCode"] == "VALIDATION_ERROR"' in source
