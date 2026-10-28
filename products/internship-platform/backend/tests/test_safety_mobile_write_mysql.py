"""Normal-student safety writes must reach the authoritative service on real MySQL."""
import os
import pytest
from test_plan_allocation_story_mysql import seed_plan_story,login,ok,ROOT

MOBILE='/api/v1/mobile/internship/safety'

@pytest.fixture
def story():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE')!='1':pytest.skip('isolated MySQL opt-in required')
    return seed_plan_story()

def course(school,story,**changes):
    return ok(school.post(ROOT+'/compliance/safety',json={'batchId':story['batchId'],'title':'虚构安全学习','courseVersion':'联调第一版','contentSnapshot':'虚构课程：识别岗位风险，停止危险操作，报告导师并等待恢复确认。','requiredMinutes':1,'passingScore':80,'maxAttempts':3,'requireCommitment':True,**changes}))

def test_mobile_safety_routes_keep_identity_hash_time_and_version_authority(story):
    with login(story) as school,login(story,'STUDENT') as student,login(story,'INTERN_MENTOR') as teacher:
        created=course(school,story)
        cid=created['id'];started=ok(student.post(MOBILE+'/courses/'+cid+'/start'))
        assert started['status']=='IN_PROGRESS' and started['startedAt'] and started['studiedMinutes']==0
        assert started['startedAt'].endswith('+00:00')
        assert ok(student.post(MOBILE+'/courses/'+cid+'/start'))['id']==started['id']
        detail=ok(student.get(MOBILE+'/courses/'+cid+'/detail'))
        body={'expectedVersion':started['version'],'contentHash':detail['contentHash'],'deviceDigest':'synthetic-local-device'}
        assert student.post(MOBILE+'/completions/'+started['id']+'/commit',json={**body,'contentHash':'wrong'}).json()['code']!=0
        committed=ok(student.post(MOBILE+'/completions/'+started['id']+'/commit',json=body))
        assert committed['commitmentConfirmed'] and committed['version']>started['version']
        submitted=student.post(MOBILE+'/courses/'+cid+'/submit',json={'expectedVersion':committed['version'],'studiedMinutes':99999,'answers':[]})
        assert submitted.json()['code']!=0
        reread=ok(student.get(MOBILE+'/courses/'+cid+'/detail'))['completion']
        assert reread['status']=='IN_PROGRESS' and reread['version']==committed['version']
        for path,body in [('/courses/'+cid+'/start',{}),('/courses/'+cid+'/submit',{}),('/completions/'+started['id']+'/commit',body)]:
            assert teacher.post(MOBILE+path,json=body).status_code==403

def test_safety_mobile_can_submit_with_configured_zero_without_claiming_time(story):
    with login(story) as school,login(story,'STUDENT') as student:
        created=course(school,story,requiredMinutes=0)
        cid=created['id'];started=ok(student.post(MOBILE+'/courses/'+cid+'/start'));detail=ok(student.get(MOBILE+'/courses/'+cid+'/detail'))
        committed=ok(student.post(MOBILE+'/completions/'+started['id']+'/commit',json={'expectedVersion':started['version'],'contentHash':detail['contentHash'],'deviceDigest':'synthetic-device'}))
        submitted=ok(student.post(MOBILE+'/courses/'+cid+'/submit',json={'expectedVersion':committed['version'],'studiedMinutes':0,'answers':[]}))
        assert submitted['id']==started['id'] and submitted['status']=='PENDING_REVIEW' and submitted['studiedMinutes']==0
        assert student.post(MOBILE+'/courses/'+cid+'/submit',json={'expectedVersion':committed['version'],'studiedMinutes':0}).json()['code']!=0

def test_safety_mobile_foreign_school_and_unrelated_batch_have_no_write_access(story):
    other=seed_plan_story()
    with login(other) as school,login(story,'STUDENT') as student,login(story) as own_school:
        foreign=course(school,other);other_batch=course(own_school,story,batchId=story['batches'][1]['id'])
        for item in [foreign,other_batch]:
            assert student.post(MOBILE+'/courses/'+item['id']+'/start').status_code==404
            assert student.post(MOBILE+'/courses/'+item['id']+'/submit',json={'expectedVersion':0,'studiedMinutes':99999}).status_code==404

def test_school_confirmation_command_is_registered_only_for_school_identity(story):
    code='internship.agreement.schoolConfirm'
    with login(story) as school,login(story,'INTERN_MENTOR') as teacher,login(story,'STUDENT') as student:
        assert code in ok(school.get('/api/v1/rbac/current-context'))['permissionPatterns']
        assert code not in ok(teacher.get('/api/v1/rbac/current-context'))['permissionPatterns']
        path=ROOT+'/agreements/9223372036854775800/school-confirm'
        assert teacher.post(path,json={'expectedVersion':0}).status_code==403
        assert student.post(path,json={'expectedVersion':0}).status_code==403
        assert school.post(path,json={'expectedVersion':0}).status_code==404
