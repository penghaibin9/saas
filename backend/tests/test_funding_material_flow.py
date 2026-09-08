"""Funding original evidence and versioned supplements remain one scoped four-client flow."""
from test_funding_application_workspace import _accounts, _project_batch
from test_aid_mobile_queue import _login
from test_aid_material_flow import _data


def test_funding_material_return_resubmit_accept_and_application_scope(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import FundingApplication

    _accounts(db_mode)
    teacher_pc = _login(client, 'school_admin01', 'PC')
    teacher_mini = _login(client, 'school_admin01', 'TEACHER_MINI')
    student_pc = _login(client, 'fund_student', 'PC')
    student_mini = _login(client, 'fund_student', 'STUDENT_MINI')
    other = _login(client, 'fund_other', 'PC')
    _, batch = _project_batch(client, teacher_pc)

    def upload(headers, text, biz_type='MATERIAL_SUPPLEMENT'):
        return _data(client.post('/api/v1/files', headers=headers, data={'bizType': biz_type},
            files={'file': ('funding-proof.txt', text.encode(), 'text/plain')}))['fileId']

    original = upload(student_pc, 'original award evidence', 'FUNDING')
    app = _data(client.post('/api/v1/portal/affairs/funding/apply', headers=student_pc,
        json={'batchId': batch['batchId'], 'statement': '依据本校开放项目提交奖助申请', 'confirm': True, 'fileIds': [original]}))
    other_app = _data(client.post('/api/v1/portal/affairs/funding/apply', headers=other,
        json={'batchId': batch['batchId'], 'statement': '另一学生提交自己的奖助申请', 'confirm': True}))
    context = {'bizType': 'FUNDING', 'bizId': app['applicationId']}
    requirement = _data(client.post('/api/v1/student-affairs/material-requirements', headers=teacher_pc,
        json={**context, 'itemCode': 'AWARD_PROOF', 'itemName': '获奖证明补充件', 'requirementReason': '请补充证书完整页及获奖时间'}))
    _data(client.post('/api/v1/student-affairs/material-requirements', headers=teacher_pc,
        json={'bizType': 'FUNDING', 'bizId': other_app['applicationId'], 'itemCode': 'OTHER_PROOF', 'itemName': '另一申请专属材料'}))
    rid = requirement['requirementId']
    submit_url = '/api/v1/mobile/affairs/material-requirements/'+rid+'/submissions'
    review_url = '/api/v1/student-affairs/material-requirements/'+rid+'/review'

    def inspect(status, note=None):
        for path, headers in [('/api/v1/student-affairs/material-requirements', teacher_pc),
                              ('/api/v1/student-affairs/material-requirements', teacher_mini),
                              ('/api/v1/mobile/affairs/material-requirements', student_pc),
                              ('/api/v1/mobile/affairs/material-requirements', student_mini)]:
            data = _data(client.get(path, headers=headers, params={**context, 'page': 1, 'pageSize': 10}))
            assert data['total'] == 1
            row = data['items'][0]
            assert row['requirementId'] == rid and row['bizId'] == app['applicationId']
            assert row['status'] == status
            if note:
                assert row['currentSubmission']['reviewNote'] == note
            files = _data(client.get('/api/v1/files', headers=headers, params=context))['items']
            assert [f['fileId'] for f in files] == [original]
        assert _data(client.get('/api/v1/mobile/affairs/material-requirements', headers=other, params=context))['total'] == 0

    inspect('MISSING')
    first_file = upload(student_pc, 'first supplement lacks date')
    first = _data(client.post(submit_url, headers=student_pc,
        json={'fileId': first_file, 'version': requirement['version'], 'note': '第一版补交证明'}))
    inspect('PENDING_REVIEW')
    assert client.post(submit_url, headers=student_mini,
        json={'fileId': first_file, 'version': requirement['version']}).status_code == 409
    note = '请补全证书日期和盖章页再提交'
    returned = _data(client.post(review_url, headers=teacher_mini,
        json={'action': 'RETURN', 'reason': note, 'version': first['version']}))
    inspect('RETURNED', note)
    second_file = upload(student_mini, 'second supplement includes date and stamp')
    second = _data(client.post(submit_url, headers=student_mini,
        json={'fileId': second_file, 'version': returned['version'], 'note': '已补全日期和盖章'}))
    assert client.post(review_url, headers=teacher_pc,
        json={'action': 'ACCEPT', 'version': returned['version']}).status_code == 409
    accepted = _data(client.post(review_url, headers=teacher_pc,
        json={'action': 'ACCEPT', 'version': second['version']}))
    inspect('ACCEPTED', '材料验收通过')
    assert len(accepted['versions']) == 2 and accepted['currentSubmission']['fileId'] == second_file
    assert any(v['reviewNote'] == note for v in accepted['versions'])
    assert client.get('/api/v1/files/download/'+second_file, headers=other).status_code in {403, 404}
    assert b'second supplement' in client.get('/api/v1/files/download/'+second_file, headers=student_pc).content
    with get_sessionmaker()() as db:
        assert db.get(FundingApplication, int(app['applicationId'])).status == app['status']
