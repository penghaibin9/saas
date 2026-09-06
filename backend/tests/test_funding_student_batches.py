"""Both real student entry points paginate eligible batches before projection."""
from datetime import datetime, timedelta

from test_affairs_funding import BASE, TID, _seed, _hdr


def test_student_batch_search_scope_and_new_application_window(client, db_mode):
    from sqlalchemy import func, select
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import FundingBatch, FundingProject, FundingApplication, Role, User, UserRole, StudentAccountLink
    from test_aid_mobile_queue import _login
    ids = _seed(db_mode)
    now = datetime.utcnow()
    invalid = []
    with get_sessionmaker()() as db:
        role = Role(tenant_id=TID, role_code='STUDENT', role_name='学生', role_type='SYSTEM', status='ACTIVE')
        db.add(role); db.flush()
        student = User(tenant_id=TID, login_name='fund_batch_student', real_name='批次验收学生', user_type='STUDENT',
            password_hash=hash_password('AidQueue-Test-2026!'), status='ACTIVE', must_change_password=False)
        db.add(student); db.flush()
        db.add(UserRole(tenant_id=TID, user_id=student.id, role_id=role.id, status='ACTIVE'))
        db.add(StudentAccountLink(tenant_id=TID, user_id=student.id, student_id=ids['sa'], link_status='ACTIVE', source='MANUAL'))
        project = FundingProject(tenant_id=TID, project_name='历史专项100%奖学金', project_type='SCHOLARSHIP', amount=3000, status='ENABLED')
        grant = FundingProject(tenant_id=TID, project_name='当前助学金', project_type='GRANT', amount=2000, status='ENABLED')
        db.add_all([project, grant]); db.flush()
        target = FundingBatch(tenant_id=TID, project_id=project.id, project_type='SCHOLARSHIP', year_code='2021-2022', status='OPEN')
        db.add(target); db.flush(); target_id = str(target.id)
        for i in range(209):
            db.add(FundingBatch(tenant_id=TID, project_id=grant.id, project_type='GRANT', year_code='2026-2027', status='OPEN'))
        for fields in [{'status':'DRAFT'}, {'status':'CLOSED'}, {'apply_start':now+timedelta(days=1)},
                       {'apply_end':now-timedelta(days=1)}, {'tenant_id':TID+99}, {'is_deleted':True},
                       {'project_type':'WORK_STUDY'}, {'project_type':'GRANT'}]:
            batch = FundingBatch(**dict({'tenant_id':TID,'project_id':project.id,'project_type':'SCHOLARSHIP',
                'year_code':'2099-2100','status':'OPEN'}, **fields))
            db.add(batch); db.flush(); invalid.append(str(batch.id))
        for fields in [{'status':'DISABLED'}, {'is_deleted':True}, {'tenant_id':TID+99}]:
            hidden = FundingProject(**dict({'tenant_id':TID,'project_name':'不可用项目','project_type':'SCHOLARSHIP',
                'amount':3000,'status':'ENABLED'}, **fields))
            db.add(hidden); db.flush()
            batch = FundingBatch(tenant_id=TID, project_id=hidden.id, project_type='SCHOLARSHIP', year_code='2099-2100', status='OPEN')
            db.add(batch); db.flush(); invalid.append(str(batch.id))
        db.commit()
    teacher = _hdr(client, 'school_admin01')
    for prefix, kind in [('/api/v1/portal', 'PC'), ('/api/v1/mobile', 'STUDENT_MINI')]:
        headers = _login(client, 'fund_batch_student', kind)
        url = prefix + '/affairs/funding/batches'
        first = client.get(url, headers=headers)
        assert first.status_code == 200, first.text
        data = first.json()['data']
        assert data['total'] == 210 and len(data['items']) == 20
        assert target_id not in [row['batchId'] for row in data['items']]
        last = client.get(url, headers=headers, params={'page':11}).json()['data']
        assert len(last['items']) == 10 and target_id in [row['batchId'] for row in last['items']]
        for query in [{'keyword':'历史专项'}, {'keyword':'2021-2022'}, {'keyword':'%'}, {'projectType':'SCHOLARSHIP'}]:
            found = client.get(url, headers=headers, params=query).json()['data']
            assert found['total'] == 1 and found['items'][0]['batchId'] == target_id
            assert '历史专项100%奖学金' in found['items'][0]['batchName']
        assert client.get(url, headers=headers, params={'keyword':'2099'}).json()['data'] == {'items':[], 'total':0}
        assert client.get(url, headers=headers, params={'pageSize':201}).status_code == 400
        assert client.get(url, headers=headers, params={'projectType':'LOAN'}).status_code == 400
        assert client.get(url, headers=teacher).status_code == 403
        for batch_id in invalid:
            denied = client.post(prefix+'/affairs/funding/apply', headers=headers,
                json={'batchId':batch_id,'statement':'隔离批次窗口验收申请','confirm':True})
            assert denied.status_code in (404, 409), denied.text
    for batch_id in invalid:
        denied = client.post(BASE+'/funding/applications', headers=teacher,
            json={'batchId':batch_id,'studentId':str(ids['sa']),'statement':'教师代办窗口验收'})
        assert denied.status_code in (404, 409), denied.text
        preflight = client.get(BASE+'/funding/preflight', headers=teacher,
            params={'batchId':batch_id,'studentId':str(ids['sa'])})
        assert preflight.status_code in (404, 409), preflight.text
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(FundingApplication)) == 0
