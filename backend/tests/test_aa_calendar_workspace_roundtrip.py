"""Opening-condition calendar UI flows through formal HTTP routers and real MySQL."""
from test_aa_term import BASE, TID, _hdr, _term


def _govern(term_id):
    from app.db.session import get_sessionmaker
    from app.models.academic_calendar import AcademicCalendarGovernance, ACTIVE_SENTINEL
    with get_sessionmaker()() as db:
        db.add(AcademicCalendarGovernance(tenant_id=TID, term_id=int(term_id), calendar_type='ACADEMIC', timezone='Asia/Shanghai', governance_status='ACTIVE', active_key=ACTIVE_SENTINEL))
        db.commit()


def test_calendar_publish_cannot_switch_away_from_governed_current(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    current = _term(client, headers).json()['data']['termId']
    draft = _term(client, headers, no=2).json()['data']['termId']
    assert client.post(f'{BASE}/terms/{current}/publish', headers=headers).status_code == 200
    _govern(current)
    assert client.post(f'{BASE}/time-slots', headers=headers, json={'slotNo': 1}).status_code == 200
    response = client.post(f'{BASE}/terms/{draft}/calendar/publish', headers=headers)
    assert response.status_code == 409, response.text
    terms = client.get(f'{BASE}/terms', headers=headers).json()['data']['items']
    assert next(t for t in terms if t['termId'] == draft)['status'] == 'DRAFT'
    assert [t['termId'] for t in terms if t['isCurrent']] == [current]


def test_calendar_publication_locks_events_and_records_compat_switch(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    term_id = _term(client, headers).json()['data']['termId']
    path = f'{BASE}/terms/{term_id}/calendar'
    assert client.post(path + '/publish', headers=headers).status_code == 400
    assert client.post(f'{BASE}/time-slots', headers=headers, json={'slotNo': 1}).status_code == 200
    event = client.post(path, headers=headers, json={'eventType': 'HOLIDAY', 'startDate': '2026-10-01', 'endDate': '2026-10-07'}).json()['data']
    assert client.post(path + '/publish', headers=headers).status_code == 200
    assert client.post(path + '/publish', headers=headers).status_code == 200
    assert client.put(path + '/' + event['eventId'], headers=headers, json={'remark': '不能修改已发布校历'}).status_code == 409
    assert client.delete(path + '/' + event['eventId'], headers=headers).status_code == 409
    rows = client.get(f'{BASE}/terms/switch-log', headers=headers).json()['data']['items']
    assert any(row['toTermId'] == term_id for row in rows), rows


def test_calendar_dates_and_event_type_are_validated_and_type_change_clears_swap(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    term_id = _term(client, headers).json()['data']['termId']
    path = f'{BASE}/terms/{term_id}/calendar'
    for change in ({'eventType': 'UNKNOWN'}, {'endDate': '2026-09-01'}, {'endDate': 'bad-date'}, {'eventType': 'SWAP', 'swapToDate': '2026-09-08'}):
        response = client.post(path, headers=headers, json={'eventType': 'TEACHING', 'startDate': '2026-09-08', **change})
        assert response.status_code in (400, 422), response.text
    assert client.get(path, headers=headers).json()['data']['items'] == []
    event = client.post(path, headers=headers, json={'eventType': 'SWAP', 'startDate': '2026-10-02', 'swapToDate': '2026-10-10', 'remark': '调休验收'}).json()['data']
    updated = client.put(path + '/' + event['eventId'], headers=headers, json={'eventType': 'HOLIDAY', 'startDate': '2026-10-02', 'endDate': '2026-10-02', 'swapToDate': None, 'remark': ''})
    assert updated.status_code == 200, updated.text
    assert updated.json()['data']['swapToDate'] is None
    assert updated.json()['data']['remark'] == ''


def test_term_weeks_and_calendar_agree_on_exam_range_and_explicit_events(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    term_id = _term(client, headers).json()['data']['termId']
    path = f'{BASE}/terms/{term_id}'
    assert client.put(path + '/teaching-weeks', headers=headers, json={'teachingWeeks': 18, 'examWeekStart': 17}).status_code == 200
    assert client.post(path + '/calendar', headers=headers, json={'eventType': 'EXAM', 'startDate': '2026-09-08', 'endDate': '2026-09-10'}).status_code == 200
    weeks = client.get(path + '/weeks', headers=headers).json()['data']['items']
    calendar = client.get(path + '/week-calendar', headers=headers).json()['data']['weeks']
    assert [w['weekType'] for w in weeks] == [w['weekType'] for w in calendar]
    assert weeks[1]['weekType'] == weeks[16]['weekType'] == weeks[17]['weekType'] == 'EXAM'


def test_governed_calendar_publication_does_not_rewrite_legacy_flags(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    old = _term(client, headers).json()['data']['termId']
    current = _term(client, headers, no=2).json()['data']['termId']
    assert client.post(f'{BASE}/terms/{old}/publish', headers=headers).status_code == 200
    _govern(current)
    assert client.post(f'{BASE}/time-slots', headers=headers, json={'slotNo': 1}).status_code == 200
    response = client.post(f'{BASE}/terms/{current}/calendar/publish', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['data']['isCurrent'] is False
    assert client.get(f'{BASE}/terms/current', headers=headers).json()['data']['termId'] == current
    terms = client.get(f'{BASE}/terms', headers=headers).json()['data']['items']
    assert next(t for t in terms if t['termId'] == old)['isCurrent'] is True


def test_calendar_current_week_uses_school_local_day_and_swap_marks_both_weeks(client, db_mode, monkeypatch):
    from datetime import datetime, timezone
    from app.core import timeutil
    headers = _hdr(client, 'school_admin01')
    term_id = _term(client, headers).json()['data']['termId']
    path = f'{BASE}/terms/{term_id}'
    # Tuesday after midnight in Shanghai is still Monday in UTC: the second teaching week has begun.
    monkeypatch.setattr(timeutil, 'utc_now', lambda: datetime(2026, 9, 7, 17, tzinfo=timezone.utc))
    monkeypatch.setattr(timeutil, 'tenant_tz', lambda: __import__('zoneinfo').ZoneInfo('Asia/Shanghai'))
    weeks = client.get(path + '/weeks', headers=headers).json()['data']['items']
    assert [w['weekNo'] for w in weeks if w['isCurrent']] == [2]
    response = client.post(path + '/calendar', headers=headers, json={'eventType': 'SWAP', 'startDate': '2026-09-02', 'swapToDate': '2026-09-12'})
    assert response.status_code == 200, response.text
    weeks = client.get(path + '/week-calendar', headers=headers).json()['data']['weeks']
    assert [w['weekNo'] for w in weeks if w['swaps']] == [1, 2]
