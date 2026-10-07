"""Real four-client funding commands: rule parity, private evidence and returned edits."""
import json
from decimal import Decimal

from sqlalchemy import func, select
from test_affairs_funding import BASE, TID, _seed, _approve_to_publicity
from test_aid_material_flow import _data
from test_aid_mobile_queue import _login
from affairs_contract_test_support import expire_publicity, post_versioned, role_headers


def _accounts(db_mode):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, User, UserRole, StudentAccountLink
    ids = _seed(db_mode)
    with get_sessionmaker()() as db:
        role = Role(tenant_id=TID, role_code='STUDENT', role_name='学生', role_type='SYSTEM', status='ACTIVE')
        db.add(role); db.flush()
        for name, sid in [('fund_student',ids['sa']),('fund_other',ids['sb'])]:
            user = User(tenant_id=TID, login_name=name, real_name=name, user_type='STUDENT',
                password_hash=hash_password('AidQueue-Test-2026!'), status='ACTIVE', must_change_password=False)
            db.add(user); db.flush()
            db.add(UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status='ACTIVE'))
            db.add(StudentAccountLink(tenant_id=TID, user_id=user.id, student_id=sid, link_status='ACTIVE', source='MANUAL'))
        db.commit()
    return ids


def _project_batch(client, admin, *, conditions=None):
    project = _data(client.post(BASE+'/funding/projects', headers=admin, json={
        'projectName':'四端项目规则验收','projectType':'SCHOLARSHIP','amount':3000,'quota':10,'conditions':conditions or {}}))
    batch = _data(client.post(BASE+'/funding/batches', headers=admin, json={
        'projectId':project['projectId'],'schoolYear':'2026-2027','publicityDays':1,'quota':10,'publish':True}))
    return project, batch


def test_funding_student_rules_evidence_return_review_and_disbursement(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import FundingApplication, StudentProfile, FundingBatch
    from app.services.affairs_student_atomic_service import _payload_sha256
    ids = _accounts(db_mode)
    admin = _login(client,'school_admin01','PC')
    counselor = _login(client,'counselor01','TEACHER_MINI')
    pc = _login(client,'fund_student','PC'); mini = _login(client,'fund_student','STUDENT_MINI')
    other = _login(client,'fund_other','PC')
    project, batch = _project_batch(client,admin,conditions={'eligibility':{'requireActiveStatus':False}})
    with get_sessionmaker()() as db:
        db.get(StudentProfile,ids['sa']).student_status='SUSPENDED'; db.commit()
    preflight = _data(client.get(BASE+'/funding/preflight',headers=admin,
        params={'batchId':batch['batchId'],'studentId':ids['sa']}))
    assert preflight['eligible'] is True and preflight['checkSnapshot']['rules']['requireActiveStatus'] is False
    uploaded = _data(client.post('/api/v1/files',headers=pc,data={'bizType':'FUNDING'},
        files={'file':('funding-evidence.txt',b'owned scholarship evidence','text/plain')}))
    file_id=uploaded['fileId']
    assert client.get('/api/v1/files/'+file_id,headers=other).status_code in (403,404)
    statement='依据学校开放项目提交申请，请核验附件。'
    created = _data(client.post('/api/v1/portal/affairs/funding/apply',headers=pc,json={
        'batchId':batch['batchId'],'statement':statement,'amount':'9.99','confirm':True,'fileIds':[file_id]}))
    app_id=created['applicationId']
    detail_urls = ['/api/v1/portal/affairs/funding/applications/'+app_id,
                   '/api/v1/mobile/affairs/funding/applications/'+app_id]
    for url, headers in zip(detail_urls, [pc, mini]):
        mine = _data(client.get(url, headers=headers))
        assert mine['requestedAmount'] == '3000.00' and mine['approvedAmount'] is None
        assert mine['statement'] == statement and mine['disbursements'] == []
        assert mine['applicationId'] == app_id and mine['status'] == 'COUNSELOR_REVIEW'
        assert 'checkSnapshot' not in mine and 'studentId' not in mine
        assert client.get(url, headers=other).status_code in (403,404)
        assert client.get(url, headers=admin).status_code == 403
    with get_sessionmaker()() as db:
        row=db.get(FundingApplication,int(app_id)); snapshot=json.loads(row.check_snapshot_json)
        assert row.amount == row.requested_amount == Decimal('3000.00') and row.approved_amount is None
        assert str(snapshot['projectId'])==project['projectId'] and snapshot['rules']['requireActiveStatus'] is False
        assert snapshot['amountAuthority']['amount']=='3000.00'
        expected=_payload_sha256({'bizType':'FUNDING_COMMIT','studentId':ids['sa'],'batchId':int(batch['batchId']),
            'projectType':'SCHOLARSHIP','amount':'3000.00','statement':statement,'checkSnapshot':snapshot})
        assert created['payloadSha256']==expected
    for headers in [pc,mini,admin,counselor]:
        files=_data(client.get('/api/v1/files',headers=headers,params={'bizType':'FUNDING','bizId':app_id}))['items']
        assert [x['fileId'] for x in files]==[file_id]
    assert client.get('/api/v1/files',headers=other,params={'bizType':'FUNDING','bizId':app_id}).status_code in (403,404)
    detail=_data(client.get('/api/v1/mobile/teacher/affairs/funding/'+app_id,headers=counselor))
    assert detail['allowedActions'] == ['APPROVE', 'RETURN', 'REJECT']
    pending=_data(client.get('/api/v1/mobile/teacher/affairs/funding/pending',headers=counselor))
    assert next(x for x in pending['list'] if x['applicationId']==app_id)['allowedActions'] == detail['allowedActions']
    admin_detail=_data(client.get('/api/v1/mobile/teacher/affairs/funding/'+app_id,headers=admin))
    assert admin_detail['allowedActions'] == []  # Administrator is not the current counselor assignee.
    returned=_data(client.post('/api/v1/mobile/teacher/affairs/funding/'+app_id+'/review',headers=counselor,
        json={'action':'RETURN','reason':'请补充本人申请说明','version':detail['version']}))
    assert returned['status']=='RETURNED'
    assert _data(client.get(detail_urls[0], headers=pc))['allowedActions'] == ['EDIT_RETURNED','RESUBMIT']
    assert _data(client.get('/api/v1/mobile/teacher/affairs/funding/'+app_id,headers=counselor))['allowedActions'] == []
    editable='/api/v1/mobile/affairs/funding/'+app_id
    draft=_data(client.get(editable+'/editable',headers=mini))
    assert client.get(editable+'/editable',headers=other).status_code in (403,404)
    update=_data(client.put(editable+'/returned',headers=mini,
        json={'statement':'已按老师要求补充完整申请说明。','amount':'999999','version':draft['version']}))
    with get_sessionmaker()() as db:
        row=db.get(FundingApplication,int(app_id)); assert row.amount==Decimal('3000.00')
        # Closing NEW applications must not strand a returned, already accepted application.
        db.get(FundingBatch,int(batch['batchId'])).status='CLOSED'; db.commit()
    resubmitted=_data(client.post(editable+'/resubmit',headers=pc,json={'version':update['version']}))
    assert resubmitted['status']=='COUNSELOR_REVIEW'
    with get_sessionmaker()() as db:
        row=db.get(FundingApplication,int(app_id)); current=json.loads(row.check_snapshot_json)
        assert current['amountAuthority']==snapshot['amountAuthority']
        assert current['rules']['requireActiveStatus'] is False
    _approve_to_publicity(client,app_id)
    teacher_mini = _login(client, 'school_admin01', 'TEACHER_MINI')
    for submit_url, applicant, review_on_mini in [
        ('/api/v1/portal/affairs/funding/appeal', pc, True),
        ('/api/v1/mobile/affairs/funding/appeal', mini, False),
    ]:
        appeal = _data(client.post(submit_url, headers=applicant,
            json={'applicationId': app_id, 'reason': '请复核本人的公示资助信息'}))
        appeal_id = appeal['appealId']
        exact_url = '/api/v1/mobile/teacher/affairs/appeals/FUNDING_APPEAL/' + appeal_id + '/detail'
        queue = _data(client.get('/api/v1/mobile/teacher/affairs/appeals/FUNDING_APPEAL', headers=teacher_mini, params={'page':1,'pageSize':1}))
        assert queue['total'] == 1 and queue['items'][0]['allowedActions'] == ['REVIEW']
        exact = _data(client.get(exact_url, headers=teacher_mini))
        assert exact['appealId'] == appeal_id and exact['applicationId'] == app_id
        assert client.get(exact_url, headers=pc).status_code == 403
        assert client.post(submit_url, headers=applicant,
            json={'applicationId':app_id,'reason':'不允许重复提交进行中申诉'}).status_code == 409
        review_url = '/api/v1/mobile/teacher/affairs/appeals/FUNDING_APPEAL/' + appeal_id + '/review' if review_on_mini else BASE+'/funding/appeals/'+appeal_id+'/review'
        review_headers = teacher_mini if review_on_mini else admin
        body = {'version':exact['version'],'result':'OVERRULED','opinion':'经复核公示信息无误，维持原公示。'}
        assert client.post(review_url, headers=review_headers, json={**body,'version':exact['version']+10}).status_code == 409
        assert _data(client.post(review_url, headers=review_headers, json=body))['status'] == 'CLOSED'
        assert client.post(review_url, headers=review_headers, json=body).status_code == 409
        closed = _data(client.get(exact_url, headers=teacher_mini))
        assert closed['status'] == 'CLOSED' and closed['allowedActions'] == []
        from app.models import UnifiedMessage
        with get_sessionmaker()() as db:
            notice = db.scalar(select(UnifiedMessage).where(UnifiedMessage.tenant_id == TID,
                UnifiedMessage.title == '资助公示申诉结果', UnifiedMessage.source_biz_id == int(appeal_id)))
            assert notice is not None
            notice_id = str(notice.id)
            assert notice.action_params_json == {'bizType':'FUNDING','recordId':app_id}
        message_urls = ['/api/v1/portal/messages/'+notice_id, '/api/v1/mobile/me/messages/'+notice_id]
        for url, headers in zip(message_urls, [pc, mini]):
            action = _data(client.get(url, headers=headers))['action']
            assert action['target']['query']['recordId'] == app_id
            assert action['target']['path'] in ('/campus-service','/pages/student/affairs/funding')
            if headers == pc:
                assert action['target']['query']['tab'] == 'funding'
        # Historical notices stored the appeal ID, which differs from the application on round two.
        with get_sessionmaker()() as db:
            db.get(UnifiedMessage, int(notice_id)).action_params_json = {'bizType':'FUNDING_APPEAL','recordId':appeal_id}
            db.commit()
        for url, headers in zip(message_urls, [pc, mini]):
            action = _data(client.get(url, headers=headers))['action']
            assert action['target']['query']['recordId'] == app_id
            assert action['target']['query']['bizType'] == 'FUNDING'
        with get_sessionmaker()() as db:
            db.get(UnifiedMessage, int(notice_id)).action_params_json = {'bizType':'FUNDING_APPEAL','recordId':'99999999'}
            db.commit()
        for url, headers in zip(message_urls, [pc, mini]):
            assert _data(client.get(url, headers=headers))['action']['target'] is None
        for url, headers in zip(detail_urls,[pc,mini]):
            result = _data(client.get(url,headers=headers))
            assert result['hasPendingAppeal'] is False and result['status'] == 'PUBLICITY'
            assert result['appealResults'][0]['reviewOpinion'] == body['opinion']
    expire_publicity('FundingApplication',app_id)
    staff=role_headers('STUDENT_AFFAIRS_ADMIN',login_name='sa_admin01',real_name='测试学工处管理员')
    granted=_data(post_versioned(client,BASE+'/funding/applications/'+app_id+'/publicity-confirm',headers=staff))
    assert granted['status']=='GRANTED'
    generated=_data(client.post(BASE+'/funding/batches/'+batch['batchId']+'/disbursements/generate',headers=staff))
    assert generated['generated']==1
    item=_data(client.get(BASE+'/funding/disbursements',headers=staff,params={'batchId':batch['batchId']}))['items'][0]
    item=_data(client.post(BASE+'/funding/disbursements/'+item['disbursementId']+'/fail',headers=staff,
        json={'version':item['version'],'reason':'账户信息需核对，请联系负责老师'}))
    teacher_result_url = '/api/v1/mobile/teacher/affairs/funding/'+app_id
    for url, headers in zip([*detail_urls, teacher_result_url], [pc, mini, teacher_mini]):
        payment=_data(client.get(url, headers=headers))['disbursements'][0]
        assert payment['status']=='FAILED' and payment['failReason']=='账户信息需核对，请联系负责老师'
    issued=_data(client.post(BASE+'/funding/disbursements/'+item['disbursementId']+'/issue',headers=staff,
        json={'version':item['version'],'disburseNo':'TEST-FUNDING-001','bankLast4':'1234'}))
    assert issued['bankStatus']=='ISSUED' and issued['amount']=='3000.00'
    from app.models import FundingAppeal, AffairsAuditTrail
    with get_sessionmaker()() as db:
        db.add(FundingAppeal(tenant_id=TID, application_id=int(app_id), student_id=ids['sa'],
            status='CLOSED', result='OVERRULED', appellant_name='PRIVATE_APPELLANT',
            reason='PRIVATE_APPEAL_REASON', reviewer='PRIVATE_REVIEWER', review_opinion='经复核维持原资助结果。'))
        db.add(AffairsAuditTrail(tenant_id=TID, biz_type='FUNDING', biz_id=int(app_id),
            action='PROJECT_CREATE', detail='PRIVATE_PROJECT_DETAIL', operator='PRIVATE_OPERATOR'))
        db.commit()
    results=[]
    for url, headers in zip(detail_urls, [pc, mini]):
        mine = _data(client.get(url, headers=headers)); results.append(mine)
        assert mine['status']=='GRANTED' and mine['approvedAmount']=='3000.00'
        assert mine['disbursements'][0]['status']=='ISSUED' and mine['disbursements'][0]['amount']=='3000.00'
        assert mine['disbursements'][0]['issuedAt']
        assert mine['disbursements'][0]['failReason']==''
        assert mine['appealResults'][0]['reviewOpinion']=='经复核维持原资助结果。'
        assert 'PRIVATE_' not in json.dumps(mine)
        assert any(event['title']=='确认获资助' for event in mine['history'])
        assert all('operator' not in event for event in mine['history'])
    assert results[0] == results[1]
    teacher_payment = _data(client.get(teacher_result_url, headers=teacher_mini))['disbursements'][0]
    assert teacher_payment['status'] == 'ISSUED' and teacher_payment['failReason'] == ''
    assert teacher_payment['issuedAt'] and 'bankLast4' not in teacher_payment and 'disburseNo' not in teacher_payment
    with get_sessionmaker()() as db:
        db.add_all([FundingAppeal(tenant_id=TID,application_id=int(app_id),student_id=ids['sa'],
            status='CLOSED',result='OVERRULED',reason='隔离历史申诉完整分页验收') for _ in range(205)])
        db.commit()
    all_ids=[]
    for page in range(1,12):
        history = _data(client.get(BASE+'/funding/appeals',headers=admin,
            params={'status':'CLOSED','page':page,'pageSize':20,'applicationId':app_id}))
        assert history['total'] == 208
        all_ids.extend(x['appealId'] for x in history['items'])
        assert all(x['allowedActions'] == [] for x in history['items'])
    assert len(all_ids) == len(set(all_ids)) == 208
    assert _data(client.get(BASE+'/funding/appeals',headers=admin,params={'appealId':appeal_id}))['total'] == 1
    for url, headers in [('/api/v1/portal/affairs/funding',pc),('/api/v1/mobile/affairs/funding/my',mini)]:
        mine=_data(client.get(url,headers=headers))['items']
        listed = next(x for x in mine if x['applicationId']==app_id)
        assert listed['status']=='GRANTED'
        assert listed['projectName'] == '四端项目规则验收'
        assert listed['schoolYear'] == '2026-2027' and listed['batchId'] == batch['batchId']
        assert listed['projectName'] == results[0]['projectName']
    with get_sessionmaker()() as db:
        db.get(FundingApplication,int(app_id)).is_deleted=True; db.commit()
    for url, headers in zip(detail_urls, [pc, mini]):
        assert client.get(url,headers=headers).status_code in (403,404)
    for url, headers in [('/api/v1/portal/affairs/funding',pc),('/api/v1/mobile/affairs/funding/my',mini)]:
        mine=_data(client.get(url,headers=headers))['items']
        assert all(x['applicationId'] != app_id for x in mine)


def test_funding_foreign_evidence_rolls_back_application_and_teacher_freeze_is_atomic(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import FundingApplication, WorkflowInstance
    from app.services import affairs_funding_authority_service as authority
    from app.core.exceptions import AppException
    ids=_accounts(db_mode)
    admin=_login(client,'school_admin01','PC'); pc=_login(client,'fund_student','PC'); other=_login(client,'fund_other','PC')
    _,batch=_project_batch(client,admin)
    file_id=_data(client.post('/api/v1/files',headers=other,data={'bizType':'FUNDING'},
        files={'file':('other-evidence.txt',b'other private evidence','text/plain')}))['fileId']
    denied=client.post('/api/v1/mobile/affairs/funding/apply',headers=pc,json={
        'batchId':batch['batchId'],'statement':'这份文件并不属于当前申请人','confirm':True,'fileIds':[file_id]})
    assert denied.status_code in (403,404),denied.text
    def fail_freeze(*args):
        raise AppException('DATA_CONFLICT','隔离注入金额冻结失败')
    monkeypatch.setattr(authority,'_freeze_rule_snapshot',fail_freeze)
    failed=client.post(BASE+'/funding/applications',headers=admin,json={
        'batchId':batch['batchId'],'studentId':str(ids['sa']),'statement':'事务回滚验收申请'})
    assert failed.status_code==409,failed.text
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(FundingApplication))==0
        assert db.scalar(select(func.count()).select_from(WorkflowInstance).where(WorkflowInstance.source_biz_type=='FUNDING'))==0
