"""Commercial HTTP wiring regressions, using the real production route registrar.

These are routing/permission/transport proofs, not MySQL lifecycle acceptance.
Only authenticated identity input, stored PAM records and business IO are replaced.
The real identity-plane and capability checks execute; no customer rows are read.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class CommerceRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi import APIRouter, FastAPI
        from app.api.v1 import platform, sandbox_story_api
        from app.api.v1.route_registration import register_platform_routes
        from app.core.exceptions import register_exception_handlers
        from app.modules.platform import routers
        from app.modules.platform.routers import module_commerce_router, platform_bundle, platform_router
        from app.modules.platform.services import platform_access_governance_legacy

        cls.facade, cls.package = platform, routers
        cls.commerce, cls.canonical, cls.bundle = module_commerce_router, platform_router, platform_bundle
        cls.sandbox = sandbox_story_api
        cls.pam = platform_access_governance_legacy
        cls.registered = APIRouter()
        register_platform_routes(cls.registered)
        cls.app = FastAPI()
        register_exception_handlers(cls.app)
        cls.app.include_router(cls.registered, prefix='/api/v1')

    def setUp(self):
        from fastapi.testclient import TestClient
        from app.core.security import get_current_user
        self.actor = {
            'userId': '42', 'currentRoleCode': 'PLATFORM_COMMERCIAL',
            'userType': 'PLATFORM_COMMERCIAL', 'permissions': [],
        }
        self.app.dependency_overrides[get_current_user] = lambda: self.actor
        self.addCleanup(self.app.dependency_overrides.clear)
        records = patch.object(self.pam, '_load_user_records', return_value=([], []))
        self.records = records.start()
        self.addCleanup(records.stop)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    @staticmethod
    def contexts(router):
        from app.core.commercial_surface_module_gate import iter_effective_route_contexts
        return list(iter_effective_route_contexts(router))

    @classmethod
    def signatures(cls, router):
        return [(method, context.path) for context in cls.contexts(router)
                for method in (getattr(context, 'methods', None) or ())]

    def test_facade_package_and_production_owner_share_one_router(self):
        self.assertIs(self.facade.router, self.canonical.router)
        self.assertIs(self.package.router, self.canonical.router)
        self.assertIs(self.facade.platform_context, self.canonical.platform_context)
        self.assertIs(self.facade.require_platform_super_admin, self.bundle.require_platform_super_admin)

    def test_all_sixteen_commerce_routes_reach_real_registration_once(self):
        declared = self.commerce.router.routes
        self.assertEqual(len(declared), 16)
        for route in declared:
            for method in route.methods:
                with self.subTest(method=method, path=route.path):
                    matches = [r for r in self.contexts(self.registered)
                               if getattr(r, 'path', '') == route.path
                               and method in (getattr(r, 'methods', None) or ())]
                    self.assertEqual(len(matches), 1)
                    self.assertIs(matches[0].endpoint, route.endpoint)
                    self.assertTrue(matches[0].dependant.dependencies)

    def test_frozen_surface_is_preserved_without_duplicate_signatures(self):
        final = self.signatures(self.canonical.router)
        self.assertEqual(len(final), len(set(final)))
        self.assertTrue(set(self.signatures(self.bundle.router)).issubset(final))

    def test_sandbox_compat_replacement_reaches_production_owner(self):
        matches = [r for r in self.contexts(self.registered)
                   if getattr(r, 'path', '').endswith('/reset-sandbox-data')
                   and 'POST' in (getattr(r, 'methods', None) or ())]
        self.assertEqual(len(matches), 1)
        self.assertIs(matches[0].endpoint, self.sandbox.reset_sandbox_compat)

    def test_repeat_install_is_noop_and_keeps_order(self):
        before = tuple(self.canonical.router.routes)
        self.assertEqual(self.commerce.install_into_platform_router(self.canonical.router), 0)
        self.assertEqual(tuple(self.canonical.router.routes), before)

    def test_late_collision_never_partially_installs_earlier_routes(self):
        from fastapi import APIRouter
        target = APIRouter()
        target.add_api_route('/untouched', lambda: {}, methods=['GET'])
        target.add_api_route(self.commerce.router.routes[-1].path, lambda: {}, methods=['POST'])
        before = tuple(target.routes)
        with self.assertRaisesRegex(RuntimeError, 'route collision'):
            self.commerce.install_into_platform_router(target)
        self.assertEqual(tuple(target.routes), before)

    def test_method_overlap_and_duplicate_existing_handlers_fail_closed(self):
        from fastapi import APIRouter
        target = APIRouter()
        first = self.commerce.router.routes[0]
        target.add_api_route(first.path, lambda: {}, methods=['GET', 'POST'])
        with self.assertRaisesRegex(RuntimeError, 'route collision'):
            self.commerce.install_into_platform_router(target)
        target.routes[:] = [first, first]
        with self.assertRaisesRegex(RuntimeError, 'route collision'):
            self.commerce.install_into_platform_router(target)

    def test_included_route_collision_is_not_hidden_by_a_tree_node(self):
        from fastapi import APIRouter
        target, child = APIRouter(), APIRouter()
        child.add_api_route('/cutover', lambda: {}, methods=['POST'])
        target.include_router(child, prefix='/platform/commercial/tenants/{tenant_id}')
        before = tuple(target.routes)
        with self.assertRaisesRegex(RuntimeError, 'route collision'):
            self.commerce.install_into_platform_router(target)
        self.assertEqual(tuple(target.routes), before)

    def test_duplicate_extension_declaration_is_not_treated_as_idempotency(self):
        from fastapi import APIRouter
        first = self.commerce.router.routes[0]
        target = APIRouter()
        with patch.object(self.commerce.router, 'routes', [first, first]):
            with self.assertRaisesRegex(RuntimeError, 'duplicate'):
                self.commerce.install_into_platform_router(target)
        self.assertEqual(target.routes, [])

    def test_school_wildcard_is_denied_at_every_commercial_endpoint(self):
        self.actor.update(currentRoleCode='SCHOOL_ADMIN', userType='ADMIN', permissions=['*'])
        for route in self.commerce.router.routes:
            url = '/api/v1' + route.path.format(tenant_id=42, module_key='internship', source_id=7, job_id=9)
            for method in route.methods:
                with self.subTest(method=method, path=route.path):
                    response = self.client.request(method, url, json={}, headers={'Idempotency-Key': 'router-test-42'})
                    self.assertEqual(response.status_code, 403, response.text)
                    self.assertEqual(response.json()['bizCode'], 'NO_PERMISSION')
        self.records.assert_not_called()

    def test_commercial_read_reaches_canonical_business_facade(self):
        from app.services import module_commerce_lifecycle_service as lifecycle
        with patch.object(lifecycle, 'tenant_module_portfolio', return_value={'tenantId': '42', 'modules': []}) as reader:
            response = self.client.get('/api/v1/platform/commercial/tenants/42/modules')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['code'], 0)
        reader.assert_called_once_with(42)

    def test_order_idempotency_header_and_actor_are_not_lost_in_composition(self):
        from app.services import commercial_order_item_service as orders
        payload = {'tenantId': '42', 'items': [], 'currency': 'CNY'}
        with patch.object(orders, 'create_itemized_order', return_value={'status': 'UNPAID'}) as writer:
            response = self.client.post('/api/v1/platform/commercial/orders', json=payload,
                                        headers={'Idempotency-Key': 'route-order-42'})
        self.assertEqual(response.status_code, 200, response.text)
        writer.assert_called_once_with(payload, idempotency_key='route-order-42', actor_id='42')

    def test_missing_idempotency_header_rejects_before_business_io(self):
        from app.services import commercial_order_item_service as orders
        with patch.object(orders, 'create_itemized_order') as writer:
            response = self.client.post('/api/v1/platform/commercial/orders', json={'tenantId': '42'})
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()['code'], 422001)
        self.assertTrue(any(item['field'] == 'Idempotency-Key' for item in response.json()['details']))
        writer.assert_not_called()

    def test_source_cancellation_preserves_zero_version_and_reason(self):
        from app.services import module_subscription_service as subscriptions
        with patch.object(subscriptions, 'cancel_subscription_source_now', return_value={'status': 'CANCELLED'}) as writer:
            response = self.client.post('/api/v1/platform/commercial/tenants/42/sources/7/cancel',
                                        json={'expectedVersion': 0, 'reason': 'transport-contract'})
        self.assertEqual(response.status_code, 200, response.text)
        writer.assert_called_once_with(42, 7, expected_version=0, reason='transport-contract')

    def test_other_platform_duty_does_not_gain_commercial_access(self):
        from app.services import module_commerce_lifecycle_service as lifecycle
        self.actor.update(currentRoleCode='PLATFORM_SECURITY_AUDITOR', userType='PLATFORM_SECURITY_AUDITOR')
        with patch.object(lifecycle, 'tenant_module_portfolio') as reader:
            response = self.client.get('/api/v1/platform/commercial/tenants/42/modules')
        self.assertEqual(response.status_code, 403, response.text)
        reader.assert_not_called()


class BrowserFixtureContractTests(unittest.TestCase):
    def test_full_browser_gate_seeds_matrix_before_spec_collection(self):
        import yaml
        workflow = yaml.safe_load((ROOT / '.github/workflows/playwright-production-e2e.yml').read_text())
        job = workflow['jobs']['browser-e2e']
        steps = job['steps']
        seed = [i for i, step in enumerate(steps)
                if 'python scripts/e2e_seed_module_commerce_m2.py' in step.get('run', '')]
        self.assertEqual(len(seed), 1)
        bootstrap = next(i for i, step in enumerate(steps) if step.get('uses') == './.github/actions/browser-runtime')
        run = next(i for i, step in enumerate(steps) if 'run-browser-suite.sh production-non-graduation' in step.get('run', ''))
        self.assertLess(bootstrap, seed[0])
        self.assertLess(seed[0], run)
        seed_step = steps[seed[0]]
        self.assertEqual(seed_step['working-directory'], 'backend')
        self.assertIn('git rev-parse HEAD', seed_step['run'])
        self.assertIn('$E2E_EXPECTED_SHA', seed_step['run'])
        self.assertIn('test -s ../e2e/runtime-fixtures/module-commerce-m2.json', seed_step['run'])
        self.assertNotIn('continue-on-error', seed_step)
        self.assertEqual(job['env']['MOCK_LOGIN_ENABLED'], 'false')
        self.assertEqual(job['env']['E2E_ALLOW_DESTRUCTIVE_TESTS'], 'true')
        self.assertIn('@127.0.0.1:3306/student_lifecycle_e2e', job['env']['DATABASE_URL'])
        # Runtime fixtures contain refresh credentials, not reportable evidence.
        for step in steps:
            if step.get('uses', '').startswith('actions/upload-artifact'):
                self.assertNotIn('runtime-fixtures', step['with']['path'])

    def test_foundation_runs_router_proof_and_archives_its_inputs(self):
        text = (ROOT / '.github/workflows/module-commerce-foundation.yml').read_text()
        self.assertIn('python -B backend/tests/test_module_commerce_router_install.py -v', text)
        archive = next(line for line in text.splitlines() if 'git archive' in line and 'test_module_commercial_review.py' in line)
        self.assertIn('backend/tests/test_module_commerce_router_install.py', archive)
        self.assertIn('.github/workflows/playwright-production-e2e.yml', archive)


class NestedCommercialFenceTests(unittest.TestCase):
    """Real ASGI route trees; replace only commercial/context IO, never the gate.

    The same cases execute on the pinned tree-based framework in foundation CI.
    Dev's older flat framework is exercised too but does not prove tree behavior.
    """
    def setUp(self):
        from app.core import commercial_surface_module_gate as gate, context
        from app.core.exceptions import AppException
        from app.db import session
        from app.services import module_access_service
        self.gate, self.error = gate, AppException
        self.hits = []
        for target, name, value in (
            (context, 'get_current_user_ctx', {'userId': '42', 'tenantId': '42'}),
            (context, 'get_tenant', {'tenantId': '42'}),
            (session, 'db_enabled', True),
        ):
            handle = patch.object(target, name, return_value=value)
            handle.start()
            self.addCleanup(handle.stop)
        handle = patch.object(module_access_service, 'assert_module_access')
        self.authority = handle.start()
        self.addCleanup(handle.stop)

    def application(self, prefixes, *, auth=False):
        from fastapi import APIRouter, Depends, FastAPI
        from fastapi.testclient import TestClient
        from app.core.exceptions import register_exception_handlers
        from app.core.security import get_current_user
        leaf, middle, root = APIRouter(), APIRouter(), APIRouter()
        def probe():
            self.hits.append('business')
            return {'ok': True}
        for method in ('GET', 'POST'):
            leaf.add_api_route('/probe', probe, methods=[method],
                               dependencies=[Depends(get_current_user)] if auth else [])
        for prefix in prefixes:
            middle.include_router(leaf, prefix=prefix)
        root.include_router(middle, prefix='/api/v1')
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(root)
        client = TestClient(app)
        self.addCleanup(client.close)
        return app, client

    def test_nested_warmed_routes_deny_every_product_before_business_handler(self):
        prefixes = {'/mobile/internship': 'internship', '/portal/graduation': 'graduationDesign',
                    '/mobile/teacher/affairs': 'studentAffairs', '/mobile/academic': 'academicAffairs'}
        app, client = self.application(prefixes)
        # Force the real include contexts into their cached form before installing.
        app.openapi()
        self.gate.install_on_router(app.router)
        self.authority.side_effect = self.error('NO_PERMISSION', 'unpaid or frozen', http_status=403)
        for prefix, module in prefixes.items():
            for method in ('GET', 'POST'):
                with self.subTest(method=method, module=module):
                    self.authority.reset_mock()
                    response = client.request(method, '/api/v1'+prefix+'/probe')
                    self.assertEqual(response.status_code, 403, response.text)
                    self.authority.assert_called_once_with(42, module, write=method == 'POST')
        self.assertEqual(self.hits, [])

    def test_paid_nested_route_retains_read_write_intent(self):
        app, client = self.application(['/mobile/academic'])
        self.gate.install_on_router(app.router)
        for method in ('GET', 'POST'):
            self.authority.reset_mock()
            response = client.request(method, '/api/v1/mobile/academic/probe')
            self.assertEqual(response.status_code, 200, response.text)
            self.authority.assert_called_once_with(42, 'academicAffairs', write=method == 'POST')
        self.assertEqual(self.hits, ['business', 'business'])

    def test_alias_inclusion_uses_effective_request_path_not_leaf_declaration(self):
        app, client = self.application(['/mobile/internship', '/system/tree-probe'])
        app.openapi()
        self.gate.install_on_router(app.router)
        self.authority.side_effect = self.error('NO_PERMISSION', 'unpaid', http_status=403)
        self.assertEqual(client.get('/api/v1/mobile/internship/probe').status_code, 403)
        self.authority.reset_mock()
        self.assertEqual(client.get('/api/v1/system/tree-probe/probe').status_code, 200)
        self.authority.assert_not_called()
        self.assertEqual(self.hits, ['business'])

    def test_outage_remains_503_and_missing_identity_still_reaches_auth(self):
        from app.core import context
        app, client = self.application(['/mobile/academic'])
        self.gate.install_on_router(app.router)
        self.authority.side_effect = self.error('AUTHORITY_UNAVAILABLE', 'unavailable', http_status=503)
        result = client.get('/api/v1/mobile/academic/probe')
        self.assertEqual(result.status_code, 503, result.text)
        self.assertEqual(result.json()['bizCode'], 'AUTHORITY_UNAVAILABLE')
        self.assertEqual(self.hits, [])
        app2, client2 = self.application(['/mobile/academic'], auth=True)
        self.gate.install_on_router(app2.router)
        self.authority.reset_mock()
        with patch.object(context, 'get_current_user_ctx', return_value={}):
            result = client2.get('/api/v1/mobile/academic/probe')
        self.assertEqual(result.status_code, 401, result.text)
        self.authority.assert_not_called()

    def test_repeated_install_has_one_dependency_per_effective_leaf(self):
        from fastapi.routing import APIRoute
        app, client = self.application(['/mobile/internship', '/mobile/academic'])
        app.openapi()
        self.gate.install_on_router(app.router)
        self.assertEqual(self.gate.install_on_router(app.router), 0)
        count = 0
        for context in self.gate.iter_effective_route_contexts(app.router):
            leaf = getattr(context, 'route', context)
            if not isinstance(leaf, APIRoute):
                continue
            calls = [dep.call for dep in context.dependant.dependencies]
            self.assertEqual(calls.count(self.gate.enforce_commercial_surface_access), 1)
            count += 1
        self.assertGreaterEqual(count, 2)
        self.authority.side_effect = self.error('NO_PERMISSION', 'unpaid', http_status=403)
        self.assertEqual(client.get('/api/v1/mobile/academic/probe').status_code, 403)
        self.authority.assert_called_once_with(42, 'academicAffairs', write=False)

    def test_already_included_graduation_supplement_is_not_duplicated(self):
        from fastapi import APIRouter
        from app.api.v1.student_portal_graduation_guard import router as graduation
        parent, nested = APIRouter(), APIRouter()
        nested.include_router(graduation)
        parent.include_router(nested)
        def signatures():
            return [(context.path, tuple(sorted(context.methods or ())))
                    for context in self.gate.iter_effective_route_contexts(parent)]
        before = signatures()
        self.gate._mount_reviewed_commercial_supplements(parent)
        self.assertEqual(signatures(), before)
        self.assertEqual(len(before), len(set(before)))


if __name__ == '__main__':
    unittest.main()
