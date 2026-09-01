"""D4 migration and public contract guards."""
from pathlib import Path


def test_d4_migration_is_serial_preflighted_and_safe_to_downgrade():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260901_dorm_checkout_d4.py"
    source = path.read_text(encoding="utf-8")
    assert 'down_revision = "20260901_orientation_self_o3"' in source
    assert "D4 stay/bed preflight failed before DDL" in source
    assert "occupied_without_stay" in source and "duplicate_active_student" in source
    assert "D4 downgrade blocked: checkout workflow data exists" in source


def test_d4_checkout_and_history_contracts_are_explicit():
    root = Path(__file__).parents[1]
    api = (root / "app" / "api" / "v1" / "student_affairs.py").read_text(encoding="utf-8")
    service = (root / "app" / "services" / "affairs_dorm_stay_service.py").read_text(encoding="utf-8")
    assert '/dorm/checkout-requests' in api and '/dorm/stays' in api
    assert "PENDING_CONFIRMATION" in service and "TRANSFER_IN_PROGRESS" in service
    assert "stay.status = \"ENDED\"" in service
    assert 'bed.status = "VACANT"' in service
