"""Student sees review feedback and can submit a correction on the same welcome record."""
from test_orientation_o3_self_service import _seed_o3, _token
import pytest


@pytest.mark.parametrize('include_payment', [False, True])
def test_returned_green_channel_roundtrip(client, db_mode, auth_headers, include_payment):
    ids = _seed_o3(db_mode, include_payment=include_payment)
    student = _token(user_id=ids['userId'], student_id=ids['profileId'], student_no=ids['studentNo'], name=ids['name'])
    endpoint = '/api/v1/mobile/orientation/green-channel'
    first = client.post(endpoint, headers=student, json={
        'applyType': '缓缴学费', 'applyAmount': 100, 'remark': '迎新联调虚构申请', 'clientRequestId': 'green-journey-first',
    })
    assert first.status_code == 200, first.text
    application = first.json()['data']
    returned = client.post('/api/v1/orientation/green-channels/'+application['id']+'/return', headers=auth_headers,
                           json={'expectedVersion': application['version'], 'reason': '请补充预计缴费日期'})
    assert returned.status_code == 200, returned.text
    snapshot = client.get('/api/v1/mobile/orientation/my', headers=student).json()['data']
    assert snapshot['greenChannelStatus'] == 'RETURNED'
    assert snapshot['greenChannel']['rejectReason'] == '请补充预计缴费日期'
    assert snapshot['greenChannel']['applyAmount'] == 100
    corrected = {'applyType': '缓缴学费', 'applyAmount': 100, 'remark': '预计本月月底缴费，虚构验收数据', 'clientRequestId': 'green-journey-corrected'}
    submitted = client.post(endpoint, headers=student, json=corrected)
    assert submitted.status_code == 200, submitted.text
    current = submitted.json()['data']
    assert current['studentId'] == str(ids['orientationId'])
    assert client.post(endpoint, headers=student, json=corrected).json()['data']['id'] == current['id']
    for action in ('approve', 'return', 'reject'):
        stale = client.post('/api/v1/orientation/green-channels/'+application['id']+'/'+action, headers=auth_headers,
                            json={'expectedVersion': returned.json()['data']['version'], 'reason': '旧单不能再次审核', 'remark': '旧单不能再次审核'})
        assert stale.status_code == 409, stale.text
    snapshot = client.get('/api/v1/mobile/orientation/my', headers=student).json()['data']
    assert snapshot['greenChannelStatus'] == 'SUBMITTED'
    assert snapshot['greenChannel']['id'] == current['id']
    approved = client.post('/api/v1/orientation/green-channels/'+current['id']+'/approve', headers=auth_headers,
                           json={'expectedVersion': current['version'], 'remark': '虚构联调审核通过'})
    assert approved.status_code == 200, approved.text
    snapshot = client.get('/api/v1/mobile/orientation/my', headers=student).json()['data']
    assert snapshot['greenChannel']['status'] == 'APPROVED'
    assert snapshot['greenChannel']['remark'] == corrected['remark']
    assert snapshot['greenChannelStatus'] == 'APPROVED'
    from app.services.orientation_flow_service import student_step_projection
    other = _token(user_id=ids['otherUserId'], student_id=ids['otherProfileId'], student_no=ids['otherNo'], name=ids['otherName'])
    assert client.get('/api/v1/mobile/orientation/my', headers=other).json()['data'].get('greenChannel') is None
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudent
    with get_sessionmaker()() as db:
        steps = student_step_projection(db, db.get(OrientationStudent, ids['orientationId']))
        assert steps.get('PAYMENT') == ('DONE' if include_payment else None)
        db.get(OrientationStudent, ids['orientationId']).stage = 'ENROLLED'
        db.commit()
    response = client.post(endpoint, headers=student, json={**corrected, 'clientRequestId':'green-after-completion'})
    assert response.status_code >= 400, response.text
