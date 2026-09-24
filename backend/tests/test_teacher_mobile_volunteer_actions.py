"""Mobile school processing delegates to the canonical versioned placement authority."""
import pytest

from app.db.session import get_sessionmaker
from app.models import InternshipRecord, InternshipPosition
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from tests.test_internship_school_volunteer_actions import ready, body
from tests.test_internship_catalog_preparation import _linked_student_headers

BASE = '/api/v1/mobile/teacher/internship/context'


@pytest.mark.parametrize('action', ['confirm', 'return'])
def test_mobile_volunteer_action_versions_batch_and_result(client, auth_headers, db_mode, action):
    ids = ready()
    params = {'batchId': ids['batch'], 'campaignId': ids['campaign']}
    url = f"{BASE}/volunteer-groups/{ids['0']}/{action}"
    payload = body(ids) if action == 'confirm' else {
        'reason': '请补充本人实训项目内容', 'expectedGroupVersion': 0, 'expectedRecordVersion': 0}
    campaigns = client.get(BASE+'/volunteer-campaigns', headers=auth_headers, params={'batchId': ids['batch']})
    assert campaigns.status_code == 200, campaigns.json()
    assert [item['id'] for item in campaigns.json()['data']['items']] == [str(ids['campaign'])]
    missing = client.post(url, headers=auth_headers, params=params, json={})
    assert missing.status_code == 400, missing.json()
    stale = client.post(url, headers=auth_headers, params=params, json={**payload, 'expectedGroupVersion': 99})
    assert stale.status_code == 409, stale.json()
    foreign = client.post(url, headers=auth_headers, params={**params, 'batchId': ids['batch']+99999}, json=payload)
    assert foreign.status_code == 404, foreign.json()
    with get_sessionmaker()() as db:
        assert db.get(InternshipVolunteerGroup, ids['0']).status == 'LOCKED'
        assert db.get(InternshipPosition, ids['position']).allocated_count == 0
    response = client.post(url, headers=auth_headers, params=params, json=payload)
    assert response.status_code == 200, response.json()
    expected = 'APPROVED' if action == 'confirm' else 'NEEDS_REVISION'
    assert response.json()['data']['status'] == expected
    read = client.get(f"{BASE}/volunteer-groups/{ids['0']}", headers=auth_headers, params=params)
    assert read.status_code == 200 and read.json()['data']['status'] == expected
    with get_sessionmaker()() as db:
        assert bool(db.get(InternshipRecord, ids['record']).current_placement_snapshot_id) == (action == 'confirm')
        assert db.get(InternshipPosition, ids['position']).allocated_count == (1 if action == 'confirm' else 0)
    replay = client.post(url, headers=auth_headers, params=params, json=payload)
    assert replay.status_code == 409, replay.json()


def test_student_cannot_use_teacher_mobile_volunteer_writes(client, auth_headers, db_mode):
    ids = ready()
    with get_sessionmaker()() as db:
        student_id = db.get(InternshipRecord, ids['record']).student_id
    student_headers = _linked_student_headers(student_id, 'MOBILE-ACTION-DENIED')
    for action in ['confirm', 'return']:
        response = client.post(f"{BASE}/volunteer-groups/{ids['0']}/{action}",
            headers=student_headers, params={'batchId': ids['batch'], 'campaignId': ids['campaign']},
            json={**body(ids), 'reason': '不能越权审批本人志愿'})
        assert response.status_code == 403, response.json()
    with get_sessionmaker()() as db:
        assert db.get(InternshipVolunteerGroup, ids['0']).status == 'LOCKED'
