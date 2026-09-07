"""Mobile teacher position reads preserve batch, record scope and field boundaries."""
import uuid
from app.core.security import create_access_token
from app.models import InternshipBatch, InternshipRecord, InternshipPosition, StudentProfile
from tests.test_internship_position_publish_versions import position, session, TENANT

ROOT='/api/v1/mobile/teacher/internship/context/positions'

def headers(uid, role='INTERN_MENTOR', tenant=TENANT):
    return {'Authorization':'Bearer '+create_access_token({
        'userId':str(uid),'realName':'虚构指导教师','userType':'STUDENT' if role=='STUDENT' else 'TEACHER',
        'currentRoleCode':role,'tenantId':str(tenant),'tid':'x','clientType':'MP',
    })}

def test_teacher_mobile_position_scope_readonly_and_private_fields(client, position):
    _, row=position
    with session() as db:
        student=StudentProfile(tenant_id=TENANT,student_no='MOB-POS-'+uuid.uuid4().hex[:10],real_name='不应投影的学生姓名',current_stage='INTERN',status='ACTIVE')
        db.add(student);db.flush()
        db.add(InternshipRecord(tenant_id=TENANT,student_id=student.id,batch_id=int(row['batchId']),advisor_user_id=9001,status='PREPARING'))
        other=InternshipBatch(tenant_id=TENANT,batch_name='其他指导批次',batch_no=uuid.uuid4().hex,status='RUNNING')
        db.add(other);db.flush();other_id=other.id
        db.get(InternshipPosition,int(row['id'])).risk_note='内部风险调查说明'
        db.commit()
    params={'batchId':row['batchId']}
    own=headers(9001)
    listed=client.get(ROOT,headers=own,params=params)
    assert listed.status_code==200,listed.json()
    data=listed.json()['data'];assert data['batchId']==row['batchId']
    assert [item['id'] for item in data['items']]==[row['id']]
    detail=client.get(ROOT+'/'+row['id'],headers=own,params=params)
    assert detail.status_code==200,detail.json()
    assert detail.json()['data']['dailyHours']==8
    assert not {'assignedStudents','auditTrail','riskNote','remark','geofenceLat'} & set(detail.json()['data'])
    assert '不应投影的学生姓名' not in detail.text and '内部风险调查说明' not in detail.text
    assert client.get(ROOT,headers=own,params={**params,'keyword':'不会匹配的关键词'}).json()['data']['total']==0
    for endpoint in (ROOT,ROOT+'/'+row['id']):
        assert client.get(endpoint,headers=headers(9002),params=params).status_code==404
        assert client.get(endpoint,headers=own,params={'batchId':str(other_id)}).status_code==404
        assert client.get(endpoint,headers=headers(9001,tenant=TENANT+1),params=params).status_code==404
        assert client.get(endpoint,headers=headers(9001,role='STUDENT'),params=params).status_code==403
        assert client.get(endpoint,params=params).status_code==401
    assert client.get(ROOT+'/'+str(int(row['id'])+1000),headers=own,params=params).status_code==404
    assert client.get(ROOT,headers=own).status_code==400
    assert client.get(ROOT,headers=own,params={**params,'status':'INVALID'}).status_code==400
    assert client.post(ROOT+'/'+row['id'],headers=own,params=params,json={'action':'PUBLISH'}).status_code in (403,405)
    denied=client.post('/api/v1/internship/positions/'+row['id']+'/status',headers=own,json={'action':'SUBMIT','expectedVersion':row['version']})
    assert denied.status_code==403
