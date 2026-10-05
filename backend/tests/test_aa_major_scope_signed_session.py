"""T07：同一真实签名令牌预热后撤权；不是正常账号登录或浏览器验收。"""
import hashlib
import time
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker
from app.core.timeutil import utc_now_naive
from tests.test_aa_major_scope_and_school_transfer import OTHER_TID, TID, facts

BASE = '/api/v1/academic-affairs'
VIEW = 'academicAffairs.program.view'
MANAGE = 'academicAffairs.program.manage'
DASHBOARD = 'academicAffairs.dashboard.view'


def _academic_module_authority(facts):
    """复用正式商品发布、分项订单支付和学校启用命令，不能用 FEATURES 开关冒充购买。"""
    from tests.test_module_commerce_m12_runtime import _sku, _pay
    from app.services.module_access_service import module_access_state
    from app.services.tenant_capability_setting_service import set_capability

    set_tenant(TID)
    set_current_user(facts['school_user'])
    snapshot = _sku('academicAffairs', code='T07-SIGNED-ACADEMIC')
    _pay(TID, [snapshot], 't07-signed-academic-order')
    set_capability('academicAffairs', enabled=True, reason='隔离教务旧会话验收启用',
                   tenant_id=TID, user=facts['school_user'])
    state = module_access_state(TID, 'academicAffairs')
    assert state['entitled'] and state['enabled'] and state['allowed'] and state['writable']


def _signed_identity(facts):
    """补正式治理事实与具体工作台权限，再由实际身份服务签发一次。"""
    from app.core.security import create_access_token
    from app.models import (CustomRoleSource, Role, RolePermission,
                            RoleTemplate, User, UserRole)
    from app.services import role_assignment_p1_guard_service as memberships
    from app.modules.system_admin.services import role_template_service as templates
    from app.modules.system_admin.services.school_iam_authority_projection_service import _template_permissions
    from app.modules.system_admin.routers.system_router import _custom_role_source_snapshot
    from app.services.auth_service_db import _claims, _role_contexts
    from tests.support_academic_review_identity import _ensure_permission

    codes = sorted([VIEW, MANAGE, DASHBOARD])
    draft = templates.create_draft(template_code='T07_SIGNED_PROGRAM_SOURCE',
        template_name='隔离专业会话回归模板', permission_codes=codes,
        change_reason='隔离旧会话的正式来源模板', actor_user_id=None)
    published = templates.publish_draft(int(draft['id']), expected_version=int(draft['version']),
                                        actor_user_id=None)
    with get_sessionmaker()() as db:
        role = db.get(Role, int(facts['major_user']['activeContextId'].split(':')[1]))
        user = db.get(User, int(facts['major_user']['userId']))
        user.must_change_password = False
        initial_member = db.scalar(select(UserRole).where(UserRole.tenant_id == TID,
            UserRole.user_id == user.id, UserRole.role_id == role.id))
        # Explicit initial facts: the public P1 command must grant, not overwrite an ACTIVE membership.
        initial_member.status = 'EXPIRED'
        grant = _ensure_permission(db, DASHBOARD)
        db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=grant.id, status='ACTIVE'))
        # A real pinned source lets the existing permission command retain its binding/audit guards.
        template = db.get(RoleTemplate, int(published['id']))
        assert _template_permissions(db, template) == codes
        db.add(CustomRoleSource(tenant_id=TID, role_id=role.id, role_code=role.role_code,
            source_template_code=template.template_code, source_template_version=template.template_version,
            permission_codes_json={'items': codes}, drift_json={'policy': 'PINNED', 'automaticUpgrade': False},
            status='ACTIVE'))
        # Removal is restricted to the actor's authoring catalog as well as retained permissions.
        for code in (VIEW, MANAGE, DASHBOARD, 'systemAdmin.role.config'):
            permission = _ensure_permission(db, code)
            if not db.scalar(select(RolePermission.id).where(RolePermission.tenant_id == TID,
                    RolePermission.role_id == facts['school_role'], RolePermission.permission_id == permission.id)):
                db.add(RolePermission(tenant_id=TID, role_id=facts['school_role'],
                    permission_id=permission.id, status='ACTIVE'))
        db.commit()
        assert _custom_role_source_snapshot(db, role, tenant_id=TID) == (
            template.template_code, template.template_version)
        user_id, role_id, role_code = user.id, role.id, role.role_code
    granted = memberships.grant_assignment(user_id, role_code, reason='正式授予隔离专业岗位',
        tenant_id=TID, user=facts['school_user'])
    with get_sessionmaker()() as db:
        user = db.get(User, user_id)
        contexts = _role_contexts(db, user)
        context = next(row for row in contexts if row['roleCode'] == role_code)
        token = create_access_token(_claims(db, user, context, contexts, 'PC'))
        return {'Authorization': 'Bearer ' + token}, int(granted['assignmentId']), role_id



def _state(program_id):
    from app.models import AaProgram, AffairsAuditTrail
    with get_sessionmaker()() as db:
        row = db.get(AaProgram, program_id)
        updates = db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == TID, AffairsAuditTrail.biz_type == 'AA_PROGRAM',
            AffairsAuditTrail.biz_id == program_id, AffairsAuditTrail.action == 'UPDATE'))
        return (row.program_name, row.total_credits, row.version, row.requirement_json, updates)


@pytest.mark.parametrize('condition', ['immediate_grant', 'no_history', 'future', 'expired',
    'revoked', 'deleted', 'wrong_user', 'wrong_role', 'foreign_tenant_history'])
def test_actual_role_contexts_enforce_member_validity_identity_and_window(facts, condition):
    """直接真实角色解析，既不重复购买许可，也不替换身份服务。"""
    from app.models import User, UserRole
    from app.models.role_assignment import RoleAssignmentValidity
    from app.services import role_assignment_service as memberships
    from app.services.auth_service_db import _role_contexts

    validity_id = None
    if condition != 'no_history':
        _headers, validity_id, _role_id = _signed_identity(facts)
    with get_sessionmaker()() as db:
        user = db.get(User, int(facts['major_user']['userId']))
        if validity_id is None:
            assert not db.scalar(select(RoleAssignmentValidity.id).where(
                RoleAssignmentValidity.tenant_id == TID, RoleAssignmentValidity.user_id == user.id))
        else:
            window = db.get(RoleAssignmentValidity, validity_id)
            assert db.get(UserRole, window.user_role_id).status == 'ACTIVE'
            if condition == 'future':
                window.effective_at = memberships._now() + timedelta(days=1)
            elif condition == 'expired':
                window.expires_at = memberships._now() - timedelta(days=1)
            elif condition == 'revoked':
                window.status = 'REVOKED'
            elif condition == 'deleted':
                window.is_deleted = True
            elif condition == 'wrong_user':
                window.user_id = int(facts['school_user']['userId'])
            elif condition == 'wrong_role':
                window.role_code = facts['school_user']['currentRoleCode']
            elif condition == 'foreign_tenant_history':
                window.tenant_id = OTHER_TID
                window.status = 'REVOKED'
            db.commit()
        returned = {row['roleCode'] for row in _role_contexts(db, user)}
        expected = condition in ('immediate_grant', 'no_history', 'foreign_tenant_history')
        assert (facts['major_user']['currentRoleCode'] in returned) is expected


def _response_diagnostic(response):
    """失败诊断仅保留错误码，不能把刷新凭据或响应数据写入测试日志。"""
    try:
        body = response.json()
    except ValueError:
        body = {}
    return {'status': response.status_code, 'code': body.get('code'), 'bizCode': body.get('bizCode')}


def _assert_public_contexts(identity):
    contexts = identity['contexts']
    assert isinstance(contexts, list) and contexts
    for context in contexts:
        private_keys = {'_roleVersion', '_memberVersion', 'version'}.intersection(context)
        assert not private_keys, private_keys


@pytest.mark.parametrize('change', ['member_revoked', 'validity_expired', 'validity_future',
                                    'validity_revoked', 'validity_deleted', 'scope_revoked',
                                    'scope_expired', 'manage_revoked'])
def test_same_signed_major_session_rechecks_revocation_without_relogin(client, facts, change, record_property):
    from app.core.config import settings
    from app.models import Role, RoleAssignmentScope, UserRole
    from app.models.role_assignment import RoleAssignmentValidity
    from app.modules.system_admin.routers.system_router import save_system_role_permissions
    from app.services import role_assignment_service
    from app.services.role_assignment_scope_service import revoke_removed_role_scopes

    _academic_module_authority(facts)
    headers, validity_id, role_id = _signed_identity(facts)
    original_digest = hashlib.sha256(headers['Authorization'].encode()).hexdigest()
    program_id = facts['programs']['own']
    interval = 1.05 / max(1, min(settings.USER_API_RATE_LIMIT_PER_SECOND,
                                settings.TENANT_API_RATE_LIMIT_PER_SECOND))
    last_request = 0.0

    def request(method, path, *, include_access=True, session_headers=None, **kwargs):
        nonlocal last_request
        time.sleep(max(0.0, interval - (time.monotonic() - last_request)))
        selected_headers = session_headers if session_headers is not None else headers if include_access else {}
        response = client.request(method, path, headers=selected_headers, **kwargs)
        last_request = time.monotonic()
        return response

    def success(response):
        assert response.status_code == 200, _response_diagnostic(response)
        assert response.json()['code'] == 0, _response_diagnostic(response)
        return response.json()['data']

    def denied(response):
        assert response.status_code in (401, 403), _response_diagnostic(response)
        assert response.json()['code'] != 0, _response_diagnostic(response)

    warm_identity = success(request('GET', '/api/v1/auth/me'))
    _assert_public_contexts(warm_identity)
    assert success(request('GET', f'{BASE}/programs/{program_id}'))['majorId'] == str(facts['major'])
    success(request('PUT', f'{BASE}/programs/{program_id}', json={'programName': '旧会话撤权前正式编辑'}))
    projection = success(request('GET', f'{BASE}/flow'))
    assert projection['viewer']['majorIds'] == [str(facts['major'])]
    from app.core.security import decode_token
    from app.core.redis_client import cache_get_json, get_redis
    from app.services.auth_service_db import _subject_cache_key, _subject_cache_matches
    claims = decode_token(headers['Authorization'].split(' ', 1)[1])
    cached = cache_get_json(_subject_cache_key(claims))
    assert get_redis() is not None, '该旧会话检查要求总控配置独立真实缓存，不能替身或跳过预热'
    assert isinstance(cached, dict), '首次真实接口请求未写入本主体缓存'
    assert cached['active'] is True
    assert cached['roleCode'] == claims['currentRoleCode']
    assert cached['permissionVersion'] == claims['permissionVersion']
    assert _subject_cache_matches(claims) is True
    record_property('subject_cache_storage', 'Redis')
    from app.core.token_store import issue_refresh
    refresh_token = None
    if change == 'member_revoked' or change.startswith('validity_') or change == 'manage_revoked':
        refresh_token = issue_refresh(dict(claims))
    before = _state(program_id)

    # The HTTP request may clear request context; explicitly restore the separate trusted fixture actor.
    set_tenant(TID)
    set_current_user(facts['school_user'])
    if change == 'member_revoked':
        with get_sessionmaker()() as db:
            version = int(db.get(RoleAssignmentValidity, validity_id).version or 0)
        role_assignment_service.revoke_assignment(validity_id, reason='正式回收专业编制岗位',
            expected_version=version, tenant_id=TID, user=facts['school_user'])
    elif change == 'manage_revoked':
        with get_sessionmaker()() as db:
            version = int(db.get(Role, role_id).version or 0)
        result = save_system_role_permissions(role_id, {'permissionCodes': [VIEW, DASHBOARD],
            'expectedVersion': version, 'reason': '正式撤销专业编制权限', 'requestId': str(uuid.uuid4())},
            user=facts['school_user'])
        assert result['code'] == 0
    else:
        with get_sessionmaker()() as db:
            if change.startswith('validity_'):
                window = db.get(RoleAssignmentValidity, validity_id)
                if change == 'validity_expired':
                    window.expires_at = role_assignment_service._now() - timedelta(days=1)
                elif change == 'validity_future':
                    window.effective_at = role_assignment_service._now() + timedelta(days=1)
                elif change == 'validity_revoked':
                    window.status = 'REVOKED'
                else:
                    window.is_deleted = True
                assert db.get(UserRole, window.user_role_id).status == 'ACTIVE'
            elif change == 'scope_expired':
                db.get(RoleAssignmentScope, facts['scope']).expires_at = utc_now_naive() - timedelta(days=1)
            else:
                revoke_removed_role_scopes(db, tenant_id=TID, user_id=int(facts['major_user']['userId']),
                    active_role_codes=set(), actor=facts['school_user'])
            db.commit()

    denied(request('PUT', f'{BASE}/programs/{program_id}', json={'programName': '撤权后禁止写入'}))
    denied(request('GET', f'{BASE}/programs/{program_id}'))
    denied(request('GET', f'{BASE}/flow'))
    me = request('GET', '/api/v1/auth/me')
    if change == 'member_revoked' or change.startswith('validity_') or change == 'manage_revoked':
        denied(me)
    else:
        success(me)
    if refresh_token is not None:
        # Let the refresh endpoint validate its persisted original claims; no access-header rejection shortcut.
        denied(request('POST', '/api/v1/authz/token/refresh', include_access=False,
                       json={'refreshToken': refresh_token}))
    if change == 'manage_revoked':
        from app.core.permissions import has_permission
        from app.models import CustomRoleSource, Permission, RolePermission
        set_tenant(TID)
        assert has_permission(facts['major_user'], VIEW)
        assert has_permission(facts['major_user'], DASHBOARD)
        assert not has_permission(facts['major_user'], MANAGE)
        with get_sessionmaker()() as db:
            source = db.scalar(select(CustomRoleSource).where(CustomRoleSource.tenant_id == TID,
                CustomRoleSource.role_id == role_id, CustomRoleSource.is_deleted.is_(False)))
            assert set(source.permission_codes_json['items']) == {VIEW, DASHBOARD}
            current_codes = set(db.scalars(select(Permission.permission_code).join(RolePermission,
                RolePermission.permission_id == Permission.id).where(RolePermission.tenant_id == TID,
                RolePermission.role_id == role_id, RolePermission.status == 'ACTIVE',
                RolePermission.is_deleted.is_(False))).all())
            assert current_codes == {VIEW, DASHBOARD}
        # This is a separate current identity, created only after the original access/refresh refusals.
        from app.core.security import create_access_token
        from app.models import User
        from app.services.auth_service_db import _claims, _role_contexts
        with get_sessionmaker()() as db:
            current_user = db.get(User, int(facts['major_user']['userId']))
            current_contexts = _role_contexts(db, current_user)
            current_context = next(row for row in current_contexts
                if row['roleCode'] == facts['major_user']['currentRoleCode'])
            fresh_token = create_access_token(_claims(db, current_user, current_context, current_contexts, 'PC'))
        fresh_headers = {'Authorization': 'Bearer ' + fresh_token}
        fresh_digest = hashlib.sha256(fresh_headers['Authorization'].encode()).hexdigest()
        assert fresh_digest != original_digest
        fresh_identity = success(request('GET', '/api/v1/auth/me', session_headers=fresh_headers))
        _assert_public_contexts(fresh_identity)
        assert fresh_identity['currentRole']['roleCode'] == facts['major_user']['currentRoleCode']
        current_program = success(request('GET', f'{BASE}/programs/{program_id}', session_headers=fresh_headers))
        assert current_program['programName'] == before[0]
        assert current_program['majorId'] == str(facts['major'])
        current_flow = success(request('GET', f'{BASE}/flow', session_headers=fresh_headers))
        assert current_flow['viewer']['majorIds'] == [str(facts['major'])]
        fresh_write = request('PUT', f'{BASE}/programs/{program_id}', session_headers=fresh_headers,
            json={'programName': '新会话也无编制权限'})
        denied(fresh_write)
        assert fresh_write.status_code == 403, _response_diagnostic(fresh_write)
    current_digest = hashlib.sha256(headers['Authorization'].encode()).hexdigest()
    assert current_digest == original_digest
    assert _state(program_id) == before
