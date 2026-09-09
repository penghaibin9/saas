"""Time-slot and dated time-band commands through real HTTP/MySQL, including downstream reads."""
from test_aa_term import BASE, TID, _hdr


def _slot(client, headers, number=1, **fields):
    response = client.post(f'{BASE}/time-slots', headers=headers, json={'slotNo': number, **fields})
    assert response.status_code == 200, response.text
    return response.json()['data']['slotId']


def test_slot_time_validation_and_explicit_clear(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    for change in ({'slotNo': True}, {'startTime': '8:00', 'endTime': '08:45'},
                   {'startTime': '25:00', 'endTime': '26:00'}, {'startTime': '08:00'}):
        response = client.post(f'{BASE}/time-slots', headers=headers, json={'slotNo': 1, **change})
        assert response.status_code in (400, 422), response.text
    slot_id = _slot(client, headers, startTime='08:00', endTime='08:45', slotName='早间第一节')
    response = client.put(f'{BASE}/time-slots/{slot_id}', headers=headers, json={'startTime': None, 'endTime': None, 'slotName': ''})
    assert response.status_code == 200, response.text
    assert response.json()['data']['startTime'] == response.json()['data']['endTime'] == ''
    assert response.json()['data']['slotName'] == ''


def test_time_band_dates_and_same_campus_overlap(client, db_mode):
    headers = _hdr(client, 'school_admin01')
    slot_id = _slot(client, headers)
    path = f'{BASE}/time-slots/{slot_id}/time-bands'
    body = {'bandName': '夏季作息', 'campusCode': 'MAIN', 'startTime': '08:10', 'endTime': '08:55', 'effectiveStart': '2026-05-01', 'effectiveEnd': '2026-09-30'}
    for change in ({'effectiveStart': 'invalid'}, {'effectiveEnd': '2026-04-30'}):
        response = client.post(path, headers=headers, json={**body, **change})
        assert response.status_code in (400, 422), response.text
    first = client.post(path, headers=headers, json=body)
    assert first.status_code == 200, first.text
    band_id = first.json()['data']['bandId']
    assert client.post(path, headers=headers, json={**body, 'effectiveStart': '2026-09-30'}).status_code == 409
    # Different campuses remain legitimate simultaneous alternatives; next-day ranges do not overlap.
    assert client.post(path, headers=headers, json={**body, 'campusCode': 'EAST'}).status_code == 200
    assert client.post(path, headers=headers, json={**body, 'effectiveStart': '2026-10-01', 'effectiveEnd': '2026-12-31'}).status_code == 200
    assert client.put(f'{BASE}/time-bands/{band_id}', headers=headers, json={'effectiveEnd': '2026-10-01'}).status_code == 409
    assert client.put(f'{BASE}/time-bands/{band_id}', headers=headers, json={'status': 'DISABLED'}).status_code == 200
    assert client.put(f'{BASE}/time-bands/{band_id}', headers=headers, json={'effectiveEnd': '2026-10-01'}).status_code == 200
    assert client.put(f'{BASE}/time-bands/{band_id}', headers=headers, json={'status': 'ENABLED'}).status_code == 409


def test_time_band_clear_and_downstream_fallback(client, db_mode):
    from datetime import date
    from app.db.session import get_sessionmaker
    from app.models import AaTimeSlot, AaClassTimeBand
    from app.modules.academic_affairs.services.mobile_academic_affairs_facade import resolve_schedule_time_bands
    headers = _hdr(client, 'school_admin01')
    slot_id = _slot(client, headers, startTime='08:00', endTime='08:45')
    response = client.post(f'{BASE}/time-slots/{slot_id}/time-bands', headers=headers, json={'bandName': '夏季', 'campusCode': 'MAIN', 'effectiveStart': '2026-05-01', 'effectiveEnd': '2026-09-30', 'startTime': '08:10', 'endTime': '08:55'})
    assert response.status_code == 200, response.text
    band_id = response.json()['data']['bandId']
    with get_sessionmaker()() as db:
        slots, bands = [db.get(AaTimeSlot, int(slot_id))], [db.get(AaClassTimeBand, int(band_id))]
        assert resolve_schedule_time_bands(slots, bands, date(2026, 7, 1))[0]['startTime'] == '08:10'
        assert resolve_schedule_time_bands(slots, bands, date(2026, 12, 1))[0]['source'] == 'TIME_SLOT'
    updated = client.put(f'{BASE}/time-bands/{band_id}', headers=headers, json={'effectiveStart': None, 'effectiveEnd': None, 'bandName': '', 'campusCode': ''})
    assert updated.status_code == 200, updated.text
    assert updated.json()['data']['effectiveStart'] is None and updated.json()['data']['effectiveEnd'] is None
    assert updated.json()['data']['bandName'] == updated.json()['data']['campusCode'] == ''


def test_used_slot_cannot_be_deleted_or_renumbered_and_deleted_parent_rejects_band_writes(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem
    headers = _hdr(client, 'school_admin01')
    slot_id = _slot(client, headers)
    with get_sessionmaker()() as db:
        db.add(AaScheduleItem(tenant_id=TID, batch_id=999, weekday=1, slot_no=1, course_name='节次引用验收'))
        db.commit()
    assert client.put(f'{BASE}/time-slots/{slot_id}', headers=headers, json={'slotNo': 3}).status_code == 409
    assert client.delete(f'{BASE}/time-slots/{slot_id}', headers=headers).status_code == 409
    assert client.put(f'{BASE}/time-slots/{slot_id}', headers=headers, json={'enabled': False}).status_code == 409
    assert client.put(f'{BASE}/time-slots/{slot_id}', headers=headers, json={'slotName': '第一节更名'}).status_code == 200
    unused = _slot(client, headers, 2)
    band = client.post(f'{BASE}/time-slots/{unused}/time-bands', headers=headers, json={'startTime': '09:00', 'endTime': '09:45'}).json()['data']
    assert client.delete(f'{BASE}/time-slots/{unused}', headers=headers).status_code == 200
    assert client.put(f"{BASE}/time-bands/{band['bandId']}", headers=headers, json={'status': 'ENABLED'}).status_code == 404


def test_parallel_creates_cannot_duplicate_slot_number_or_overlap_clock_time(db_mode, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.routers.academic_affairs import TimeSlotCreate
    from app.modules.academic_affairs.services import academic_affairs_service as facade
    monkeypatch.setattr(facade._legacy, '_tid', lambda: TID)
    def create(number):
        try:
            facade.create_time_slot(TimeSlotCreate(slotNo=number, startTime='08:00', endTime='08:45'), {})
            return 'ok'
        except AppException as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(create, [1, 2]))
    assert sorted(outcomes) == ['DATA_CONFLICT', 'ok'], outcomes
