"""Confirmed recognition -> proposed change -> real owner review -> four-client result."""
from sqlalchemy import select
from test_affairs_aid import BASE, TID, _seed, _open_batch, _apply, _review, _expire_publicity
from test_aid_mobile_queue import _login


def data(response):
    assert response.status_code == 200, response.text
    return response.json()['data']


def test_adjustment_assignment_versions_and_four_client_result(client, db_mode):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, User, UserRole, StudentAccountLink, UnifiedTodo, AidLevelHistory
    ids = _seed(db_mode)
    with get_sessionmaker()() as db:
        role = Role(tenant_id=TID, role_code='STUDENT', role_name='学生', role_type='SYSTEM', status='ACTIVE')
        db.add(role); db.flush()
        student = User(tenant_id=TID, login_name='aid_adjust_student', real_name='隔离学生', user_type='STUDENT',
            password_hash=hash_password('AidQueue-Test-2026!'), status='ACTIVE', must_change_password=False)
        db.add(student); db.flush()
        db.add(UserRole(tenant_id=TID, user_id=student.id, role_id=role.id, status='ACTIVE'))
        db.add(StudentAccountLink(tenant_id=TID, user_id=student.id, student_id=ids['sa'], link_status='ACTIVE', source='MANUAL'))
        db.commit()
    pc = _login(client, 'school_admin01', 'PC')
    phone = _login(client, 'school_admin01', 'TEACHER_MINI')
    counselor = _login(client, 'counselor01', 'TEACHER_MINI')
    students = [_login(client, 'aid_adjust_student', kind) for kind in ['PC', 'STUDENT_MINI']]
    batch = _open_batch(client, pc)
    row = data(_apply(client, pc, batch, ids['sa']))
    for _ in range(4): row = _review(client, pc, row)
    aid_id = row['applyId']
    base = f'{BASE}/aid/applications/{aid_id}'
    _expire_publicity(aid_id)
    row = data(client.post(f'{base}/publicity-confirm', headers=pc, json={'version':row['version']}))
    original = row['finalLevel']
    unchanged = client.post(f'{base}/adjust', headers=pc, json={'targetLevel':original, 'reason':'当前等级并没有变化', 'version':row['version']})
    assert unchanged.status_code == 400, unchanged.text
    for decision in ['REJECT', 'APPROVE']:
        row = data(client.post(f'{base}/adjust', headers=pc,
            json={'targetLevel':'SPECIAL', 'reason':'家庭发生重大变化需要重新核定', 'version':row['version']}))
        assert row['status'] == 'ADJUST_REVIEW' and row['finalLevel'] == original
        with get_sessionmaker()() as db:
            owner = db.scalar(select(User).where(User.tenant_id == TID, User.login_name == 'school_admin01'))
            todo = db.scalar(select(UnifiedTodo).where(UnifiedTodo.source_biz_id == int(aid_id), UnifiedTodo.todo_type == 'AID_ADJUST', UnifiedTodo.status == 'PENDING'))
            assert todo.assignee_id == owner.id
        queue = data(client.get('/api/v1/mobile/teacher/affairs/aid/pending?kind=AID_ADJUST', headers=phone))
        assert any(x['applyId'] == aid_id for x in queue['list'])
        detail = data(client.get(base, headers=pc))
        assert detail['adjustment']['targetLevel'] == 'SPECIAL'
        assert detail['adjustment']['reason'] == '家庭发生重大变化需要重新核定'
        library = data(client.get(f'{BASE}/aid/difficult-students', headers=pc))
        assert library['items'][0]['level'] == original and library['total'] == 1
        assert library['items'][0]['applyId'] == aid_id
        assert library['items'][0]['batchName'] and library['items'][0]['schoolYear']
        assert library['items'][0]['studentNo'] == 'A001'
        assert not ({'statement','annualIncome','debt','familyMembers'} & library['items'][0].keys())
        ledger = data(client.get(f'{BASE}/aid/applications', headers=pc))['items'][0]
        assert ledger['batchName'] == library['items'][0]['batchName'] and ledger['createdAt']
        stats = data(client.get(f'{BASE}/aid/stats', headers=pc))
        assert stats['approved'] == 1
        from test_affairs_four_end_hardening import _set_ctx, _clear_ctx
        from app.services.affairs_funding_service import _check_grant
        _set_ctx({'tenantId':str(TID), 'userId':'school_admin01', 'currentRoleCode':'SCHOOL_ADMIN', 'userType':'SCHOOL_ADMIN'})
        try:
            with get_sessionmaker()() as db:
                eligibility = _check_grant(db, ids['sa'])
                assert eligibility['inDifficultLibrary'] and eligibility['aidLevel'] == original
        finally:
            _clear_ctx()
        for student_headers in students:
            overview = data(client.get('/api/v1/mobile/affairs/aid/my', headers=student_headers))
            assert overview['currentLevel'] == original
            mine = data(client.get(f'/api/v1/mobile/affairs/aid/{aid_id}/detail', headers=student_headers))
            assert mine['adjustment']['fromLevel'] == original and mine['adjustment']['targetLevel'] == 'SPECIAL'
            assert 'reason' not in mine['adjustment'] and mine['allowedActions'] == []
        mobile_url = f'/api/v1/mobile/teacher/affairs/aid/{aid_id}/review'
        payload = {'action':decision, 'level':'SPECIAL', 'reason':'现有依据暂不足以支持本次调整', 'version':row['version']}
        assert client.post(mobile_url, headers=counselor, json=payload).status_code == 403
        assert client.post(mobile_url, headers=phone, json={**payload, 'version':row['version']-1}).status_code == 409
        assert client.post(mobile_url, headers=phone, json={**payload, 'level':'GENERAL'}).status_code == 409
        assert client.post(mobile_url, headers=phone, json={**payload, 'action':'UNKNOWN'}).status_code == 400
        response = (client.post(mobile_url, headers=phone, json=payload) if decision == 'APPROVE'
            else client.post(f'{base}/adjust-approve', headers=pc, json=payload))
        row = data(response)
        assert row['status'] == 'APPROVED'
        assert row['finalLevel'] == ('SPECIAL' if decision == 'APPROVE' else original)
        for student_headers in students:
            mine = data(client.get(f'/api/v1/mobile/affairs/aid/{aid_id}/detail', headers=student_headers))
            assert mine['adjustment'] is None and mine['finalLevel'] == row['finalLevel']
            assert mine['history'][-1]['title'] == ('等级调整通过' if decision == 'APPROVE' else '等级调整未通过')
            if decision == 'REJECT': assert mine['history'][-1]['description'] == payload['reason']
    with get_sessionmaker()() as db:
        history = db.scalars(select(AidLevelHistory).where(AidLevelHistory.apply_id == int(aid_id), AidLevelHistory.change_type == 'ADJUST')).all()
        assert len(history) == 1 and history[0].to_level == 'SPECIAL'
        assert all(x.status == 'DONE' for x in db.scalars(select(UnifiedTodo).where(UnifiedTodo.source_biz_id == int(aid_id), UnifiedTodo.todo_type == 'AID_ADJUST')))
