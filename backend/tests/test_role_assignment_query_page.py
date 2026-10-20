"""Query shape guards supplement read-only MySQL ledger verification."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

from app.services.role_assignment_query_service import list_page


def test_requested_page_is_limited_before_any_detail_hydration():
    db = Mock()
    summary = dict(total=22241, EXPIRING_SOON=0, EXPIRED_NOT_RECLAIMED=0,
                   UNREVIEWED_ACROSS_TERM=22239, UNKNOWN_SOURCE=22239)
    db.execute.side_effect = [Mock(one=lambda: SimpleNamespace(_mapping=summary)), []]
    db.scalar.return_value = 1
    result = list_page(db, tenant_id=1007, now=datetime(2026, 9, 13),
                       role_code='', bucket='', page=445, page_size=50)
    query = db.execute.call_args_list[1].args[0]
    assert query._limit_clause.value == 50
    assert query._offset_clause.value == 22200
    assert list(query.selected_columns.keys()) == ['kind', 'id']
    assert db.execute.call_count == 2  # Empty page does not fetch accounts or links.
    assert result['total'] == 22241 and result['list'] == []


def test_empty_school_aggregates_return_zero_instead_of_null():
    db = Mock()
    summary = dict(total=0, EXPIRING_SOON=0, EXPIRED_NOT_RECLAIMED=0,
                   UNREVIEWED_ACROSS_TERM=0, UNKNOWN_SOURCE=0)
    db.execute.side_effect = [Mock(one=lambda: SimpleNamespace(_mapping=summary)), []]
    db.scalar.return_value = 0
    result = list_page(db, tenant_id=1008, now=datetime(2026, 9, 13),
                       role_code='', bucket='', page=1, page_size=50)
    assert result['total'] == 0 and result['list'] == []
    assert all(v == 0 for v in result['summary'].values())
