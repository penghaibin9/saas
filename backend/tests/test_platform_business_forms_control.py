"""School-bound platform form maintenance using normal password login and isolated MySQL."""
import secrets
from uuid import uuid4
import pytest

from sqlalchemy import select

from app.models import User, Role, UserRole, Permission, RolePermission, Tenant, SecurityAuditLog
from app.core.tenant_identity import PLATFORM
from app.modules.platform.business_forms.models import BusinessFormDefinition, BusinessFormVersion

TENANT = 1000000000000000001
OTHER = 1000000000000000909
ROOT = f"/api/v1/platform/tenants/{TENANT}"


def _platform(client, codes):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    nonce = uuid4().hex[:12]
    password = secrets.token_urlsafe(24)
    with get_sessionmaker()() as db:
        if db.get(Tenant, PLATFORM.tenant_id) is None:
            db.add(Tenant(id=PLATFORM.tenant_id, tenant_code=PLATFORM.tenant_code, school_name="独立平台验证域", status="ACTIVE"))
        role = Role(tenant_id=PLATFORM.tenant_id, role_code=f"PLATFORM_FORM_{nonce.upper()}", role_name="独立表单验证职责", role_type="CUSTOM", status="ACTIVE")
        user = User(tenant_id=PLATFORM.tenant_id, login_name=f"form_{nonce}", real_name="独立表单验证员", user_type="PLATFORM_OP", password_hash=hash_password(password), status="ACTIVE")
        db.add_all([role, user]); db.flush()
        for code in codes:
            perm = db.scalar(select(Permission).where(Permission.permission_code == code))
            if perm is None:
                perm = Permission(permission_code=code, permission_name="表单验证权限", module_code="PLATFORM")
                db.add(perm); db.flush()
            db.add(RolePermission(tenant_id=PLATFORM.tenant_id, role_id=role.id, permission_id=perm.id, status="ACTIVE"))
        db.add(UserRole(tenant_id=PLATFORM.tenant_id, user_id=user.id, role_id=role.id, status="ACTIVE"))
        login_name = user.login_name
        db.commit()
    challenge = client.post('/api/v1/auth/captcha', json={"scene":"PLATFORM_LOGIN", "loginName":login_name,
                            "tenantCode":PLATFORM.tenant_code, "clientNonce":nonce, "clientType":"PLATFORM_PC"})
    assert challenge.status_code == 200
    captcha = challenge.json()['data']
    response = client.post('/api/v1/auth/login', json={"loginName": login_name, "password": password,
        "tenantCode":PLATFORM.tenant_code, "clientType": "PLATFORM_PC", "clientNonce":nonce, "captchaId":captcha['captchaId'], "captchaCode":captcha['devCode']})
    assert response.status_code == 200, response.json().get('message')
    return {"Authorization": "Bearer " + response.json()["data"]["accessToken"]}


def test_normal_platform_editor_is_school_bound_and_readonly_role_cannot_write(client, db_mode):
    from app.db.session import get_sessionmaker
    from system_admin_test_auth import school_admin_headers
    with get_sessionmaker()() as db:
        db.add(Tenant(id=OTHER, tenant_code="form-other-school", school_name="另一个独立学校")); db.commit()
    editor = _platform(client, ['platform.businessForms.view', 'platform.businessForms.manage'])
    viewer = _platform(client, ['platform.businessForms.view'])
    school = school_admin_headers(client)
    assert client.get(ROOT+'/business-forms', headers=school).status_code == 403
    context = client.get('/api/v1/platform/context', headers=editor).json()['data']
    assert 'businessForms.view' in context['duties'] and 'businessForms.manage' in context['duties']
    assert '*' not in context['duties']
    body = {'formCode':'D609_TEST','formName':'独立验证表单','domainCode':'INTERNSHIP','reason':'独立范围验证创建'}
    assert client.post(ROOT+'/business-forms', headers=viewer, json=body).status_code == 403
    response = client.post(ROOT+'/business-forms', headers=editor, json=body)
    assert response.status_code == 200, response.text
    definition = response.json()['data']
    draft = client.post(ROOT+f"/business-forms/{definition['id']}/versions", headers=editor, json={
        'supportedClients':['STAFF_PC'],'domainDataAdapter':'INTERNSHIP_SPECIAL_FILING_INITIAL',
        'domainCommandAdapter':'INTERNSHIP_SPECIAL_FILING','fields':[{'code':'triggerReason','type':'textarea','label':'说明','required':True}],
        'reason':'独立版本创建验证',
    })
    assert draft.status_code == 200, draft.text
    version = draft.json()['data']; vid = version['versionId']
    history = client.get(ROOT+f"/business-forms/{definition['id']}/versions?pageSize=1", headers=viewer).json()['data']
    assert history['total'] == 1 and history['items'][0]['versionId'] == vid
    assert client.get(f'/api/v1/platform/tenants/{PLATFORM.tenant_id}/business-forms', headers=editor).status_code == 404
    assert client.get(f'/api/v1/platform/tenants/{OTHER}/business-form-versions/{vid}', headers=editor).status_code == 404
    assert client.get(ROOT+f'/business-form-versions/{vid}', headers=viewer).status_code == 200
    lifecycle = {'expectedVersion':version['version'],'reason':'独立发布范围验证'}
    assert client.post(ROOT+f'/business-form-versions/{vid}/publish', headers=viewer, json=lifecycle).status_code == 403
    published = client.post(ROOT+f'/business-form-versions/{vid}/publish', headers=editor, json=lifecycle)
    assert published.status_code == 200, published.text
    assert client.post(ROOT+f'/business-form-versions/{vid}/publish', headers=editor, json=lifecycle).status_code == 409
    disabled = client.post(ROOT+f'/business-form-versions/{vid}/disable', headers=editor, json={
        'expectedVersion':published.json()['data']['version'],'reason':'独立停用范围验证'})
    assert disabled.status_code == 200, disabled.text
    with get_sessionmaker()() as db:
        assert db.get(BusinessFormVersion, int(vid)).status == 'DISABLED'
        events = db.scalars(select(SecurityAuditLog).where(SecurityAuditLog.tenant_id == 0, SecurityAuditLog.action.like('PLATFORM_FORM_%'))).all()
        assert len(events) == 4
        assert all(x.detail_json['targetTenantId'] == str(TENANT) for x in events)


def test_platform_form_mutation_rolls_back_when_atomic_audit_fails(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.modules.platform.routers import business_forms_control as api
    editor = _platform(client, ['platform.businessForms.manage'])
    def failed(*args, **kwargs):
        raise RuntimeError('isolated audit failure')
    monkeypatch.setattr(api, 'audit_insert_in_session', failed)
    try:
        response = client.post(ROOT+'/business-forms', headers=editor, json={
            'formCode':'D609_ROLLBACK','formName':'审计失败验证','domainCode':'INTERNSHIP','reason':'独立原子性验证'})
    except RuntimeError as error:
        assert str(error) == 'isolated audit failure'
    else:
        assert response.status_code >= 500
    with get_sessionmaker()() as db:
        assert db.scalar(select(BusinessFormDefinition).where(BusinessFormDefinition.form_code == 'D609_ROLLBACK')) is None


def test_form_permissions_are_explicit_platform_capabilities_not_new_default_grants():
    from app.services.platform_access_governance_service import KNOWN_CAPABILITIES, DUTY_CAPABILITIES
    from app.core.permission_catalog import permission_meta, assert_custom_role_assignable
    from app.core.exceptions import AppException
    for capability in ['businessForms.view', 'businessForms.manage']:
        assert capability in KNOWN_CAPABILITIES
        assert all(capability not in grants for grants in DUTY_CAPABILITIES.values())
        code = 'platform.' + capability
        assert permission_meta(code)['plane'] == 'PLATFORM'
        with pytest.raises(AppException):
            assert_custom_role_assignable([code])


@pytest.mark.parametrize('kind', ['definition', 'draft'])
def test_duplicate_schema_or_definition_is_a_conflict_and_rolls_back(monkeypatch, kind):
    from types import SimpleNamespace
    from sqlalchemy.exc import IntegrityError
    from app.core.exceptions import AppException
    from app.modules.platform.routers import business_forms_control as api
    rolled_back = []
    def duplicate(*args, **kwargs):
        raise IntegrityError('isolated duplicate', {}, RuntimeError('duplicate'))
    monkeypatch.setattr(api, '_service', lambda *args: SimpleNamespace(create_definition=duplicate, create_draft_version=duplicate))
    db = SimpleNamespace(rollback=lambda: rolled_back.append(True))
    with pytest.raises(AppException) as caught:
        if kind == 'definition':
            api.create_definition(api.CreateDefinition(formCode='DUP',formName='重复定义',domainCode='INTERNSHIP',reason='独立重复验证'), tenant_id=TENANT,user={},db=db)
        else:
            api.create_draft(api.CreateDraft(supportedClients=['STAFF_PC'],domainDataAdapter='INTERNSHIP_SPECIAL_FILING_INITIAL',domainCommandAdapter='INTERNSHIP_SPECIAL_FILING',fields=[],reason='独立重复验证'),tenant_id=TENANT,definition_id=1,user={},db=db)
    assert caught.value.code == 'DATA_CONFLICT' and caught.value.http_status == 409
    assert rolled_back == [True]


def test_source_catalog_reports_registered_capabilities_not_student_assessment(monkeypatch):
    from app.modules.platform.routers import business_forms_control as api
    monkeypatch.setattr(api, '_school', lambda db, tenant_id: None)
    result = api.sources(tenant_id=TENANT, user={}, db=None)['data']
    assert result['scope'] == 'REGISTERED_CAPABILITIES_ONLY'
    assert len(result['items']) == 4 and all(row['registered'] for row in result['items'])
    evidence = [row for row in result['items'] if row['mode'] == 'EVIDENCE_ONLY']
    assert {row['domain'] for row in evidence} == {'ACADEMIC','STUDENT_AFFAIRS'}
    assert all(row['operationCodes'] == [] for row in evidence)
