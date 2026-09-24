from types import SimpleNamespace

import pytest

from app.modules.internship.services.internship_guidance_service import _guidance_limits
from app.modules.internship.services.internship_compliance_facts import _expected_count
from app.modules.internship.services import internship_compliance_facts
from app.modules.system_admin.services.security_change_legacy import _snapshot_item_count


@pytest.mark.parametrize('value', [True, False, None])
def test_boolean_batch_rules_keep_default_quantities(value):
    batch = SimpleNamespace(rules_config={'guidance': value})
    assert _guidance_limits(batch) == (2, 2)
    assert _expected_count({'checkin': value}, 'checkin', ['expectedCount'], 30) == 30


def test_explicit_quantity_zero_is_preserved():
    batch = SimpleNamespace(rules_config={'guidance': {'minCommunicationsPerMonth': 0, 'minVisitsPerTerm': 4}})
    assert _guidance_limits(batch) == (0, 4)
    assert _expected_count({'checkin': {'expectedCount': 0}}, 'checkin', ['expectedCount'], 30) == 0


@pytest.mark.parametrize('flag', [True, False, None])
def test_material_facts_boolean_sections_preserve_unspecified_quantity_defaults(monkeypatch, flag):
    class EmptyDatabase:
        def scalars(self, query):
            return SimpleNamespace(all=lambda: [])

        def scalar(self, query):
            return 0

    monkeypatch.setattr(internship_compliance_facts, '_tid', lambda: 7)
    record = SimpleNamespace(id=1, intern_start_date='2026-09-07', intern_end_date='2026-09-11')
    batch = SimpleNamespace(rules_config={}, start_date=None, end_date=None)
    expected = internship_compliance_facts.material_quantity_facts(EmptyDatabase(), record, batch)
    batch.rules_config = {'checkin': flag, 'guidance': flag, 'weeklyReport': flag}
    assert internship_compliance_facts.material_quantity_facts(EmptyDatabase(), record, batch) == expected
    assert expected['checkin']['expected'] == 5


@pytest.mark.parametrize('snapshot,expected', [
    ({'items': [{}, {}]}, 2), ({'items': []}, 0), ({'items': 3}, 3),
    ({'items': 0}, 0), ({'items': -1}, None), ({'items': True}, None),
    ({'items': '3'}, None), (None, None),
])
def test_activation_count_handles_historical_summaries_without_fabricating_detail(snapshot, expected):
    assert _snapshot_item_count(snapshot) == expected
