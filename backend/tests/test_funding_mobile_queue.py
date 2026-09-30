"""Real SQL queue: current workflow ownership and scope precede search/count/paging."""
from sqlalchemy import select

from test_affairs_funding import TID, BASE, _seed, _fund_apply
from test_funding_application_workspace import _project_batch
from test_aid_mobile_queue import _login
from test_aid_material_flow import _data

MOBILE = '/api/v1/mobile/teacher/affairs/funding'


def test_funding_queue_reaches_old_tasks_and_excludes_transferred_or_invalid_work(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import FundingApplication, StudentProfile, User, WorkflowInstance, WorkflowTask

    ids = _seed(db_mode)
    admin = _login(client, 'school_admin01', 'PC')
    counselor = _login(client, 'counselor01', 'TEACHER_MINI')
    _, batch = _project_batch(client, admin)
    real = _data(_fund_apply(client, admin, batch['batchId'], ids['sa']))
    expected = {real['applicationId']}
    with get_sessionmaker()() as db:
        owner = db.scalar(select(User.id).where(User.tenant_id == TID, User.login_name == 'counselor01'))
        other = db.scalar(select(User.id).where(User.tenant_id == TID, User.login_name == 'school_admin01'))
        original = db.get(FundingApplication, int(real['applicationId']))
        workflow_code = db.get(WorkflowInstance, original.workflow_instance_id).workflow_code
        college_id = db.get(StudentProfile, ids['sa']).college_id
        for i in range(130):
            student = StudentProfile(tenant_id=TID, student_no=f'FQUEUE{i:03}',
                real_name='含%字符' if i == 0 else f'奖助队列{i:03}', college_id=college_id,
                class_id=ids['B'] if i == 123 else ids['A'], current_stage='ORIENTATION',
                student_status='NORMAL', status='ACTIVE', is_deleted=i == 127)
            db.add(student); db.flush()
            status = 'RETURNED' if i == 121 else 'COLLEGE_REVIEW' if i == 124 else 'COUNSELOR_REVIEW'
            row = FundingApplication(tenant_id=TID, batch_id=int(batch['batchId']), student_id=student.id,
                project_type='SCHOLARSHIP', apply_source='SELF', status=status,
                amount=3000, requested_amount=3000, statement='仅详情展示的家庭说明', is_deleted=i == 128)
            db.add(row); db.flush()
            if i < 121:
                expected.add(str(row.id))
            if i == 125:
                continue
            instance = WorkflowInstance(tenant_id=TID, workflow_code=workflow_code,
                source_module='student-affairs', source_biz_type='FUNDING', source_biz_id=row.id,
                applicant_id=student.id, title='隔离队列测试', status='RUNNING', current_node=status)
            db.add(instance); db.flush(); row.workflow_instance_id = instance.id
            db.add(WorkflowTask(tenant_id=TID, instance_id=instance.id, node_code=status,
                assignee_id=other if i == 122 else owner, status='PENDING', is_deleted=i == 126))
            if i == 129:
                db.flush()
                db.add(WorkflowTask(tenant_id=TID, instance_id=instance.id, node_code=status,
                    assignee_id=other, status='PENDING'))  # Latest task overrides the older owner.
        db.commit()
    seen = []
    for page in range(1, 8):
        data = _data(client.get(MOBILE+'/pending', headers=counselor, params={'page':page, 'pageSize':20}))
        assert data['total'] == 122 and len(data['list']) == (2 if page == 7 else 20)
        for item in data['list']:
            seen.append(item['applicationId'])
            assert item['allowedActions'] == ['APPROVE', 'RETURN', 'REJECT']
            assert 'statement' not in item
    assert len(seen) == len(set(seen)) == 122 and set(seen) == expected
    found = _data(client.get(MOBILE+'/pending', headers=counselor, params={'keyword':'%'}))
    assert found['total'] == 1 and found['list'][0]['realName'] == '含%字符'
    assert _data(client.get(MOBILE+'/pending', headers=admin))['total'] == 0
    for params in ({'page':0}, {'pageSize':101}, {'keyword':'字'*101}):
        assert client.get(MOBILE+'/pending', headers=counselor, params=params).status_code == 400
    detail = _data(client.get(MOBILE+'/'+real['applicationId'], headers=counselor))
    assert detail['allowedActions'] == ['APPROVE', 'RETURN', 'REJECT']
    result = _data(client.post(MOBILE+'/'+real['applicationId']+'/review', headers=counselor,
        json={'action':'RETURN', 'reason':'请补充完整申请说明', 'version':detail['version']}))
    assert result['status'] == 'RETURNED'
    assert _data(client.get(MOBILE+'/pending', headers=counselor))['total'] == 121
    result = _data(client.get(MOBILE+'/'+real['applicationId'], headers=counselor))
    assert result['status'] == 'RETURNED' and result['allowedActions'] == []
    assert _data(client.get(BASE+'/funding/applications/'+real['applicationId'], headers=admin))['allowedActions'] == []
