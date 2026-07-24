from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services import affairs_sla


def test_risk_levels_have_distinct_deadlines():
    critical = affairs_sla.get_risk_sla("CRITICAL")
    low = affairs_sla.get_risk_sla("LOW")
    assert critical == {"assignHours": 1, "processHours": 24}
    assert low == {"assignHours": 8, "processHours": 120}
    assert critical["processHours"] < low["processHours"]


def test_json_overrides_and_invalid_values_fall_back(monkeypatch):
    monkeypatch.setattr(affairs_sla, "settings", SimpleNamespace(
        AFFAIRS_RISK_NEW_ASSIGN_HOURS=4,
        AFFAIRS_RISK_ASSIGNED_PROCESS_HOURS=72,
        AFFAIRS_RISK_SLA_JSON='{"HIGH":{"assignHours":3,"processHours":36},"LOW":{"assignHours":0}}',
        AFFAIRS_LEAVE_SLA_JSON='{"approvalHours":12,"nearDueHours":"bad"}',
    ))
    assert affairs_sla.get_risk_sla("HIGH") == {"assignHours": 3.0, "processHours": 36.0}
    assert affairs_sla.get_risk_sla("LOW") == {"assignHours": 8, "processHours": 120}
    assert affairs_sla.get_leave_sla()["approvalHours"] == 12.0
    assert affairs_sla.get_leave_sla()["nearDueHours"] == 12


def test_risk_overdue_uses_level_and_status(monkeypatch):
    monkeypatch.setattr(affairs_sla, "settings", SimpleNamespace(
        AFFAIRS_RISK_NEW_ASSIGN_HOURS=4,
        AFFAIRS_RISK_ASSIGNED_PROCESS_HOURS=72,
        AFFAIRS_RISK_SLA_JSON="",
        AFFAIRS_LEAVE_SLA_JSON="",
    ))
    now = datetime(2026, 1, 1, 12)
    critical = SimpleNamespace(status="NEW", risk_level="CRITICAL", created_at=now - timedelta(hours=2))
    low = SimpleNamespace(status="NEW", risk_level="LOW", created_at=now - timedelta(hours=2))
    assigned = SimpleNamespace(status="ASSIGNED", risk_level="HIGH", created_at=now,
                               assigned_at=now - timedelta(hours=49))
    assert affairs_sla.risk_is_overdue(critical, now)
    assert not affairs_sla.risk_is_overdue(low, now)
    assert affairs_sla.risk_is_overdue(assigned, now)
    assert affairs_sla.risk_due_at(critical) == critical.created_at + timedelta(hours=1)
