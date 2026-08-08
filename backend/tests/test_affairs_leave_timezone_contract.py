from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.services import affairs_leave_service as leave_svc


ROOT = Path(__file__).resolve().parents[2]


def test_leave_tenant_wall_clock_drops_timezone_without_changing_local_fields():
    local = datetime(2026, 8, 8, 18, 30, 45, tzinfo=timezone(timedelta(hours=8)))
    with patch.object(leave_svc, "local_now", return_value=local):
        assert leave_svc._tenant_wall_now() == datetime(2026, 8, 8, 18, 30, 45)


def test_actual_return_validation_never_compares_local_input_to_utc_wall_clock():
    source = (ROOT / "backend/app/services/affairs_leave_service.py").read_text(encoding="utf-8")
    assert source.count("ret > _tenant_wall_now()") == 2
    assert "ret > datetime.utcnow()" not in source
