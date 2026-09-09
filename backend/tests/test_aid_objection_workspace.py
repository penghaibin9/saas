"""异议手机真分页、单据直达和学生结果可见性。"""
from sqlalchemy import select
from test_affairs_aid import TID, _seed
from test_aid_mobile_queue import _login
from test_affairs_four_end_hardening import _set_ctx, _clear_ctx

MOBILE = '/api/v1/mobile/teacher/affairs/appeals/AID_OBJECTION'


def test_objection_queue_and_exact_detail_with_versioned_review(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AidApply, AidBatch, AidObjection, UnifiedTodo, User
    from app.api.v1.affairs_student_returned import aid_detail
    ids = _seed(db_mode)
    header = _login(client, 'college_admin01', 'TEACHER_MINI')
    expected = []
    with get_sessionmaker()() as db:
        owner = db.scalar(select(User.id).where(User.login_name == 'college_admin01', User.tenant_id == TID))
        other = db.scalar(select(User.id).where(User.login_name == 'school_admin01', User.tenant_id == TID))
        for i in range(53):
            batch = AidBatch(tenant_id=TID, batch_name=f'历史认定{i}', year_code=f'TEST-{i}', status='PUBLICITY')
            db.add(batch); db.flush()
            application = AidApply(tenant_id=TID, batch_id=batch.id, student_id=ids['sa'], status='PUBLICITY', apply_level='GENERAL')
            db.add(application); db.flush()
            row = AidObjection(tenant_id=TID, apply_id=application.id, student_id=ids['sa'], status='SUBMITTED',
                reason='匿名异议理由不能向被异议学生泄露', objector_name='匿名核验', open_key=application.id)
            db.add(row); db.flush()
            db.add(UnifiedTodo(tenant_id=TID, source_module='student-affairs', source_biz_type='AID_OBJECTION',
                source_biz_id=row.id, student_id=ids['sa'], todo_type='AID_OBJECTION_REVIEW',
                assignee_id=owner if i < 51 else other, title='测试异议', status='PENDING'))
            if i < 51: expected.append(str(row.id))
            if i == 0: application_id, target = application.id, str(row.id)
            if i == 52: denied_id = str(row.id)
        db.commit()
    seen = []
    for page in range(1, 4):
        response = client.get(MOBILE, headers=header, params={'page': page, 'pageSize': 20})
        assert response.status_code == 200, response.text
        data = response.json()['data']
        assert data['total'] == 51
        seen.extend(row['objectionId'] for row in data['items'])
        assert all(row['allowedActions'] == ['REVIEW'] for row in data['items'])
    assert set(seen) == set(expected) and len(seen) == 51
    current = client.get(f'{MOBILE}/{target}/detail', headers=header).json()['data']
    assert current['objectionId'] == target
    denied = client.get(f'{MOBILE}/{denied_id}/detail', headers=header).json()['data']
    assert denied['allowedActions'] == []
    assert client.post(f'{MOBILE}/{denied_id}/review', headers=header,
        json={'version': denied['version'], 'result': 'OVERRULED', 'opinion': '不得处理其他责任人待办'}).status_code == 403
    response = client.post(f'{MOBILE}/{target}/review', headers=header,
        json={'version': current['version'], 'result': 'OVERRULED', 'opinion': '已核实申报信息，维持原认定结果'})
    assert response.status_code == 200, response.text
    terminal = client.get(f'{MOBILE}/{target}/detail', headers=header).json()['data']
    assert terminal['status'] == 'CLOSED' and terminal['allowedActions'] == []
    repeated = client.post(f'{MOBILE}/{target}/review', headers=header,
        json={'version': current['version'], 'result': 'SUSTAINED', 'opinion': '重复请求不得改变原结论'})
    assert repeated.status_code != 200
    student = {'userId': 'u-A001', 'studentNo': 'A001', 'realName': '甲一', 'userType': 'STUDENT', 'currentRoleCode': 'STUDENT', 'tenantId': str(TID)}
    _set_ctx(student)
    try:
        detail = aid_detail(application_id, student)['data']
        outcome = detail['objectionResults'][0]
        assert detail['status'] == 'PUBLICITY' and detail['hasPendingObjection'] is False
        assert outcome['status'] == 'CLOSED' and outcome['reviewOpinion'] == '已核实申报信息，维持原认定结果'
        assert outcome['reviewedAt'] and outcome['resultLabel']
        assert not ({'reason', 'objectorName', 'reviewer'} & outcome.keys())
    finally: _clear_ctx()
