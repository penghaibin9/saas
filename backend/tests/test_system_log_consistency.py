"""D6-02: displayed audit outcomes, identity and local-day queries match real facts."""
from datetime import datetime
from types import SimpleNamespace
import uuid

import pytest

from app.modules.system_admin.routers import system_bundle as logs
from test_security_wx_binding_approval_mysql import school_account


def row(**values):
    defaults = dict(id=1, action='USER_UPDATE', result='SUCCESS', detail_json={},
        created_at=datetime(2026, 10, 25, 8, 58), operator_id=None, operator_name=None,
        current_role=None, resource='user:1', request_path='/api/v1/system/users/1',
        request_method='PUT', trace_id='trace-test', data_scope=None, ip='127.0.0.1', user_agent='test')
    return SimpleNamespace(**(defaults | values))


def test_audit_time_keeps_utc_offset_for_display_and_unknown_is_not_success():
    assert logs._operation_log_row(row())['time'] == '2026-10-25T08:58:00Z'
    unknown = logs._operation_log_row(row(result='UNRECOGNIZED'))
    assert unknown['result'] == 'UNKNOWN'
    assert unknown['resultLabel'] == '结果未确认'
    assert unknown['timeZone']=='Asia/Shanghai'
    assert logs._export_local_time(datetime(2026,10,25,8,58)) == '2026-10-25 16:58:00'


def test_legacy_denial_disagrees_with_raw_success_without_rewriting_history():
    value = row(action='PERMISSION_DENIED', result='SUCCESS')
    projected = logs._operation_log_row(value)
    assert projected['result'] == 'DENIED'
    assert projected['detail']['recordedResult'] == 'SUCCESS'
    assert '不一致' in projected['detail']['resultNote']
    assert value.result == 'SUCCESS'


def test_login_events_remain_distinguishable():
    projected = logs._login_log_row(row(action='TOKEN_REFRESH'), {})
    assert projected['eventLabel'] == '会话刷新'
    assert projected['userNo'] == ''
    assert projected['time'].endswith('Z')
    browser=logs._login_log_row(row(user_agent='Mozilla/5.0 Chrome/156'),{})
    assert browser['device']=='电脑浏览器'
    assert browser['deviceDetail']=='Mozilla/5.0 Chrome/156'


def test_new_audit_writes_honor_event_and_http_result(monkeypatch):
    from app.services import operation_audit_service as audit, db_service
    from app.db import session as db_session
    captured=[]
    monkeypatch.setattr(audit,'_resolved_tenant_id',lambda _target:1000000000000000001)
    monkeypatch.setattr(db_session,'db_enabled',lambda:True)
    monkeypatch.setattr(db_service,'audit_insert',lambda action,resource,detail,result,**kwargs:captured.append(result))
    audit.record('PERMISSION_DENIED',status_code=403)
    audit.record('RATE_LIMITED')
    audit.record('D6_FAILED',status_code=500)
    assert captured == ['DENIED','BLOCKED','FAIL']


def test_evidence_uses_existing_critical_registry_and_declares_sample_scope(monkeypatch):
    from app.services import audit_evidence_service as evidence, db_service
    value={'auditId':'fixture','action':'ROLE_PERMISSION_SAVE','actorId':1,'tenantId':'1',
           'resource':'role:1','requestId':'-','detail':{'reason':'核对已有权限'},'result':'SUCCESS'}
    assert evidence.is_high_risk_action(value['action'])
    assert 'traceId' in evidence.evaluate_evidence_completeness([value])['gaps'][0]['missing']
    monkeypatch.setattr(db_service,'audit_query',lambda *_args:([value],1000))
    overview=evidence.governance_overview()
    assert overview['sampledCount']==1 and overview['totalRecent']==1000
    assert overview['highRiskChangeCount']==1 and overview['auditGapCount']==1


def test_log_and_evidence_share_action_target_and_unknown_labels():
    from app.services.operation_audit_service import present_result, present_target
    value=row(action='TOKEN_REFRESH', resource='auth')
    projected=logs._operation_log_row(value)
    assert projected['actionLabel']==present_result(value.action,value.result)['actionLabel']=='会话刷新'
    assert projected['targetLabel']==present_target(value.resource)=='登录账号'
    assert present_target('role:4')=='角色配置'
    assert present_result('UNKNOWN_HISTORY','SUCCESS')['actionLabel']=='未识别的历史操作'
    assert present_target('UNKNOWN_HISTORY')=='未识别的历史对象'
    assert present_target('attempted-account','LOGIN_FAIL')=='登录尝试（身份未确认）'


def test_mysql_queries_filter_before_pagination_and_keep_tenant_scope(db_mode):
    from sqlalchemy import select
    from app.core.context import set_tenant
    from app.core.exceptions import AppException
    from app.models import SecurityAuditLog, User
    from app.services.db_service import session
    tid = 1000000000000000001
    set_tenant({'tenantId': tid})
    with session() as db:
        foreign = User(tenant_id=tid+1, login_name='FOREIGN-DO-NOT-LEAK', real_name='其他学校', password_hash='fixture', user_type='ADMIN')
        db.add(foreign); db.flush()
        for domain, path in [('studentAffairs','student-affairs'), ('academicAffairs','academic-affairs'), ('graduationDesign','graduation'), ('internship','internship')]:
            db.add(SecurityAuditLog(tenant_id=tid, action='D6_QUERY', result='SUCCESS',
                resource='D6-'+domain, request_path='/api/v1/'+path+'/items', created_at=datetime(2026,10,24,16)))
        db.add(SecurityAuditLog(tenant_id=tid, action='D6_QUERY', result='SUCCESS',resource='D6-excluded-day',
            request_path='/api/v1/academic-affairs/items', created_at=datetime(2026,10,24,15,59,59)))
        db.add(SecurityAuditLog(tenant_id=tid+1, action='D6_QUERY', result='SUCCESS',resource='D6-other-tenant', created_at=datetime(2026,10,24,16)))
        # Newer unrelated rows used to hide the matching older row behind an in-memory page cutoff.
        db.add_all([SecurityAuditLog(tenant_id=tid,action='D6_QUERY',result='SUCCESS',resource='D6-system',
            request_path='/api/v1/system/users',created_at=datetime(2026,10,25,1)) for _ in range(250)])
        db.add(SecurityAuditLog(tenant_id=tid, action='LOGIN', result='SUCCESS', resource='D6-malformed-actor',operator_id=foreign.id))
        db.add(SecurityAuditLog(tenant_id=tid, action='PERMISSION_DENIED', result='SUCCESS',resource='D6-old-denial'))
        db.add_all([SecurityAuditLog(tenant_id=tid,action=code,result='SUCCESS',resource='alias-fixture') for code in ('CONFIG','CONFIG_CHANGE')])
        db.commit()
    for domain in ('studentAffairs','academicAffairs','graduationDesign','internship'):
        page = logs._audit_page(False, 'D6-', '', '', domain, 1, 10, '2026-10-25','2026-10-25')
        assert page['total'] == 1
        assert page['list'][0]['module'] == domain
        assert page['list'][0]['time'] == '2026-10-24T16:00:00Z'
    denied = logs._audit_page(False, 'D6-old-denial', 'DENIED', '', '',1,10)
    assert denied['total'] == 1 and denied['list'][0]['result'] == 'DENIED'
    assert logs._audit_page(False,'alias-fixture','','CONFIG_CHANGE','',1,10)['total']==2
    from app.services import db_service
    evidence, _ = db_service.audit_query(1, 10, action='PERMISSION_DENIED')
    assert evidence[0]['result'] == 'DENIED' and evidence[0]['recordedResult'] == 'SUCCESS'
    malformed = logs._audit_page(True,'D6-malformed-actor','','','',1,10)
    assert malformed['list'][0]['userNo'] == ''
    with pytest.raises(AppException):
        logs._audit_page(False,'','','','',1,10,'not-a-date','')


def test_real_browser_login_records_actor_and_last_login_but_role_switch_does_not(db_mode, client):
    from sqlalchemy import select
    from app.core.security import hash_password
    from app.models import User, Role, UserRole, SecurityAuditLog
    from app.services.db_service import session
    tid = 1000000000000000001
    with session() as db:
        actor = User(tenant_id=tid, login_name='d602_login', real_name='审计验收经办人', password_hash=hash_password('Test@D6022026'),user_type='ADMIN',status='ACTIVE')
        role = Role(tenant_id=tid,role_code='SCHOOL_ADMIN',role_name='学校管理员',role_type='SYSTEM',status='ACTIVE')
        db.add_all([actor,role]); db.flush()
        db.add(UserRole(tenant_id=tid,user_id=actor.id,role_id=role.id,status='ACTIVE'))
        limited=Role(tenant_id=tid,role_code='SYS_ADMIN',role_name='系统管理员',role_type='SYSTEM',status='ACTIVE')
        db.add(limited); db.flush()
        db.add(UserRole(tenant_id=tid,user_id=actor.id,role_id=limited.id,status='ACTIVE'))
        actor_id=actor.id
        db.commit()
    tab = str(uuid.uuid4())
    response=client.post('/api/v1/auth/browser-login',json={'tenantCode':'demo','loginName':'d602_login','password':'Test@D6022026','clientType':'PC'},headers={'X-Browser-Session-Id':tab})
    assert response.status_code == 200, response.text
    result=response.json()['data']
    with session() as db:
        actor=db.get(User,actor_id)
        last_login=actor.last_login_at
        assert last_login is not None
        entries=db.scalars(select(SecurityAuditLog).where(SecurityAuditLog.tenant_id==tid,SecurityAuditLog.action=='登录')).all()
        assert len(entries)==1
        event=entries[0]
        assert (event.operator_id,event.operator_name,event.current_role)==(actor_id,'审计验收经办人','SCHOOL_ADMIN')
        assert event.trace_id and event.created_at == last_login
    refreshed=client.post('/api/v1/auth/browser-refresh',headers={'X-Browser-Session-Id':tab,'X-Browser-Session':'staff'})
    assert refreshed.status_code==200, refreshed.text
    result['accessToken']=refreshed.json()['data']['accessToken']
    with session() as db:
        assert db.get(User,actor_id).last_login_at==last_login
        refresh_event=db.scalar(select(SecurityAuditLog).where(SecurityAuditLog.tenant_id==tid,SecurityAuditLog.action=='TOKEN_REFRESH').order_by(SecurityAuditLog.id.desc()))
        assert refresh_event.operator_id==actor_id and refresh_event.current_role=='SCHOOL_ADMIN'
    # Switching an existing role is a session operation, not another password login.
    context=next(item['contextId'] for item in result['contexts'] if item['roleCode']=='SYS_ADMIN')
    switched=client.post('/api/v1/auth/switch-role',json={'contextId':context,'clientType':'PC'},headers={'Authorization':'Bearer '+result['accessToken']})
    assert switched.status_code==200
    with session() as db:
        assert db.get(User,actor_id).last_login_at==last_login
        assert len(db.scalars(select(SecurityAuditLog).where(SecurityAuditLog.tenant_id==tid,SecurityAuditLog.action=='登录')).all())==1
    token=switched.json()['data']['accessToken']
    account=client.get('/api/v1/system/users/'+str(actor_id),headers={'Authorization':'Bearer '+token}).json()['data']
    assert account['lastLoginAt'].endswith('Z')
    assert account['loginHistory'][0]['userName']=='审计验收经办人'
    denied=client.get('/api/v1/academic-affairs/teaching-tasks',headers={'Authorization':'Bearer '+token})
    assert denied.status_code==403, denied.text
    with session() as db:
        event=db.scalar(select(SecurityAuditLog).where(SecurityAuditLog.tenant_id==tid,SecurityAuditLog.action=='PERMISSION_DENIED').order_by(SecurityAuditLog.id.desc()))
        assert event.result=='DENIED'
    failed=client.post('/api/v1/auth/login',json={'tenantCode':'demo','loginName':'d602_login','password':'wrong-password'})
    assert failed.status_code==401
    with session() as db:
        assert db.get(User,actor_id).last_login_at==last_login


def test_authenticated_wechat_event_keeps_subject_identity(client, school_account, monkeypatch):
    from sqlalchemy import select
    from app.models import SecurityAuditLog, User
    from app.db.session import get_sessionmaker
    from app.services import wx_auth_service
    from test_security_wx_binding_approval_mysql import _strict, _issue, _wx_token, UID, TID, OPENID, PASSWORD
    _strict(monkeypatch)
    ticket=_issue()
    bound=client.post('/api/v1/auth/wx-bind',json={'wxToken':_wx_token(),'loginName':'pr265-binding-student',
        'password':PASSWORD,'tenantCode':'demo','clientType':'STUDENT_MINI','bindingApprovalToken':ticket['bindingApprovalToken']})
    assert bound.status_code==200, bound.text
    monkeypatch.setattr(wx_auth_service,'code2session',lambda _code:OPENID)
    signed_in=client.post('/api/v1/auth/wx-login',json={'code':'local-verified-wechat-fixture','clientType':'STUDENT_MINI'})
    assert signed_in.status_code==200, signed_in.text
    with get_sessionmaker()() as db:
        record=db.scalar(select(SecurityAuditLog).where(SecurityAuditLog.tenant_id==TID,SecurityAuditLog.action=='微信登录').order_by(SecurityAuditLog.id.desc()))
        assert (record.operator_id,record.operator_name,record.current_role)==(UID,'绑定验收账号','STUDENT')
        assert record.created_at==db.get(User,UID).last_login_at and record.trace_id
