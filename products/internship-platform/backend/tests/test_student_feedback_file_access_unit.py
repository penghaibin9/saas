from types import SimpleNamespace
import pytest
from app.services import file_access_service as access
from app.modules.internship.services import internship_student_feedback_service as feedback
from app.modules.internship.services import internship_complaint_service as complaints
from app.core import permissions


@pytest.fixture
def story(monkeypatch):
    file=SimpleNamespace(id=9,tenant_id=1,is_deleted=False,biz_type='INTERNSHIP_FEEDBACK',biz_id='8',owner_user_id=10,created_by=10,status='AVAILABLE',scan_status='CLEAN')
    binding=SimpleNamespace(tenant_id=1,file_id=9,biz_type='INTERNSHIP_FEEDBACK',biz_id='8',status='ACTIVE',is_current=True,is_deleted=False,subject_type='BUSINESS_OBJECT',subject_id='8',scope_json={},data_scope_snapshot_json={})
    row=SimpleNamespace(id=8,tenant_id=1,is_deleted=False,source='STUDENT',category='STUDENT_FEEDBACK',image_file_ids=['9'],student_id=5,batch_id=3,internship_id=7)
    db=SimpleNamespace(scalar=lambda query:row)
    monkeypatch.setattr(access,'current_tenant_id',lambda:1)
    monkeypatch.setattr(feedback,'_tid',lambda:1)
    monkeypatch.setattr(feedback,'_student_context',lambda db,user,payload,for_write:(SimpleNamespace(id=7),SimpleNamespace(id=user.get('studentId')),3))
    monkeypatch.setattr(permissions,'has_permission',lambda user,code:code in user.get('permissions',[]))
    monkeypatch.setattr(complaints,'_complaint_in_scope',lambda db,row,user:user.get('inScope',False))
    return file,binding,row,db


def test_feedback_staff_needs_real_view_permission_and_original_scope(story):
    file,binding,row,db=story
    staff={'userId':'11','userType':'TEACHER','permissions':['internship.complaint.view'],'inScope':True}
    assert access.authorize_file_object(file,[binding],staff,'download',db)
    for changed in [{'permissions':[]},{'inScope':False}]:
        assert not access.authorize_file_object(file,[binding],{**staff,**changed},'download',db)


@pytest.mark.parametrize('invalid',['revoked','not-current','wrong-object','deleted-feedback','wrong-member','unsafe','foreign-feedback'])
def test_feedback_bound_owner_cannot_bypass_invalid_business_facts(story,invalid):
    file,binding,row,db=story
    if invalid=='revoked':binding.status='REVOKED'
    elif invalid=='not-current':binding.is_current=False
    elif invalid=='wrong-object':binding.biz_id='999'
    elif invalid=='deleted-feedback':row.is_deleted=True
    elif invalid=='wrong-member':row.image_file_ids=['other']
    elif invalid=='unsafe':file.scan_status='INFECTED'
    elif invalid=='foreign-feedback':row.tenant_id=2
    assert not access.authorize_file_object(file,[binding],{'userId':'10','userType':'STUDENT','studentId':5},'meta',db)


def test_feedback_student_requires_current_trusted_profile_not_just_file_owner(story):
    file,binding,row,db=story
    owner={'userId':'10','userType':'STUDENT','studentId':5}
    assert access.authorize_file_object(file,[binding],owner,'download',db)
    assert not access.authorize_file_object(file,[binding],{**owner,'studentId':6},'download',db)
