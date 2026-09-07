"""One canonical enterprise position across correction, school publication and both student facades."""
from datetime import datetime, timedelta
import uuid

from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import (
    InternshipAuditTrail,
    InternshipBatchParticipant,
    InternshipEnterpriseInspection,
    InternshipRecord,
    MessageEventOutbox,
    UnifiedMessage,
)
from tests.test_internship_existing_member_invite import _fixture, PORTAL
from tests.test_internship_catalog_preparation import _linked_student_headers
from tests.test_internship_student import _student, _record, _RIGHTS_FACTS, TID, POS


def test_enterprise_correction_publication_and_student_pc_mobile_supply_loop(client, auth_headers, db_mode):
    now = datetime.utcnow()
    start, end = (now-timedelta(days=1)).isoformat()+'Z', (now+timedelta(days=2)).isoformat()+'Z'
    _, company_body, _, _, _, enterprise = _fixture(client, auth_headers, windows={
        'positionSubmitStartAt': start, 'positionSubmitEndAt': end,
        'studentSelectStartAt': start, 'studentSelectEndAt': end,
    })
    campaign = client.get(PORTAL+'/campaigns',headers=enterprise).json()['data'][0]
    params={'campaignId':campaign['id']}
    # Existing verified upstream facts: approved inspection, formal roster and qualification.
    no='SUPPLY-'+uuid.uuid4().hex[:10]
    sid=_student(client,auth_headers,no); rid=_record(client,auth_headers,sid,campaign['batchId'])
    student={**_linked_student_headers(sid,no),'X-Internship-Batch-Id':campaign['batchId']}
    with get_sessionmaker()() as db:
        db.get(InternshipRecord,int(rid)).eligibility_status='QUALIFIED'
        if not db.scalar(select(InternshipBatchParticipant).where(InternshipBatchParticipant.batch_id==int(campaign['batchId']),InternshipBatchParticipant.student_id==int(sid))):
            db.add(InternshipBatchParticipant(tenant_id=TID,batch_id=int(campaign['batchId']),student_id=int(sid),internship_id=int(rid),source='MANUAL',status='ACTIVE'))
        db.add(InternshipEnterpriseInspection(tenant_id=TID,company_id=int(company_body['companyId']),batch_id=int(campaign['batchId']),status='APPROVED',valid_until=now+timedelta(days=100),conclusion='虚构已核验准入事实'))
        db.commit()
    payload={'title':'虚构跨端供给岗位','headcount':3,'workLocation':'虚构园区','workAddress':'虚构园区1号',**_RIGHTS_FACTS}
    created=client.post(PORTAL+'/positions',headers=enterprise,params=params,json=payload)
    assert created.status_code==200,created.json()
    draft=created.json()['data']; pid=draft['id']
    def position_tasks(headers=enterprise, scope=params):
        response=client.get(PORTAL+'/dashboard', headers=headers, params=scope)
        assert response.status_code==200, response.json()
        return [task for task in response.json()['data']['tasks'] if task['objectType']=='INTERNSHIP_POSITION']
    initial_task=next(task for task in position_tasks() if task['objectId']==pid)
    assert initial_task['actionLabel']=='继续填写'
    student_roots=['/api/v1/portal/internship','/api/v1/mobile/internship']

    def catalog(visible):
        for root in student_roots:
            response=client.get(root+'/catalog/positions',headers=student)
            assert response.status_code==200,response.json()
            data=response.json()['data']
            ids=[str(item.get('id') or item.get('positionId')) for item in data['items']]
            assert (pid in ids) is visible, data
            assert '补正专用公开意见' not in str(data) and '内部意见不可公开' not in str(data)
            detail=client.get(root+'/catalog/positions/'+pid,headers=student)
            assert detail.status_code==(200 if visible else 404),detail.json()

    catalog(False)
    submitted=client.post(f'{PORTAL}/positions/{pid}/submit',headers=enterprise,params=params,json={'expectedVersion':draft['version']})
    assert submitted.status_code==200,submitted.json()
    pending=submitted.json()['data']; catalog(False)
    assert next(task for task in position_tasks() if task['objectId']==pid)['actionLabel']=='查看这个岗位'
    status_url=f'{POS}/{pid}/status'
    assert client.post(status_url,headers=auth_headers,json={'action':'RETURN','expectedVersion':pending['version'],'reason':'  '}).status_code==400
    assert client.post(status_url,headers=auth_headers,json={'action':'RETURN','reason':'补正专用公开意见'}).status_code==409
    assert client.post(status_url,headers=auth_headers,json={'action':'RETURN','expectedVersion':draft['version'],'reason':'补正专用公开意见'}).status_code==409
    assert client.post(status_url,headers=student,json={'action':'RETURN','expectedVersion':pending['version'],'reason':'越权'}).status_code==403
    returned=client.post(status_url,headers=auth_headers,json={'action':'RETURN','expectedVersion':pending['version'],'reason':'补正专用公开意见：补充详细工作地址。'})
    assert returned.status_code==200,returned.json()
    corrected=returned.json()['data']; assert corrected['status']=='DRAFT'
    inbox=client.get(PORTAL+'/messages',headers=enterprise).json()['data']
    returned_message=next(item for item in inbox['items'] if item['actionParams']['positionId']==pid)
    assert returned_message['msgType']=='RETURNED_NOTICE' and returned_message['readStatus']=='UNREAD'
    assert returned_message['actionKey']=='enterprise.internship.position'
    assert returned_message['actionParams']=={'positionId':pid,'campaignId':campaign['id']}
    assert '补正专用公开意见' in returned_message['summary']
    message_id=returned_message['messageId']
    assert client.get(PORTAL+'/messages/count',headers=enterprise).json()['data']['unread']==1
    detail_message=client.get(f'{PORTAL}/messages/{message_id}',headers=enterprise)
    assert detail_message.status_code==200 and '补充详细工作地址' in detail_message.json()['data']['content']
    assert client.post(f'{PORTAL}/messages/{message_id}/read',headers=enterprise).status_code==200
    assert client.get(PORTAL+'/messages/count',headers=enterprise).json()['data']['unread']==0
    with get_sessionmaker()() as db:
        delivered=db.get(UnifiedMessage,int(message_id))
        assert delivered.receiver_type=='ENTERPRISE' and delivered.receiver_user_id
        event=db.scalar(select(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id==TID,
            MessageEventOutbox.source_biz_id==int(pid),
            MessageEventOutbox.event_code=='INTERNSHIP.POSITION.RETURNED',
        ))
        assert event and event.status=='SUCCEEDED' and event.attempt_count==1
    with get_sessionmaker()() as db:
        # A newer internal/legacy return must not replace or leak into the public projection.
        db.add(InternshipAuditTrail(tenant_id=TID,target_type='POSITION',target_id=int(pid),action='STATUS_RETURN',operator_name='内部审核人',detail_json={'reason':'内部意见不可公开'},occurred_at=now))
        db.commit()
    detail=client.get(f'{PORTAL}/positions/{pid}',headers=enterprise,params=params).json()['data']
    assert detail['schoolReturn']['reason']=='补正专用公开意见：补充详细工作地址。'
    assert set(detail['schoolReturn'])=={'id','reason','returnedAt'}
    listed=client.get(PORTAL+'/positions',headers=enterprise,params=params).json()['data']['items']
    assert next(item for item in listed if item['id']==pid)['schoolReturn']==detail['schoolReturn']
    correction_task=next(task for task in position_tasks() if task['objectId']==pid)
    assert correction_task['actionLabel']=='补正这个岗位'
    assert correction_task['description']==detail['schoolReturn']['reason']
    assert correction_task['href']==f"/positions/{pid}/edit?campaignId={campaign['id']}"
    for index in range(4):
        later=client.post(PORTAL+'/positions',headers=enterprise,params=params,json={**payload,'title':f'较新的普通草稿 {index}'})
        assert later.status_code==200,later.json()
    queue=position_tasks()
    assert len(queue)==3
    assert queue[0]['objectId']==pid and queue[0]['actionLabel']=='补正这个岗位'
    assert all(task['actionLabel']=='继续填写' for task in queue[1:])
    _, _, _, _, _, other_enterprise = _fixture(client, auth_headers)
    other_campaign = client.get(PORTAL+'/campaigns', headers=other_enterprise).json()['data'][0]
    assert pid not in [task['objectId'] for task in position_tasks(other_enterprise, {'campaignId':other_campaign['id']})]
    assert client.get(f'{PORTAL}/messages/{message_id}',headers=other_enterprise).status_code==404
    for scope in (params, {'campaignId': other_campaign['id']}):
        denied = client.get(f'{PORTAL}/positions/{pid}', headers=other_enterprise, params=scope)
        assert denied.status_code in (403, 404), denied.json()
        assert '补正专用公开意见' not in denied.text
    catalog(False)
    edited=client.put(f'{PORTAL}/positions/{pid}',headers=enterprise,params=params,json={'expectedVersion':corrected['version'],'workAddress':'虚构园区1号楼2层'})
    assert edited.status_code==200,edited.json()
    resubmitted=client.post(f'{PORTAL}/positions/{pid}/submit',headers=enterprise,params=params,json={'expectedVersion':edited.json()['data']['version']})
    assert resubmitted.status_code==200,resubmitted.json()
    assert next(task for task in position_tasks() if task['objectId']==pid)['actionLabel']=='查看这个岗位'
    withdrawn=client.post(f'{PORTAL}/positions/{pid}/withdraw',headers=enterprise,params=params,json={'expectedVersion':resubmitted.json()['data']['version']})
    assert withdrawn.status_code==200,withdrawn.json()
    resumed_task=next(task for task in position_tasks() if task['objectId']==pid)
    assert resumed_task['actionLabel']=='继续填写'
    assert '补正专用公开意见' not in resumed_task['description']
    resubmitted=client.post(f'{PORTAL}/positions/{pid}/submit',headers=enterprise,params=params,json={'expectedVersion':withdrawn.json()['data']['version']})
    assert resubmitted.status_code==200,resubmitted.json()
    published=client.post(status_url,headers=auth_headers,json={'action':'PUBLISH','expectedVersion':resubmitted.json()['data']['version']})
    assert published.status_code==200,published.json()
    publish_messages=client.get(PORTAL+'/messages',headers=enterprise,params={'readStatus':'UNREAD'}).json()['data']['items']
    assert any(item['msgType']=='WORKFLOW_RESULT' and item['actionParams']['positionId']==pid for item in publish_messages)
    assert client.get(f'{PORTAL}/positions/{pid}',headers=enterprise,params=params).json()['data']['status']=='PUBLISHED'
    catalog(True)
    assert client.post(status_url,headers=auth_headers,json={'action':'RETURN','expectedVersion':published.json()['data']['version'],'reason':'不应退回已上架岗位'}).status_code==409
    offlined=client.post(status_url,headers=auth_headers,json={'action':'OFFLINE','expectedVersion':published.json()['data']['version']})
    assert offlined.status_code==200,offlined.json()
    status_messages=client.get(PORTAL+'/messages',headers=enterprise,params={'readStatus':'UNREAD'}).json()['data']['items']
    assert any(item['msgType']=='STATUS_CHANGED' and item['actionParams']['positionId']==pid for item in status_messages)
    catalog(False)
