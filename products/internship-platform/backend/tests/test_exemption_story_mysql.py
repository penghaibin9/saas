"""Exemption original-document lifecycle with normal roles and real scanned evidence."""
import os
from io import BytesIO
import pytest
from openpyxl import Workbook
from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import InternshipRecord,InternshipApplication,InternshipAuditTrail,FileBinding,InternshipBatch
from app.services.file_scan_service import process_next_scan_job
from test_plan_allocation_story_mysql import seed_plan_story,login,ok,context,ROOT,PORTAL

@pytest.fixture
def story():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE')!='1':pytest.skip('isolated MySQL opt-in required')
    result=seed_plan_story()
    with get_sessionmaker()() as db:
        record=db.get(InternshipRecord,int(result['recordId']));record.status='PREPARING';record.destination_type='NONE';record.eligibility_status='QUALIFIED'
        batch=db.get(InternshipBatch,record.batch_id)
        # This synthetic school requires safety education; existing school policies are untouched.
        batch.rules_config={**(batch.rules_config or {}),'compliance':{'safetyEducation':{'required':True}}};db.commit()
    return result

def evidence(student,story):
    workbook=Workbook();workbook.active.append(['Synthetic exemption proof; no genuine admission data'])
    output=BytesIO();workbook.save(output)
    uploaded=ok(student.post('/api/v1/files',params={'bizType':'INTERNSHIP_APPLICATION_EVIDENCE'},files={'file':('exemption-proof.xlsx',output.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}))
    fid=uploaded['fileId']
    if not uploaded['readyForBusiness']:
        assert process_next_scan_job(tenant_id=int(story['tenantId']),file_id=int(fid))
    assert ok(student.get('/api/v1/files/'+fid))['readyForBusiness']
    return fid,output.getvalue()

def payload(story,fid=''):
    return {**context(story),'applicationType':'EXEMPTION','exemptionType':'FURTHER_STUDY','exemptionDestination':'合成升学学校','exemptionReason':'合成录取后申请免实习，非真实录取信息','applicationNote':'合成免实习说明','evidenceFileId':fid}

def saved(student,story):
    fid,content=evidence(student,story)
    draft=ok(student.put(PORTAL+'/applications',json=payload(story,fid)))
    submitted=ok(student.post(PORTAL+'/applications/'+draft['id']+'/submit',json={**context(story),'expectedVersion':draft['version']}))
    return submitted,fid,content

def test_exemption_return_resubmit_approve_same_original_and_cancel_sibling(story):
    with login(story,'STUDENT') as student,login(story) as school:
        sibling=ok(student.put(PORTAL+'/applications',json={**context(story),'applicationType':'SELF_ARRANGED','applicationNote':'待填写自主申请草稿'}))
        app,fid,content=saved(student,story)
        result=ok(school.post(ROOT+'/applications/'+app['id']+'/review',json={'action':'REJECT','comment':'请补充报到日期及后续安排','batchId':story['batchId'],'expectedVersion':app['version']}))
        assert result['id']==app['id'] and result['evidenceFileId']==fid
        assert student.put(PORTAL+'/applications',json={**payload(story,fid),'id':app['id'],'expectedVersion':app['version']}).json()['code']!=0
        corrected=ok(student.put(PORTAL+'/applications',json={**payload(story,fid),'id':app['id'],'expectedVersion':result['version'],'exemptionReason':'按校方意见补充合成报到日期与后续安排'}))
        resubmitted=ok(student.post(PORTAL+'/applications/'+app['id']+'/submit',json={**context(story),'expectedVersion':corrected['version']}))
        record=ok(school.get(ROOT+'/intern-students/'+story['recordId']))
        approved=ok(school.post(ROOT+'/applications/'+app['id']+'/review',json={'action':'APPROVE','batchId':story['batchId'],'expectedVersion':resubmitted['version'],'recordExpectedVersion':record['version']}))
        assert approved['id']==app['id'] and approved['status']=='APPROVED'
        rows=ok(student.get(PORTAL+'/applications',params=context(story)))
        assert next(x for x in rows if x['id']==sibling['id'])['status']=='CANCELLED'
        detail=ok(school.get(ROOT+'/intern-students/'+story['recordId']))
        assert detail['destinationType']=='EXEMPTED' and not detail['positionId']
        assert student.get('/api/v1/files/download/'+fid).content==content
        assert school.get('/api/v1/files/download/'+fid).content==content
        assert student.put(PORTAL+'/applications',json={**payload(story,fid),'id':app['id'],'expectedVersion':approved['version']}).json()['code']!=0
        with get_sessionmaker()() as db:
            trail=db.scalars(select(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id==int(story['tenantId']),InternshipAuditTrail.target_id==int(app['id']))).all()
            assert trail

def test_exemption_missing_evidence_and_field_validation_never_submit(story):
    with login(story,'STUDENT') as student:
        draft=ok(student.put(PORTAL+'/applications',json=payload(story)))
        response=student.post(PORTAL+'/applications/'+draft['id']+'/submit',json={**context(story),'expectedVersion':draft['version']})
        assert response.json()['code']!=0
        rows=ok(student.get(PORTAL+'/applications',params=context(story)));assert rows[0]['status']=='DRAFT' and rows[0]['version']==draft['version']
        for changes in [{'exemptionType':'UNKNOWN'},{'exemptionReason':'x'*501},{'exemptionDestination':'x'*201}]:
            assert student.put(PORTAL+'/applications',json={**payload(story),'id':draft['id'],'expectedVersion':draft['version'],**changes}).json()['code']!=0

def test_exemption_permission_record_version_and_batch_boundaries(story):
    foreign=seed_plan_story()
    with login(story,'STUDENT') as student,login(story) as school,login(story,'OTHER_MENTOR') as unrelated,login(foreign) as outsider:
        app,fid,_=saved(student,story)
        body={'action':'APPROVE','expectedVersion':app['version'],'recordExpectedVersion':99999,'batchId':story['batchId']}
        assert student.post(ROOT+'/applications/'+app['id']+'/review',json=body).status_code==403
        assert unrelated.get(ROOT+'/applications/'+app['id']).json()['code']!=0
        assert unrelated.get('/api/v1/files/download/'+fid).status_code==404
        assert outsider.get(ROOT+'/applications/'+app['id']).json()['code']!=0
        assert outsider.get('/api/v1/files/download/'+fid).status_code==404
        assert school.post(ROOT+'/applications/'+app['id']+'/review',json=body).json()['code']!=0
        assert school.post(ROOT+'/applications/'+app['id']+'/review',json={**body,'batchId':story['batches'][1]['id']}).json()['code']!=0
        assert ok(school.get(ROOT+'/applications/'+app['id']))['status']=='PENDING_REVIEW'
        detail=ok(school.get(ROOT+'/intern-students/'+story['recordId']));assert detail['destinationType']=='NONE'

def test_application_evidence_requires_current_binding_and_actual_membership(story):
    with login(story,'STUDENT') as student,login(story) as school:
        app,fid,_=saved(student,story)
        with get_sessionmaker()() as db:
            binding=db.scalar(select(FileBinding).where(FileBinding.tenant_id==int(story['tenantId']),FileBinding.file_id==int(fid),FileBinding.biz_type=='INTERNSHIP_APPLICATION_EVIDENCE'))
            binding.is_current=False;db.commit()
        for client in [student,school]:assert client.get('/api/v1/files/download/'+fid).status_code==404
        with get_sessionmaker()() as db:
            db.get(FileBinding,binding.id).is_current=True;db.get(InternshipApplication,int(app['id'])).evidence_file_id=None;db.commit()
        for client in [student,school]:assert client.get('/api/v1/files/download/'+fid).status_code==404

def test_onboard_missing_real_compliance_cannot_be_replaced_by_record_labels(story):
    with login(story) as school,login(story,'STUDENT') as student:
        record=ok(school.get(ROOT+'/intern-students/'+story['recordId']))
        updated=ok(school.put(ROOT+'/intern-students/'+story['recordId'],json={'insurance':'文字已投保不代表真实保单','agreement':'文字已签约不代表正式协议','expectedVersion':record['version']}))
        ready=ok(school.post(ROOT+'/intern-students/'+story['recordId']+'/status',json={'action':'READY','expectedVersion':updated['version']}))
        checklist=ok(school.get(ROOT+'/intern-students/'+story['recordId']+'/onboard-checklist'))
        assert not checklist['canOnboard'] and checklist['blockers']
        codes={item['code'] for item in checklist['evaluation']['blockers']}
        assert {'agreement','insurance','safetyEducation'}.issubset(codes)
        assert school.post(ROOT+'/intern-students/'+story['recordId']+'/status',json={'action':'ONBOARD','expectedVersion':ready['version']}).json()['code']!=0
        final=ok(school.get(ROOT+'/intern-students/'+story['recordId']));assert final['status']=='READY' and final['version']==ready['version']
        assert student.post(ROOT+'/intern-students/'+story['recordId']+'/status',json={'action':'ONBOARD','expectedVersion':ready['version']}).status_code==403
