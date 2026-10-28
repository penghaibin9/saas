from types import SimpleNamespace
import pytest
from app.services import file_access_service as access
from app.modules.internship.services import internship_makeup_service as makeup
from app.modules.internship.services import internship_service as internship
from app.modules.internship.services import internship_student_context_guard as context
from app.core import permissions


@pytest.fixture
def story(monkeypatch):
    file=SimpleNamespace(id=9,tenant_id=1,is_deleted=False,biz_type='INTERNSHIP_MAKEUP',biz_id='8',owner_user_id=10,created_by=10,status='AVAILABLE',scan_status='CLEAN')
    binding=SimpleNamespace(tenant_id=1,file_id=9,biz_type='INTERNSHIP_MAKEUP',biz_id='8',status='ACTIVE',is_current=True,is_deleted=False,subject_type='STUDENT',subject_id='5',student_id=5,batch_id='3',scope_json={'internshipId':'7','batchId':'3','studentId':'5'},data_scope_snapshot_json={})
    row=SimpleNamespace(id=8,tenant_id=1,is_deleted=False,internship_id=7,student_id=5,evidence_id='9')
    record=SimpleNamespace(id=7,tenant_id=1,is_deleted=False,student_id=5,batch_id=3)
    student=SimpleNamespace(id=5,tenant_id=1,is_deleted=False)
    db=SimpleNamespace(scalar=lambda query:row)
    monkeypatch.setattr(access,'current_tenant_id',lambda:1);monkeypatch.setattr(makeup,'_tid',lambda:1)
    monkeypatch.setattr(makeup,'_evidence_file_id',lambda db,row:row.evidence_id)
    monkeypatch.setattr(makeup,'tenant_get',lambda db,model,id:record if model.__name__=='InternshipRecord' else student)
    monkeypatch.setattr(context,'require_explicit_context',lambda db,user,payload,for_write:(record,SimpleNamespace(id=user.get('studentId')),3))
    monkeypatch.setattr(permissions,'has_permission',lambda user,code:code in user.get('permissions',[]))
    monkeypatch.setattr(internship,'_current_scope',lambda user:user)
    monkeypatch.setattr(internship,'_rec_in_scope',lambda scope,db,record,student:scope.get('inScope',False))
    return file,binding,row,record,db


def test_makeup_original_staff_view_scope_can_read_but_review_alone_cannot(story):
    file,binding,row,record,db=story
    staff={'userId':'11','userType':'TEACHER','permissions':['internship.makeup.view'],'inScope':True}
    assert access.authorize_file_object(file,[binding],staff,'download',db)
    assert not access.authorize_file_object(file,[binding],{**staff,'inScope':False},'download',db)
    assert not access.authorize_file_object(file,[binding],{**staff,'permissions':['internship.makeup.review']},'download',db)


@pytest.mark.parametrize('invalid',['member','binding','scope','student','deleted','scan','tenant'])
def test_makeup_owner_cannot_bypass_business_or_binding_failure(story,invalid):
    file,binding,row,record,db=story
    user={'userId':'10','userType':'STUDENT','studentId':5}
    if invalid=='member':row.evidence_id='other'
    elif invalid=='binding':binding.status='REVOKED'
    elif invalid=='scope':binding.scope_json['internshipId']='other'
    elif invalid=='student':user['studentId']=6
    elif invalid=='deleted':row.is_deleted=True
    elif invalid=='scan':file.scan_status='INFECTED'
    elif invalid=='tenant':row.tenant_id=2
    assert not access.authorize_file_object(file,[binding],user,'meta',db)


def test_non_makeup_generic_file_keeps_original_owner_rule(story):
    file,binding,row,record,db=story
    file.biz_type='INTERNSHIP';file.biz_id=''
    assert access.authorize_file_object(file,[],{'userId':'10','userType':'STUDENT'},'download',db)
