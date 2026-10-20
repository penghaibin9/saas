"""Phone administration contracts on the existing permission/config authorities."""
import pytest
from sqlalchemy import select
from tests.test_phone_login_mysql import phone_db, phone_identity


def test_phone_actions_are_explicit_school_catalog_permissions():
    from app.core.permission_catalog import permission_meta
    for suffix in ('view', 'lookup', 'candidate.manage', 'remind', 'revoke', 'export',
                   'recovery.request', 'recovery.approve', 'policy.view', 'policy.manage'):
        item = permission_meta('systemAdmin.phoneBinding.' + suffix)
        assert item and item['plane'] == 'TENANT' and item['tenantAssignable']


def test_phone_login_consumes_existing_effective_override_not_only_legacy(phone_identity):
    from datetime import datetime, timedelta
    from app.db.session import get_sessionmaker
    from app.models.config_governance import ConfigOverride
    from app.services.phone_login_service import phone_login_enabled
    with get_sessionmaker()() as db:
        assert phone_login_enabled(db, phone_identity['tenant_id'])
        db.add(ConfigOverride(tenant_id=phone_identity['tenant_id'], config_key='SEC_PHONE_LOGIN_ENABLED',
            scope_type='TENANT', scope_id='', value_json={'value': 0},
            effective_at=datetime.now() - timedelta(days=1), status='ACTIVE'))
        db.commit()
        assert not phone_login_enabled(db, phone_identity['tenant_id'])


def test_phone_policy_writer_rejects_missing_version_and_scoped_override(phone_identity):
    from app.services import effective_config_service as svc
    from app.core.exceptions import AppException
    svc.ensure_definitions()
    for extra in ({}, {'scope_type': 'ORG_UNIT', 'scope_id': '1', 'expected_version': 0}):
        with pytest.raises(AppException):
            svc.set_override('SEC_PHONE_LOGIN_ENABLED', value=1, reason='虚构测试政策变更',
                tenant_id=phone_identity['tenant_id'], **extra)


def test_phone_policy_concurrent_stale_revision_and_audit_rollback(phone_identity, monkeypatch):
    from app.services import effective_config_service as svc, audit_log
    from app.core.exceptions import AppException
    svc.ensure_definitions()
    tid = phone_identity['tenant_id']
    rev = svc.resolve('SEC_PHONE_LOGIN_ENABLED', tenant_id=tid)['policyVersion']
    result = svc.set_override('SEC_PHONE_LOGIN_ENABLED', value=0, reason='虚构关闭手机号登录', expected_version=rev, tenant_id=tid)
    assert result['effective']['value'] == 0
    with pytest.raises(AppException):
        svc.set_override('SEC_PHONE_LOGIN_ENABLED', value=1, reason='陈旧页面不可覆盖', expected_version=rev, tenant_id=tid)
    rev = result['effective']['policyVersion']
    def broken(*a, **k):
        raise RuntimeError('injected policy audit failure')
    monkeypatch.setattr(audit_log, 'record_critical_in_session', broken)
    with pytest.raises(RuntimeError, match='injected policy'):
        svc.set_override('SEC_PHONE_LOGIN_ENABLED', value=1, reason='审计失败必须回滚', expected_version=rev, tenant_id=tid)
    assert svc.resolve('SEC_PHONE_LOGIN_ENABLED', tenant_id=tid)['value'] == 0


def test_governance_query_requires_fine_permission_and_strict_dto(phone_identity):
    from app.modules.system_admin.services import phone_governance_service as svc
    from app.modules.system_admin.routers.phone_governance_router import PhoneQuery, AdminCandidate
    from app.services.control_plane_auth_service import login_with_password
    from app.core.security import decode_token
    from app.core.exceptions import AppException
    from pydantic import ValidationError
    login = login_with_password(phone_identity['login'], 'Local-test-Password1!', phone_identity['tenant'])
    with pytest.raises(AppException):
        svc.query(decode_token(login['accessToken']), PhoneQuery())
    for raw in ({'tenantId': 1}, {'phoneVerified': True}, {'pageSize': 50000}, {'phone': 13800138000}):
        with pytest.raises(ValidationError):
            PhoneQuery(**raw)
    with pytest.raises(ValidationError):
        AdminCandidate(phone='13800138000', reason='test', expectedCandidateVersion=True)


@pytest.fixture
def governor(phone_identity):
    from app.db.session import get_sessionmaker
    from app.models import Role
    from app.core.context import get_tenant, get_current_user_ctx, set_tenant, set_current_user
    from app.services.system_role_shadow_service import converge_published_system_templates
    from app.services.permission_catalog_reconciliation_service import reconcile_permission_catalog
    from app.services.control_plane_auth_service import login_with_password
    from app.core.security import decode_token
    # Explicit test setup via the original catalog/template writers, never HTTP
    # runtime Permission insertion. Only this fixture's dedicated test DB is used.
    reconcile_permission_catalog(source='PHONE_TEST_FIXTURE')
    converge_published_system_templates(actor_user_id=None, source_commit_sha='7c1c2be75-phone-governance-working-tree')
    with get_sessionmaker()() as db:
        role = db.scalar(select(Role).where(Role.tenant_id == phone_identity['tenant_id']))
        role.role_code, role.role_type = 'SYS_ADMIN', 'SYSTEM'
        db.commit()
    previous = get_tenant(), get_current_user_ctx()
    set_tenant(phone_identity['tenant_id'])
    login = login_with_password(phone_identity['login'], 'Local-test-Password1!', phone_identity['tenant'])
    ctx = decode_token(login['accessToken'])
    set_current_user(ctx)
    try:
        yield {**phone_identity, 'ctx': ctx, 'login_result': login}
    finally:
        set_tenant(previous[0])
        set_current_user(previous[1])


def test_real_catalog_governance_masks_and_rejects_self_cross_tenant_stale(governor):
    from app.modules.system_admin.services import phone_governance_service as svc
    from app.modules.system_admin.routers.phone_governance_router import PhoneQuery, AdminCandidate
    from app.core.exceptions import AppException
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import User, PhoneLoginCandidate
    ctx = governor['ctx']
    result = svc.query(ctx, PhoneQuery(phone='13800138000', reason='虚构测试号码核对'))
    assert result['total'] == 1 and result['list'][0]['phoneMasked'] == '138****8000'
    assert '13800138000' not in str(result)
    body = AdminCandidate(phone='13700137000', expectedCandidateVersion=0, reason='虚构教师本人登记')
    with pytest.raises(AppException):
        svc.set_candidate(ctx, governor['user_id'], body)
    with get_sessionmaker()() as db:
        target = User(tenant_id=governor['tenant_id'], login_name='candidate-teacher', real_name='虚构教师',
            user_type='TEACHER', password_hash=hash_password('Synthetic-Test1!'))
        outsider = User(tenant_id=governor['tenant_id'] + 100000, login_name='outside', real_name='其他学校虚构教师',
            user_type='TEACHER', password_hash=hash_password('Synthetic-Test1!'))
        db.add_all([target, outsider]); db.commit()
        target_id, outsider_id, original_hash = target.id, outsider.id, target.password_hash
    with pytest.raises(AppException):
        svc.set_candidate(ctx, outsider_id, body)
    svc.set_candidate(ctx, target_id, body)
    with pytest.raises(AppException):
        svc.set_candidate(ctx, target_id, body)
    with get_sessionmaker()() as db:
        assert db.get(User, target_id).login_name == 'candidate-teacher'
        assert db.get(User, target_id).password_hash == original_hash
        assert db.scalar(select(PhoneLoginCandidate.state).where(PhoneLoginCandidate.user_id == target_id)) == 'PENDING'
    assert svc.query(ctx, PhoneQuery(userId=str(outsider_id)))['total'] == 0


def test_final_generic_policy_route_cannot_bypass_phone_permission(phone_identity, monkeypatch):
    from app.api.v1 import system_p1_closure as route
    from app.services import effective_config_service as configs
    from app.services.control_plane_auth_service import login_with_password
    from app.core.security import decode_token
    from app.core.context import get_tenant, set_tenant
    from app.core.exceptions import AppException
    ctx = decode_token(login_with_password(phone_identity['login'], 'Local-test-Password1!', phone_identity['tenant'])['accessToken'])
    configs.ensure_definitions()
    previous = get_tenant(); set_tenant(phone_identity['tenant_id'])
    # Actor has only the pre-existing generic configuration capability.
    monkeypatch.setattr(route, 'has_permission', lambda user, code: code == 'systemAdmin.config.manage')
    try:
        with pytest.raises(AppException):
            route.set_config_override(body={'configKey': 'SEC_PHONE_LOGIN_ENABLED', 'value': 0,
                'expectedVersion': 0, 'reason': '通用权限不能扩权'}, user=ctx)
        with pytest.raises(AppException):
            route.restore_effective_config_inheritance(body={
                'configKey': 'SEC_PHONE_LOGIN_ENABLED', 'reason': '不得绕过版本恢复继承'}, user=ctx)
    finally:
        set_tenant(previous)


def test_governance_formal_http_projection_and_policy_version(governor, client):
    headers = {'Authorization': 'Bearer ' + governor['login_result']['accessToken']}
    anonymous = client.post('/api/v1/system/phone-bindings/query', headers={'X-Tenant': governor['tenant']}, json={})
    assert anonymous.status_code == 401, anonymous.text
    result = client.post('/api/v1/system/phone-bindings/query', headers=headers, json={})
    assert result.status_code == 200, result.text
    assert '13800138000' not in result.text
    policy = client.get('/api/v1/system/phone-login-policy', headers=headers)
    assert policy.status_code == 200, policy.text
    item = next(row for row in policy.json()['data']['items'] if row['configKey'] == 'SEC_PHONE_LOGIN_ENABLED')
    body = {'configKey': item['configKey'], 'expectedVersion': item['policyVersion'], 'value': 0, 'reason': '虚构学校关闭手机号入口'}
    changed = client.put('/api/v1/system/phone-login-policy', headers=headers, json=body)
    assert changed.status_code == 200, changed.text
    assert changed.json()['data']['effective']['value'] == 0
    assert client.put('/api/v1/system/phone-login-policy', headers=headers, json=body).status_code == 409


def test_batch_preview_is_scope_session_bound_and_stale_candidates_cannot_send(governor):
    from app.modules.system_admin.services import phone_governance_service as svc
    from app.modules.system_admin.routers.phone_governance_router import PhoneBatchPreview, PhoneBatchConfirm
    from app.models import User, PhoneLoginCandidate
    from app.db.session import get_sessionmaker
    from app.core.exceptions import AppException
    from app.core.security import hash_password
    from app.services.phone_login_service import create_pending_candidate_in_session
    with get_sessionmaker()() as db:
        user = User(tenant_id=governor['tenant_id'], login_name='reminder-test', real_name='虚构提醒对象',
            user_type='TEACHER', password_hash=hash_password('Synthetic-Test1!'))
        db.add(user); db.flush()
        create_pending_candidate_in_session(db, tenant_id=user.tenant_id, user_id=user.id,
            phone='13700137000', source_kind='ADMIN', expected_version=0)
        db.commit(); user_id = user.id
    preview = svc.preview_batch(governor['ctx'], PhoneBatchPreview(action='REMIND',
        filters={'userId': str(user_id)}, reason='通知本人完成号码验证'))
    body = PhoneBatchConfirm(previewId=preview['previewId'])
    with pytest.raises(AppException):
        svc.confirm_batch({**governor['ctx'], 'authSessionId': 'different-session'}, body)
    with get_sessionmaker()() as db:
        candidate = db.scalar(select(PhoneLoginCandidate).where(PhoneLoginCandidate.user_id == user_id))
        candidate.version += 1; db.commit()
    with pytest.raises(AppException):
        svc.confirm_batch(governor['ctx'], body)


def test_batch_reminder_uses_original_in_app_outbox_and_one_receipt(governor):
    from app.modules.system_admin.services import phone_governance_service as svc
    from app.modules.system_admin.routers.phone_governance_router import PhoneBatchPreview, PhoneBatchConfirm
    from app.models import User, PhoneLoginCandidate, MessageEventOutbox, PasswordResetSmsJob
    from app.db.session import get_sessionmaker
    from app.core.security import hash_password
    from app.services.phone_login_service import create_pending_candidate_in_session
    with get_sessionmaker()() as db:
        user = User(tenant_id=governor['tenant_id'], login_name='reminder-once', real_name='虚构提醒对象',
            user_type='TEACHER', password_hash=hash_password('Synthetic-Test1!'))
        db.add(user); db.flush()
        create_pending_candidate_in_session(db, tenant_id=user.tenant_id, user_id=user.id,
            phone='13700137000', source_kind='ADMIN', expected_version=0)
        db.commit(); user_id = user.id
    preview = svc.preview_batch(governor['ctx'], PhoneBatchPreview(action='REMIND',
        filters={'userId': str(user_id)}, reason='通知本人完成号码验证'))
    body = PhoneBatchConfirm(previewId=preview['previewId'])
    first = svc.confirm_batch(governor['ctx'], body)
    assert first == svc.confirm_batch(governor['ctx'], body)
    assert first['channel'] == 'IN_APP' and first['count'] == 1
    with get_sessionmaker()() as db:
        rows = db.scalars(select(MessageEventOutbox).where(MessageEventOutbox.tenant_id == governor['tenant_id'])).all()
        assert len(rows) == 1 and rows[0].event_code == 'AUTH.PHONE_VERIFY_REMINDER'
        assert rows[0].recipient_refs_json == [{'userId': user_id}]
        assert '13700137000' not in str(rows[0].payload_json)
        assert db.scalar(select(PasswordResetSmsJob.id).where(PasswordResetSmsJob.tenant_id == governor['tenant_id'])) is None
        outbox_id = rows[0].id
    from app.services.message_event_outbox_service import process_pending_outbox
    from app.models import UnifiedMessage, MessageCampaign
    process_pending_outbox(limit=1, worker_id='phone-local-test', outbox_ids=[outbox_id])
    with get_sessionmaker()() as db:
        campaign = db.scalar(select(MessageCampaign).where(MessageCampaign.tenant_id == governor['tenant_id']))
        assert campaign.channels_json == ['IN_APP']
        assert db.scalar(select(UnifiedMessage.id).where(UnifiedMessage.tenant_id == governor['tenant_id'])) is not None


def test_masked_export_uses_original_private_file_job_and_download_ticket(governor, tmp_path, monkeypatch):
    from app.modules.system_admin.services import phone_governance_service as svc
    from app.modules.system_admin.routers.phone_governance_router import PhoneBatchPreview, PhoneBatchConfirm
    from app.services import data_exchange_job_service as jobs
    from app.services.storage.local import LocalStorageBackend
    from app.core.config import settings
    from app.models import FileObject
    from app.db.session import get_sessionmaker
    from app.core.exceptions import AppException
    from openpyxl import load_workbook
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(jobs, 'get_backend', LocalStorageBackend)
    preview = svc.preview_batch(governor['ctx'], PhoneBatchPreview(action='EXPORT',
        filters={'userId': str(governor['user_id'])}, reason='核对学校脱敏手机号台账'))
    body = PhoneBatchConfirm(previewId=preview['previewId'])
    result = svc.confirm_batch(governor['ctx'], body)
    assert result == svc.confirm_batch(governor['ctx'], body)
    job = result['job']
    with get_sessionmaker()() as db:
        file = db.get(FileObject, int(job['fileObjectId']))
        assert file.visibility == 'PRIVATE' and file.upload_source == 'SYSTEM'
        book = load_workbook(tmp_path / file.file_key, read_only=True)
        values = list(book.active.values); book.close()
        assert len(values) == 2 and '138****8000' in str(values)
        assert '13800138000' not in str(values)
    with pytest.raises(AppException):
        jobs.create_download_ticket(job['id'], expected_version=job['version'],
            user={**governor['ctx'], 'authSessionId': 'another-login'})
    ticket = jobs.create_download_ticket(job['id'], expected_version=job['version'], user=governor['ctx'])
    path, _ = jobs.consume_download_ticket(job['id'], ticket['ticket'], user=governor['ctx'])
    assert path.is_file()
    with pytest.raises(AppException):
        jobs.consume_download_ticket(job['id'], ticket['ticket'], user=governor['ctx'])


def test_admin_revoke_rejects_self_wrong_password_stale_and_revokes_epoch(governor):
    from app.modules.system_admin.services import phone_governance_service as svc
    from app.modules.system_admin.routers.phone_governance_router import AdminRevoke
    from app.services.phone_login_service import phone_lookup
    from app.core.field_crypto import encrypt_field
    from app.models import User, PhoneLoginBinding
    from app.core.security import hash_password
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    body = AdminRevoke(currentPassword='Local-test-Password1!', reason='学校核对误绑撤销凭据',
        expectedBindingVersion=1, operationKey='synthetic-revoke-operation-key')
    with pytest.raises(AppException):
        svc.revoke_binding(governor['ctx'], governor['user_id'], body)
    with get_sessionmaker()() as db:
        user = User(tenant_id=governor['tenant_id'], login_name='revoke-test', real_name='虚构待撤销对象',
            user_type='TEACHER', password_hash=hash_password('Synthetic-Test1!'))
        db.add(user); db.flush()
        binding = PhoneLoginBinding(tenant_id=user.tenant_id, user_id=user.id, state='VERIFIED', version=1,
            active_phone_lookup=phone_lookup(user.tenant_id, '13700137000'), phone_ciphertext=encrypt_field('+8613700137000'))
        db.add(binding); db.commit(); user_id = user.id; password_hash = user.password_hash
    for changed in ({'currentPassword': 'wrong'}, {'expectedBindingVersion': 0}):
        with pytest.raises(AppException):
            svc.revoke_binding(governor['ctx'], user_id, body.model_copy(update=changed))
    result = svc.revoke_binding(governor['ctx'], user_id, body)
    assert result == svc.revoke_binding(governor['ctx'], user_id, body)
    assert result['state'] == 'REVOKED'
    with get_sessionmaker()() as db:
        assert db.get(User, user_id).password_hash == password_hash
        assert db.get(User, user_id).credential_version == 1
        assert db.get(PhoneLoginBinding, binding.id).active_phone_lookup is None
        assert db.get(PhoneLoginBinding, binding.id).version == 2
