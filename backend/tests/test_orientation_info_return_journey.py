from test_orientation_o3_self_service import _seed_o3, _token
import pytest


@pytest.mark.parametrize('other_open_exception', [False, True])
def test_information_correction_waits_for_teacher_recheck(client, db_mode, auth_headers, other_open_exception):
    ids = _seed_o3(db_mode)
    student = _token(user_id=ids['userId'], student_id=ids['profileId'], student_no=ids['studentNo'], name=ids['name'])
    path = '/api/v1/orientation/students/'+str(ids['orientationId'])
    current = client.get(path, headers=auth_headers).json()['data']['student']
    response = client.post(path+'/verify', headers=auth_headers, json={
        'expectedVersion': current['version'], 'passed': False, 'reason': '请核对紧急联系人信息',
    })
    assert response.status_code == 200, response.text
    response = client.post('/api/v1/mobile/orientation/collect', headers=student, json={
        'phone':'13800138000', 'origin':'湖南长沙', 'emergencyContactName':'虚构联系人',
        'emergencyPhone':'13900139000', 'confirmed':True,
    })
    assert response.status_code == 200, response.text
    current = client.get(path, headers=auth_headers).json()['data']['student']
    assert current['steps']['INFO'] == 'DOING'
    mine = client.get('/api/v1/mobile/orientation/my', headers=student).json()['data']
    assert mine['checkinCredential']['canIssue'] is False
    if other_open_exception:
        from app.db.session import get_sessionmaker
        from app.models import OrientationException
        from test_orientation_o3_self_service import TID
        with get_sessionmaker()() as db:
            db.add(OrientationException(tenant_id=TID, ori_student_id=ids['orientationId'], exception_type='MATERIAL',
                                        status='OPEN', description='仍有其他材料异常', risk_level='MEDIUM'))
            db.commit()
    response = client.post(path+'/verify', headers=auth_headers, json={'expectedVersion':current['version'], 'passed':True})
    assert response.status_code == 200, response.text
    current = client.get(path, headers=auth_headers).json()['data']
    assert current['student']['steps']['INFO'] == 'DONE'
    assert current['student']['riskLevel'] == ('HIGH' if other_open_exception else 'LOW')
    identity_exceptions = [row for row in current['exceptions'] if row['exceptionType'] == 'IDENTITY']
    assert identity_exceptions and all(row['status'] == 'RESOLVED' for row in identity_exceptions)
