"""Real uploads and command transitions, rather than pre-seeded material statuses."""
from sqlalchemy import select

from test_affairs_aid import TID, _seed, _open_batch, _apply
from test_aid_mobile_queue import _login


def _data(response):
    assert response.status_code == 200, response.text
    return response.json()['data']


def test_aid_upload_return_resubmit_accept_across_four_clients(client, db_mode):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, User, UserRole, StudentAccountLink, AidApply, UnifiedTodo, UnifiedMessage
    from app.models.affairs_operations import AffairsMaterialSubmission
    from app.models.file import FileVersion
    ids = _seed(db_mode)
    with get_sessionmaker()() as db:
        role = Role(tenant_id=TID, role_code='STUDENT', role_name='学生', role_type='SYSTEM', status='ACTIVE')
        db.add(role); db.flush()
        for name, student_id in [('aid_material_student', ids['sa']), ('aid_material_other', ids['sb'])]:
            user = User(tenant_id=TID, login_name=name, real_name=name, user_type='STUDENT',
                password_hash=hash_password('AidQueue-Test-2026!'), status='ACTIVE', must_change_password=False)
            db.add(user); db.flush()
            db.add(UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status='ACTIVE'))
            db.add(StudentAccountLink(tenant_id=TID, user_id=user.id, student_id=student_id, link_status='ACTIVE', source='MANUAL'))
        db.commit()
    teacher_pc = _login(client, 'school_admin01', 'PC')
    teacher_mini = _login(client, 'school_admin01', 'TEACHER_MINI')
    student_pc = _login(client, 'aid_material_student', 'PC')
    student_mini = _login(client, 'aid_material_student', 'STUDENT_MINI')
    other = _login(client, 'aid_material_other', 'PC')
    batch = _open_batch(client, teacher_pc)
    aid = _data(_apply(client, teacher_pc, batch, ids['sa']))
    context = {'bizType': 'AID', 'bizId': aid['applyId']}
    req = _data(client.post('/api/v1/student-affairs/material-requirements', headers=teacher_pc,
        json={**context, 'itemCode':'FAMILY_STATEMENT', 'itemName':'家庭情况补充说明', 'requirementReason':'请补充家庭收入变化说明'}))
    rid = req['requirementId']
    submit_url = f'/api/v1/mobile/affairs/material-requirements/{rid}/submissions'
    review_url = f'/api/v1/student-affairs/material-requirements/{rid}/review'

    def upload(header, text, biz_type):
        return _data(client.post('/api/v1/files', headers=header, data={'bizType':biz_type},
            files={'file':('family-statement.txt', text.encode('utf-8'), 'text/plain')}))['fileId']

    def workbench_metrics():
        data = _data(client.get('/api/v1/mobile/performance/teacher/workbench?pageSize=8', headers=teacher_mini))
        return {m['key']: m['value'] for m in data['metrics']}

    initial_metrics = workbench_metrics()

    foreign_file = upload(other, '另一学生的隔离验收文件', 'ATTACHMENT')
    denied = client.post(submit_url, headers=student_pc, json={'fileId':foreign_file, 'version':req['version']})
    assert denied.status_code == 403, denied.text
    file1 = upload(student_pc, '第一版家庭情况说明，仅用于隔离验收。', 'ATTACHMENT')
    assert client.get(f'/api/v1/files/{file1}', headers=other).status_code in {403,404}
    from app.models import FileObject
    with get_sessionmaker()() as db:
        obj = db.get(FileObject, int(file1)); original_scan = obj.scan_status
        obj.scan_status = 'PENDING'; db.commit()
    metadata = _data(client.get(f'/api/v1/files/{file1}', headers=student_pc))
    assert metadata['readyForBusiness'] is False and metadata['scanStatus'] == 'PENDING'
    blocked = client.post(submit_url, headers=student_pc, json={'fileId':file1,'version':req['version']})
    assert blocked.status_code == 409, blocked.text
    with get_sessionmaker()() as db:
        db.get(FileObject, int(file1)).scan_status = original_scan; db.commit()
    assert _data(client.get(f'/api/v1/files/{file1}', headers=student_pc))['readyForBusiness'] is True
    first = _data(client.post(submit_url, headers=student_pc,
        json={'fileId':file1, 'version':req['version'], 'note':'第一版说明'}))
    assert first['status'] == 'PENDING_REVIEW'
    pending_metrics = workbench_metrics()
    assert pending_metrics['pending'] == initial_metrics['pending'] + 1
    assert pending_metrics['near'] == initial_metrics['near']  # no material deadline
    duplicate = client.post(submit_url, headers=student_mini, json={'fileId':file1, 'version':req['version']})
    assert duplicate.status_code == 409, duplicate.text
    stale = client.post(review_url, headers=teacher_pc, json={'action':'RETURN', 'reason':'请补充具体收入变化', 'version':req['version']})
    assert stale.status_code == 409, stale.text
    returned = _data(client.post(review_url, headers=teacher_pc,
        json={'action':'RETURN', 'reason':'请补充具体收入变化', 'version':first['version']}))
    assert returned['status'] == 'RETURNED'
    mine = _data(client.get('/api/v1/mobile/affairs/material-requirements', headers=student_mini, params=context))['items'][0]
    assert mine['currentSubmission']['reviewNote'] == '请补充具体收入变化'
    assert 'SUBMIT_MATERIAL' in mine['allowedActions']
    file2 = upload(student_mini, '第二版：已补充收入减少的原因，仅用于隔离验收。', 'MATERIAL_SUPPLEMENT')
    second = _data(client.post(submit_url, headers=student_mini,
        json={'fileId':file2, 'version':mine['version'], 'note':'已按老师要求补全'}))
    assert len(second['versions']) == 2
    accepted = _data(client.post(review_url, headers=teacher_mini,
        json={'action':'ACCEPT', 'version':second['version']}))
    assert accepted['status'] == 'ACCEPTED'
    assert workbench_metrics()['pending'] == initial_metrics['pending']
    final = _data(client.get('/api/v1/mobile/affairs/material-requirements', headers=student_pc, params=context))['items'][0]
    assert final['status'] == 'ACCEPTED' and final['allowedActions'] == []
    assert final['currentSubmission']['fileId'] == str(file2)
    assert len(final['versions']) == 2
    assert any(v['reviewNote'] == '请补充具体收入变化' for v in final['versions'])
    assert _data(client.get('/api/v1/mobile/affairs/material-requirements', headers=other, params=context))['total'] == 0
    assert client.get(f'/api/v1/files/download/{file2}', headers=other).status_code in {403,404}
    download = client.get(f'/api/v1/files/download/{file2}', headers=student_pc)
    assert download.status_code == 200, download.text
    assert '已补充收入减少' in download.content.decode('utf-8')
    with get_sessionmaker()() as db:
        versions = db.scalars(select(AffairsMaterialSubmission).where(AffairsMaterialSubmission.requirement_id == int(rid))).all()
        assert len(versions) == 2 and len({v.file_version_id for v in versions}) == 2
        assert db.get(FileVersion, int(final['currentSubmission']['fileVersionId'])).status == 'APPROVED'
        assert db.get(AidApply, int(aid['applyId'])).status == aid['status']
        todos = db.scalars(select(UnifiedTodo).where(UnifiedTodo.tenant_id == TID,
            UnifiedTodo.source_biz_type == 'MATERIAL_REQUIREMENT', UnifiedTodo.source_biz_id == int(rid))).all()
        assert todos and all(todo.status == 'DONE' for todo in todos)
        messages = db.scalars(select(UnifiedMessage).where(UnifiedMessage.tenant_id == TID,
            UnifiedMessage.action_key == 'student.affairs.material')).all()
        assert messages and all(str(m.action_params_json.get('materialRequirementId')) == str(rid) for m in messages)
