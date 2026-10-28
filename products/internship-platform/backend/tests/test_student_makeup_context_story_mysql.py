"""学生补卡正式上下文到已有校级动态审批队列；不新增任何导师权限。"""
import pytest
from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import InternshipCheckin
from test_student_support_story_mysql import seed_support, context, result
from test_yiyang_plan_export_options_mysql import login
from test_yiyang_write_flows_mysql import upload, png_bytes

ROOT='/api/v1/mobile/internship/context/makeups'
STAFF='/api/v1/internship/makeups'


@pytest.fixture
def story(record_property):
    data=seed_support()
    for key in ['tenantId','tenantCode','batchId','recordId']:record_property(key,data[key])
    return data


def body(data,**extra):
    return {**context(data),'checkinDate':'2026-10-12','reason':'合成缺卡原因，等待学校原权限审核。','makeupType':'MISSING',**extra}


def test_makeup_reaches_existing_school_pending_queue_then_same_record_is_approved(story):
    with login(story,'STUDENT') as student,login(story) as school,login(story,'INTERN_MENTOR') as mentor:
        row=result(student.post(ROOT,json=body(story)))
        assert mentor.post(STAFF+'/'+row['id']+'/approve',json={'expectedVersion':row['version']}).status_code==403
        pending=result(school.get(STAFF,params={'batchId':story['batchId'],'status':'PENDING'}))
        assert row['id'] in {item['id'] for item in pending['items']}
        same=result(school.get(STAFF+'/'+row['id']));assert same['id']==row['id']
        approved=result(school.post(STAFF+'/'+row['id']+'/approve',json={'expectedVersion':same['version'],'comment':'按学校补卡职责核对通过'}))
        assert approved['id']==row['id'] and approved['status']=='APPROVED'
        read=result(student.get(ROOT,params=context(story)))
        assert read['items'][0]['id']==row['id'] and read['items'][0]['status']=='APPROVED'
        assert result(school.get(STAFF,params={'batchId':story['batchId'],'status':'PENDING'}))['total']==0
    with get_sessionmaker()() as db:
        checkin=db.scalar(select(InternshipCheckin).where(InternshipCheckin.tenant_id==int(story['tenantId']),InternshipCheckin.internship_id==int(story['recordId']),InternshipCheckin.checkin_date=='2026-10-12'))
        assert checkin is not None and checkin.result=='RECORDED'


def test_makeup_evidence_is_actually_readable_by_original_authorized_reviewer(story):
    with login(story,'STUDENT') as student,login(story) as school:
        file=upload(student,name='makeup-synthetic.png',biz='INTERNSHIP')
        row=result(student.post(ROOT,json=body(story,makeupType='OUT_OF_RANGE',evidenceFileId=file['fileId'])))
        detail=result(school.get(STAFF+'/'+row['id']))
        assert detail['attachment']['fileId']==file['fileId']
        downloaded=school.get('/api/v1/files/download/'+file['fileId'])
        assert downloaded.status_code==200 and downloaded.content==png_bytes()
        result(school.post(STAFF+'/'+row['id']+'/evidence-viewed'))
        approved=result(school.post(STAFF+'/'+row['id']+'/approve',json={'expectedVersion':detail['version']}))
        assert approved['status']=='APPROVED'


def test_makeup_withdraw_keeps_same_id_and_disappears_from_school_pending_queue(story):
    with login(story,'STUDENT') as student,login(story) as school:
        row=result(student.post(ROOT,json=body(story)))
        assert student.post(ROOT+'/'+row['id']+'/withdraw',json={**context(story),'expectedVersion':row['version']+1}).status_code==400
        withdrawn=result(student.post(ROOT+'/'+row['id']+'/withdraw',json={**context(story),'expectedVersion':row['version']}))
        assert withdrawn['id']==row['id'] and withdrawn['status']=='WITHDRAWN'
        read=result(student.get(ROOT,params=context(story)))['items'][0]
        assert read['id']==row['id'] and read['status']=='WITHDRAWN'
        assert result(school.get(STAFF,params={'batchId':story['batchId'],'status':'PENDING'}))['total']==0
