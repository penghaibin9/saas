from datetime import datetime,timedelta
import pytest
from sqlalchemy import select
from app.core.exceptions import AppException

def test_delegation_duplicate_revoke_and_audit_rollback(db_mode,monkeypatch):
    from app.core.context import set_tenant,set_current_user
    from app.db.session import get_sessionmaker
    from app.models import User,SecurityAuditLog
    from app.services import system_governance_service as gov, system_governance_authority_service as authority, db_service
    from app.services.school_iam_authority_service import converge_school_iam_authority
    converge_school_iam_authority(source='D605_TEST',source_commit_sha='d605-isolated-test')
    tid=1000000000000000001
    actor={'userId':'db-900001','tenantId':str(tid),'currentRoleCode':'SCHOOL_ADMIN','realName':'临时授权验收管理员'}
    set_tenant({'tenantId':tid});set_current_user(actor)
    with get_sessionmaker()() as db:
        db.add(User(tenant_id=tid,login_name='d605-recipient',real_name='虚构受权人',password_hash='fixture',user_type='TEACHER',status='ACTIVE'))
        db.add(User(tenant_id=tid,login_name='d605-student',real_name='虚构学生',password_hash='fixture',user_type='STUDENT',status='ACTIVE'))
        db.add(User(tenant_id=tid+1,login_name='d605-foreign',real_name='虚构外校人员',password_hash='fixture',user_type='TEACHER',status='ACTIVE'))
        db.commit()
    body={'granteeUserNo':'d605-recipient','roleCode':'ACADEMIC_TEACHER','reason':'独立临时职责验收',
          'expiresAt':(datetime.now()+timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')}
    original=db_service.audit_insert_in_session
    attempts=[]
    def fail(*args,**kwargs):
        attempts.append(True)
        raise RuntimeError('isolated audit failure')
    monkeypatch.setattr(db_service,'audit_insert_in_session',fail)
    with pytest.raises(AppException): authority.create_delegation(actor,body)
    assert attempts==[True]
    assert gov.list_delegations()==[]
    monkeypatch.setattr(db_service,'audit_insert_in_session',original)
    created=authority.create_delegation(actor,body)
    for changes in ({'granteeUserNo':'d605-student'}, {'granteeUserNo':'d605-foreign'},
                    {'expiresAt':'2099-99-99 99:99:99'}, {'expiresAt':'2000-01-01 00:00:00'}):
        with pytest.raises(AppException): authority.create_delegation(actor,{**body,**changes})
    with pytest.raises(AppException) as duplicate: authority.create_delegation(actor,body)
    assert duplicate.value.code=='DATA_CONFLICT'
    revoked=gov.revoke_delegation(actor,created['id'],'测试职责已经结束')
    assert revoked['status']=='REVOKED'
    with pytest.raises(AppException): gov.revoke_delegation(actor,created['id'],'重复回收必须被拒绝')
    with get_sessionmaker()() as db:
        events=db.scalars(select(SecurityAuditLog).where(SecurityAuditLog.tenant_id==tid,
            SecurityAuditLog.action.in_(['DELEGATION_CREATE','DELEGATION_REVOKE']))).all()
        assert sorted(event.action for event in events)==['DELEGATION_CREATE','DELEGATION_REVOKE']

def test_revoked_formal_assignment_cannot_be_reviewed(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models.role_assignment import RoleAssignmentValidity
    from app.services.role_assignment_service import review_assignment
    tid=1000000000000000001
    set_tenant({'tenantId':tid})
    with get_sessionmaker()() as db:
        row=RoleAssignmentValidity(tenant_id=tid,user_role_id=99001,user_id=99001,role_code='ACADEMIC_TEACHER',
            effective_at=datetime.now(),status='REVOKED',source_type='MANUAL')
        db.add(row);db.commit();identifier=row.id
    with pytest.raises(AppException): review_assignment(identifier,term='2026-1',reason='失效记录不得再办理')
    with get_sessionmaker()() as db:
        row=db.get(RoleAssignmentValidity,identifier)
        assert row.last_reviewed_at is None and row.status=='REVOKED'
