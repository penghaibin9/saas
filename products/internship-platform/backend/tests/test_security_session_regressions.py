"""Session revocation and live identity tests; no services or database mutated."""
import asyncio
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core import security, token_store
from app.core.exceptions import AppException
from app.api.v1 import standalone_browser_auth as auth
from app.services import browser_auth_session_blocklist as families
from app.db import session as sessions


class SessionSecurityTest(unittest.TestCase):
    def test_database_access_token_does_not_serialize_live_permission_catalog(self):
        permissions=['internship.example.action'+str(n) for n in range(1000)]
        claims={**self.claims(),'permissions':permissions,'permissionCodes':['*'],'credentialVersion':3}
        with patch.object(security.settings,'JWT_SECRET','isolated-session-test-key-32-bytes!'):
            token=security.create_access_token(claims)
            decoded=security.decode_token(token)
        self.assertLess(len(token),2048)
        self.assertNotIn('permissions',decoded)
        self.assertNotIn('permissionCodes',decoded)
        for key in ('userId','tenantId','currentRoleCode','authSessionId','credentialVersion'):
            self.assertEqual(decoded[key],claims[key])
        self.assertEqual(claims['permissions'],permissions)

    def test_normal_browser_logout_invalidates_access_and_family(self):
        from fastapi import Response
        claims={**self.claims(),'exp':time.time()+120}
        for channel in ('staff','student'):
            with patch.object(token_store,'_client',return_value=None), \
                 patch.dict(token_store._memory_blocked,{},clear=True), \
                 patch.object(families,'_logout_access_claims',return_value=claims):
                auth.browser_logout(NS(cookies={}),Response(),channel,'own-test-tab','Bearer valid')
                self.assertTrue(token_store.jti_blocked('access'))
                self.assertTrue(families.auth_session_blocked('family'))
                with self.assertRaises(AppException): security._validate_db_subject(claims)

    def test_logout_cannot_report_success_when_revocation_write_fails(self):
        from fastapi import Response
        with patch.object(families,'_logout_access_claims',return_value={**self.claims(),'exp':time.time()+120}), \
             patch.object(families,'block_jti',side_effect=AppException('AUTH_STORE_UNAVAILABLE','认证存储不可用')):
            with self.assertRaises(AppException):
                auth.browser_logout(NS(cookies={}),Response(),'staff','own-test-tab','Bearer valid')

    def test_enterprise_refresh_preserves_family(self):
        from app.modules.internship.services import internship_enterprise_auth_service as enterprise
        tenant=NS(id=1,tenant_code='test',school_name='学校')
        member=NS(id=7,company_id=9,member_role='MENTOR',version=0)
        account=self.account()
        with patch.object(enterprise,'consume_refresh',return_value={'authSessionId':'family'}), \
             patch.object(enterprise,'validate_enterprise_claims',return_value=(tenant,account,member)), \
             patch.object(enterprise,'create_access_token',side_effect=lambda claims:claims), \
             patch.object(enterprise,'issue_refresh',side_effect=lambda claims:claims):
            result=enterprise.refresh(refresh_token='refresh')
            self.assertEqual(result['accessToken']['authSessionId'],'family')
            self.assertEqual(result['refreshToken']['authSessionId'],'family')

    def test_enterprise_shared_validation_rejects_revoked_family(self):
        from app.modules.internship.services import internship_enterprise_auth_service as enterprise
        claims={**self.claims(), 'userType':'ENTERPRISE_MENTOR', 'enterpriseMemberId':'7', 'companyId':'9'}
        with patch.object(enterprise,'jti_blocked',return_value=False), \
             patch.object(families,'auth_session_blocked',return_value=True), \
             patch.object(enterprise,'get_sessionmaker') as factory:
            with self.assertRaises(AppException): enterprise.validate_enterprise_claims(claims)
            factory.assert_not_called()

    def test_refresh_finishing_after_expired_access_logout_stays_revoked(self):
        import jwt
        from app.config import settings
        from app.api.v1 import standalone_mobile_auth as mobile
        with patch.object(settings,'JWT_SECRET','isolated-session-test-key-32-bytes!'), \
             patch.object(token_store,'_client',return_value=None), \
             patch.dict(token_store._memory_refresh,{},clear=True), \
             patch.dict(token_store._memory_blocked,{},clear=True):
            claims={**self.claims(),'clientType':'STUDENT_MINI'}
            expired=jwt.encode({**claims,'exp':time.time()-10},settings.JWT_SECRET,algorithm=settings.JWT_ALG)
            with self.assertRaises(AppException): security.decode_token(expired)
            original=token_store.issue_refresh(claims)
            in_flight=token_store.consume_refresh(original)
            result=mobile.mobile_logout(mobile.MobileLogoutRequest(refreshToken=original),'Bearer '+expired)
            self.assertTrue(result['data']['invalidated'])
            with self.assertRaises(AppException): token_store.issue_refresh(in_flight)
            late_access=security.create_access_token(in_flight)
            with self.assertRaises(AppException): security._validate_db_subject(security.decode_token(late_access))
            self.assertFalse(token_store._memory_refresh)

    def test_refresh_issuance_checks_family_in_the_same_redis_operation(self):
        client=MagicMock()
        with patch.object(token_store,'_client',return_value=client):
            client.eval.return_value=1
            self.assertTrue(token_store.issue_refresh(self.claims()))
            script,count,refresh_key,blocked_key,payload,ttl=client.eval.call_args.args
            self.assertEqual(count,2)
            self.assertTrue(blocked_key.endswith('auth:jti:auth-session:family'))
            self.assertEqual(ttl,token_store.REFRESH_TTL)
            client.set.assert_not_called()
            client.eval.return_value=0
            with self.assertRaises(AppException) as caught: token_store.issue_refresh(self.claims())
            self.assertEqual(caught.exception.code,'UNAUTHORIZED')
            client.eval.side_effect=OSError('unavailable')
            with self.assertRaises(AppException) as caught: token_store.issue_refresh(self.claims())
            self.assertEqual(caught.exception.code,'AUTH_STORE_UNAVAILABLE')

    def test_family_revocation_uses_write_time_duration_and_tab_refresh_consumes_once(self):
        with patch.object(token_store,'_client',return_value=None), \
             patch.dict(token_store._memory_refresh,{},clear=True), \
             patch.dict(token_store._memory_blocked,{},clear=True), \
             patch.object(token_store.time,'time',return_value=1000):
            claims={**self.claims(),'browserChannel':'staff','browserSessionIdHash':'own-tab-hash'}
            token=token_store.issue_refresh(claims)
            self.assertIsNone(token_store.consume_refresh_if_matches(token,expected_browser_channel='student',expected_browser_session_hash='own-tab-hash'))
            self.assertEqual(token_store.consume_refresh_if_matches(token,expected_browser_channel='staff',expected_browser_session_hash='own-tab-hash'),claims)
            self.assertIsNone(token_store.consume_refresh_if_matches(token,expected_browser_channel='staff',expected_browser_session_hash='own-tab-hash'))
            token_store.block_jti('auth-session:family',exp_ts=900,ttl_seconds=token_store.REFRESH_TTL)
            self.assertEqual(token_store._memory_blocked['auth-session:family'],1000+token_store.REFRESH_TTL)

    def test_logout_blocks_both_verified_families_but_not_forged_credentials(self):
        import jwt
        from app.config import settings
        with patch.object(settings,'JWT_SECRET','isolated-session-test-key-32-bytes!'), \
             patch.object(token_store,'_client',return_value=None), \
             patch.dict(token_store._memory_blocked,{},clear=True):
            token=security.create_access_token(self.claims())
            self.assertTrue(families.revoke_logout_credentials('bearer '+token,{'authSessionId':'cookie-family'}))
            self.assertTrue(families.auth_session_blocked('family'))
            self.assertTrue(families.auth_session_blocked('cookie-family'))
            forged=jwt.encode({**self.claims(),'authSessionId':'forged','exp':time.time()+60},'wrong-test-signing-key-32-bytes!!!',algorithm=settings.JWT_ALG)
            self.assertFalse(families.revoke_logout_credentials('Bearer '+forged))
            self.assertFalse(families.auth_session_blocked('forged'))

    def test_enterprise_original_login_issues_family_and_old_refresh_is_rejected(self):
        from app.modules.internship.services import internship_enterprise_auth_service as enterprise
        tenant=NS(id=1,tenant_code='test',school_name='学校')
        member=NS(id=7,company_id=9,member_role='MENTOR',version=0)
        with patch.object(enterprise,'create_access_token',side_effect=lambda claims:claims), \
             patch.object(enterprise,'issue_refresh',side_effect=lambda claims:claims):
            result=enterprise._token_result(tenant=tenant,user=self.account(),member=member)
            self.assertTrue(result['accessToken']['authSessionId'])
            self.assertEqual(result['accessToken']['authSessionId'],result['refreshToken']['authSessionId'])
        for claims in ({'userType':'ENTERPRISE_MENTOR'},
                       {'userType':'ENTERPRISE_MENTOR','authSessionId':'revoked'}):
            with patch.object(enterprise,'consume_refresh',return_value=claims), \
                 patch.object(enterprise,'jti_blocked',return_value=False), \
                 patch.object(families,'auth_session_blocked',return_value=True), \
                 patch.object(enterprise,'get_sessionmaker') as factory:
                with self.assertRaises(AppException): enterprise.refresh(refresh_token='old')
                factory.assert_not_called()

    def test_browser_refresh_without_family_requires_relogin_before_database_access(self):
        from fastapi import Response
        with patch.object(auth,'consume_refresh_if_matches',return_value=self.claims() | {'authSessionId':''}), \
             patch.object(security,'_validate_db_subject') as validate:
            with self.assertRaises(AppException) as caught:
                auth.browser_refresh(NS(cookies={auth._cookie_name('staff','own-test-tab'):'old-refresh'}),Response(),
                                     'staff','own-test-tab')
            self.assertEqual(caught.exception.code,'UNAUTHORIZED')
            validate.assert_not_called()

    def claims(self):
        return dict(userId='db-5', tenantId='1', currentRoleCode='SCHOOL_ADMIN',
                    credentialVersion=0, jti='access', authSessionId='family')

    def account(self):
        return NS(id=5, tenant_id=1, expires_at=None, version=0, credential_version=0, must_change_password=False, user_type='TEACHER',
                  login_name='teacher5', real_name='老师')

    def test_access_and_family_revocation_at_common_entry(self):
        for revoked, family in ((True, False), (False, True)):
            with patch.object(security, 'decode_token', return_value=self.claims()), \
                 patch.object(token_store, 'jti_blocked', return_value=revoked), \
                 patch.object(families, 'auth_session_blocked', return_value=family), \
                 patch.object(sessions, 'get_sessionmaker') as factory, patch.object(sessions, 'db_enabled', return_value=True):
                db = factory.return_value.return_value
                db.scalar.return_value = self.account()
                db.execute.return_value.all.return_value = [('SCHOOL_ADMIN', '管理员')]
                with self.assertRaises(AppException):
                    asyncio.run(security.get_current_user(NS(url=NS(path='/api/v1/business')), 'Bearer valid'))

    def test_school_or_role_revoked(self):
        for school, roles in ((None, [('SCHOOL_ADMIN', '管理员')]), (NS(id=1), []), (NS(id=1), [('LEADER', '领导')])):
            with patch.object(sessions, 'get_sessionmaker') as factory, patch.object(sessions, 'db_enabled', return_value=True), \
                 patch.object(token_store, 'jti_blocked', return_value=False), patch.object(families, 'auth_session_blocked', return_value=False):
                db = factory.return_value.return_value
                db.scalar.side_effect = [self.account(), school]
                db.execute.return_value.all.return_value = roles
                with self.assertRaises(AppException): security._validate_db_subject(self.claims())

    def test_live_role_removes_old_permission_override(self):
        with patch.object(sessions, 'get_sessionmaker') as factory, patch.object(sessions, 'db_enabled', return_value=True), \
             patch.object(token_store, 'jti_blocked', return_value=False), patch.object(families, 'auth_session_blocked', return_value=False):
            db = factory.return_value.return_value
            db.scalar.side_effect = [self.account(), NS(id=1)]
            db.execute.return_value.all.return_value = [('SCHOOL_ADMIN', '管理员')]
            db.get.return_value=NS(id=1,is_deleted=False,status='ACTIVE')
            db.scalars.return_value.all.return_value=[NS(id=1,tenant_id=1,role_code='SCHOOL_ADMIN',role_name='管理员',base_role_code='SCHOOL_ADMIN',version=0)]
            db.scalars.return_value.__iter__.return_value=iter(['internship.student.view'])
            result = security._validate_db_subject({**self.claims(), 'permissions': ['*'], 'permissionCodes': ['*']})
            self.assertNotIn('*', result.get('permissions', [])); self.assertNotIn('permissionCodes', result)
            self.assertEqual(result['loginName'], 'teacher5')

    def test_no_role_fallback(self):
        db = MagicMock(); db.execute.return_value.all.return_value = []
        for user_type in ('SCHOOL_ADMIN', 'TEACHER', 'STUDENT'):
            with self.subTest(user_type=user_type), self.assertRaises(AppException):
                auth._roles_for_user(db, tenant_id=1, user=NS(id=5, user_type=user_type))

    def test_revocation_read_failure_is_not_missing(self):
        client = MagicMock(); client.config_get.return_value = {'maxmemory-policy': 'noeviction', 'appendonly':'yes', 'appendfsync':'always'}
        client.get.side_effect = OSError('unavailable')
        with patch.object(token_store, 'get_redis', return_value=client), patch.object(token_store, 'cache_get', return_value=None, create=True):
            with self.assertRaises(AppException): token_store.jti_blocked('revoked')

    def test_revocation_requires_non_evicting_store(self):
        client = MagicMock(); client.config_get.return_value = {'maxmemory-policy': 'allkeys-lru'}
        with patch.object(token_store, 'get_redis', return_value=client), patch.object(token_store, 'cache_get', return_value=None, create=True):
            with self.assertRaises(AppException): token_store.block_jti('revoked')

    def test_revocation_requires_durable_acknowledgement(self):
        client=MagicMock()
        for appendonly,fsync in [('no','always'),('yes','everysec')]:
            client.config_get.return_value={'maxmemory-policy':'noeviction','appendonly':appendonly,'appendfsync':fsync}
            with patch.object(token_store,'get_redis',return_value=client),self.assertRaises(AppException):
                token_store.block_jti('revoked')
        client.config_get.return_value={'maxmemory-policy':'noeviction','appendonly':'yes','appendfsync':'always'}
        client.get.return_value='1'
        with patch.object(token_store,'get_redis',return_value=client):
            self.assertTrue(token_store.block_jti('revoked',time.time()+20))
            self.assertTrue(token_store.jti_blocked('revoked'))
            self.assertGreaterEqual(client.set.call_args.kwargs['ex'],20)


if __name__ == '__main__': unittest.main()
