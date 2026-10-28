"""Non-database behavior checks; MySQL locking and cross-role stories run separately."""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from app.core.exceptions import AppException
from app.models.internship_enterprise_portal import InternshipEnterpriseAccessGrant
from app.modules.internship.routers.internship_enterprise_member_admin import CollaborationGrant, ContactBinding
from app.modules.internship.services import internship_enterprise_member_admin_service as admin
from app.modules.internship.services import internship_enterprise_auth_service as auth
from app.modules.internship.services import internship_service


class Db:
    def __init__(self, values=()):
        self.values=iter(values);self.commits=0;self.added=[]
    def scalar(self, query): return next(self.values)
    def add(self, row): self.added.append(row)
    def commit(self): self.commits+=1
    def flush(self): pass


def member():
    return SimpleNamespace(id=11,company_id=22,contact_id=33,member_role='MENTOR',version=2,
        status='ACTIVE',accepted_at=datetime.utcnow(),user_id=44,is_primary=False,last_active_at=None)


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(admin,'_tid',lambda:7)
    row=member();db=Db()
    monkeypatch.setattr(admin,'session',lambda:nullcontext(db))
    monkeypatch.setattr(admin,'_member',lambda *args,**kwargs:row)
    monkeypatch.setattr(admin.members,'_get_contact',lambda *args,**kwargs:SimpleNamespace(id=55,name='虚构导师',status='ACTIVE',contact_type='MENTOR'))
    monkeypatch.setattr(admin,'audit_insert_in_session',lambda target,*args,**kwargs:target.add('audit'))
    return row,db


def test_schema_requires_exact_ids_explicit_offset_dates_and_versions():
    with pytest.raises(ValidationError): ContactBinding(contactId=123,expectedVersion=1)
    with pytest.raises(ValidationError): ContactBinding(contactId='001',expectedVersion=1)
    with pytest.raises(ValidationError): ContactBinding(contactId='123',expectedVersion=True)
    with pytest.raises(ValidationError): CollaborationGrant(batchId='1',validFrom='2026-10-18T10:00',validUntil='2026-11-18T10:00',expectedMemberVersion=0)
    with pytest.raises(ValidationError): CollaborationGrant(batchId='1',validFrom='2026-10-18T10:00Z',validUntil='2026-11-18T10:00Z',expectedMemberVersion=0,grantType='RECRUITMENT')


def test_school_scope_and_existing_enterprise_permission_are_both_required(monkeypatch):
    monkeypatch.setattr(internship_service,'_current_scope',lambda user:{'mode':'ADMIN_TENANT' if user.get('school') else 'SCOPED'})
    assert admin.require_school_manager({'school':True,'permissions':['internship.enterprise.manage']})
    for user in ({'school':False,'permissions':['internship.enterprise.manage']},{'school':True,'permissions':['internship.enterprise.view']}):
        with pytest.raises(AppException): admin.require_school_manager(user)


def test_contact_binding_rejects_conflict_and_updates_identity_version_with_audit(setup):
    row,db=setup
    with pytest.raises(AppException): admin.bind_contact('22','11','55',1,{})
    assert row.contact_id==33 and db.commits==0
    result=admin.bind_contact('22','11','55',2,{})
    assert result['contactId']=='55' and result['version']==3
    assert db.commits==1 and db.added==['audit']


def test_binding_wrong_contact_type_or_audit_failure_cannot_commit(setup,monkeypatch):
    row,db=setup
    monkeypatch.setattr(admin.members,'_get_contact',lambda *args,**kwargs:SimpleNamespace(id=55,status='ACTIVE',contact_type='CONTACT'))
    with pytest.raises(AppException): admin.bind_contact('22','11','55',2,{})
    assert db.commits==0 and row.contact_id==33
    monkeypatch.setattr(admin.members,'_get_contact',lambda *args,**kwargs:SimpleNamespace(id=55,name='导师',status='ACTIVE',contact_type='MENTOR'))
    def failed(*args,**kwargs): raise RuntimeError('audit unavailable')
    monkeypatch.setattr(admin,'audit_insert_in_session',failed)
    with pytest.raises(RuntimeError): admin.bind_contact('22','11','55',2,{})
    assert db.commits==0


def test_school_cannot_activate_invited_member(setup):
    row,db=setup;row.status='INVITED';row.accepted_at=None
    with pytest.raises(AppException): admin.change_status('22','11','ACTIVE',2,'学校代办',{})
    assert db.commits==0 and row.status=='INVITED'


def test_issue_fixes_scope_preserves_exact_batch_id_and_utc(setup,monkeypatch):
    row,_=setup;db=Db([9,None]);monkeypatch.setattr(admin,'session',lambda:nullcontext(db))
    start=datetime.now(timezone.utc);end=start+timedelta(days=10);calls=[]
    grant=InternshipEnterpriseAccessGrant(id=8,tenant_id=7,member_id=11,company_id=22,grant_type='INTERNSHIP_COLLAB',campaign_id=None,batch_id=9007199254740993,valid_from=start.replace(tzinfo=None),valid_until=end.replace(tzinfo=None),status='ACTIVE',version=0)
    def issue(db,**kwargs): calls.append(kwargs);return grant
    monkeypatch.setattr(admin.access,'issue_grant_in_tx',issue)
    result=admin.issue_collaboration('22','11','9007199254740993',start,end,2,{'userId':'db-1'})
    assert result['batchId']=='9007199254740993'
    assert calls[0]['campaign_id'] is None and calls[0]['grant_type']=='INTERNSHIP_COLLAB'
    assert calls[0]['valid_from'].tzinfo is None
    assert db.commits==1 and db.added==['audit']


def test_issue_existing_history_never_renews_or_revives(setup,monkeypatch):
    _,_=setup;db=Db([9,88]);monkeypatch.setattr(admin,'session',lambda:nullcontext(db))
    start=datetime.now(timezone.utc);end=start+timedelta(days=1)
    with pytest.raises(AppException,match='不会自动续期或恢复'):admin.issue_collaboration('22','11','9',start,end,2,{})
    assert db.commits==0


def test_issue_without_participation_or_binding_fails_before_any_grant(setup,monkeypatch):
    row,_=setup;db=Db([None,None]);monkeypatch.setattr(admin,'session',lambda:nullcontext(db))
    start=datetime.now(timezone.utc);end=start+timedelta(days=1)
    with pytest.raises(AppException):admin.issue_collaboration('22','11','9',start,end,2,{})
    row.contact_id=None
    with pytest.raises(AppException):admin.issue_collaboration('22','11','9',start,end,2,{})
    assert db.commits==0


def test_accepted_company_is_reused_but_revoked_participation_is_not():
    participation=SimpleNamespace(status='ACCEPTED');db=Db([participation])
    campaign=SimpleNamespace(id=1,tenant_id=7);company=SimpleNamespace(id=22)
    assert auth._ensure_campaign_invitation_in_tx(db,campaign=campaign,company=company,invite_source='MANUAL',actor_user_id=1) is participation
    assert not db.added
    participation.status='REVOKED';db=Db([participation])
    with pytest.raises(AppException):auth._ensure_campaign_invitation_in_tx(db,campaign=campaign,company=company,invite_source='MANUAL',actor_user_id=1)
