from __future__ import annotations
import unittest
from unittest.mock import patch


class M8RenewalRouterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi import APIRouter, FastAPI
        from app.api.v1.route_registration import register_platform_routes
        from app.core.exceptions import register_exception_handlers
        from app.modules.platform.routers import (
            module_commerce_finance_router, module_commerce_operations_router,
            module_commerce_renewal_router, module_commerce_router, platform_router,
        )
        from app.modules.platform.services import platform_access_governance_legacy
        cls.frozen = module_commerce_router
        cls.finance = module_commerce_finance_router
        cls.operations = module_commerce_operations_router
        cls.renewal = module_commerce_renewal_router
        cls.canonical = platform_router
        cls.pam = platform_access_governance_legacy
        cls.registered = APIRouter(); register_platform_routes(cls.registered)
        cls.app = FastAPI(); register_exception_handlers(cls.app); cls.app.include_router(cls.registered, prefix="/api/v1")

    def setUp(self):
        from fastapi.testclient import TestClient
        from app.core.security import get_current_user
        self.actor = {"userId":"42","currentRoleCode":"PLATFORM_COMMERCIAL","userType":"PLATFORM_COMMERCIAL","permissions":[]}
        self.app.dependency_overrides[get_current_user] = lambda: self.actor
        self.addCleanup(self.app.dependency_overrides.clear)
        handle = patch.object(self.pam, "_load_user_records", return_value=([], []))
        self.records = handle.start(); self.addCleanup(handle.stop)
        self.client = TestClient(self.app); self.addCleanup(self.client.close)

    @staticmethod
    def _contexts(router):
        from app.core.commercial_surface_module_gate import iter_effective_route_contexts
        return list(iter_effective_route_contexts(router))

    @classmethod
    def _signatures(cls, router):
        return {(str(method).upper(), str(context.path)) for context in cls._contexts(router)
                for method in (getattr(context, "methods", None) or ())}

    def test_renewal_surface_is_two_additive_routes_and_disjoint(self):
        self.assertEqual(len(self.frozen.router.routes), 24)
        self.assertEqual(len(self.finance.router.routes), 10)
        self.assertEqual(len(self.operations.router.routes), 8)
        self.assertEqual(len(self.renewal.router.routes), 2)
        surfaces = [self._signatures(self.frozen.router), self._signatures(self.finance.router),
                    self._signatures(self.operations.router), self._signatures(self.renewal.router)]
        for index, left in enumerate(surfaces):
            for right in surfaces[index + 1:]: self.assertFalse(left & right)
        canonical = self._signatures(self.canonical.router)
        for surface in surfaces: self.assertTrue(surface.issubset(canonical))

    def test_repeat_install_is_noop_and_collision_fails_atomically(self):
        from fastapi import APIRouter
        before = tuple(self.canonical.router.routes)
        self.assertEqual(self.renewal.install_into_platform_router(self.canonical.router), 0)
        self.assertEqual(tuple(self.canonical.router.routes), before)
        target = APIRouter(); first = self.renewal.router.routes[0]
        target.add_api_route(first.path, lambda: {}, methods=list(first.methods)); untouched = tuple(target.routes)
        with self.assertRaisesRegex(RuntimeError, "renewal route collision"):
            self.renewal.install_into_platform_router(target)
        self.assertEqual(tuple(target.routes), untouched)

    def test_school_wildcard_cannot_enter_any_renewal_route(self):
        self.actor.update(currentRoleCode="SCHOOL_ADMIN", userType="ADMIN", permissions=["*"])
        for route in self.renewal.router.routes:
            url = "/api/v1" + route.path.format(tenant_id=42, source_id=9)
            for method in route.methods:
                response = self.client.request(method, url, json={})
                self.assertEqual(response.status_code, 403, response.text)
                self.assertEqual(response.json()["bizCode"], "NO_PERMISSION")
        self.records.assert_not_called()

    def test_candidate_read_is_shared_by_commercial_and_customer_success_but_not_operations(self):
        from app.services import module_commerce_renewal_service as renewal
        url = "/api/v1/platform/commercial/tenants/42/renewal-candidates?withinDays=180&page=2&pageSize=7"
        with patch.object(renewal, "list_renewal_candidates", return_value={"items": []}) as call:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, response.text)
            call.assert_called_once_with(42, within_days=180, page=2, page_size=7)
        self.actor.update(currentRoleCode="PLATFORM_CUSTOMER_SUCCESS", userType="PLATFORM_CUSTOMER_SUCCESS")
        with patch.object(renewal, "list_renewal_candidates", return_value={"items": []}) as call:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, response.text)
            call.assert_called_once_with(42, within_days=180, page=2, page_size=7)
        self.actor.update(currentRoleCode="PLATFORM_OPERATIONS", userType="PLATFORM_OPERATIONS")
        with patch.object(renewal, "list_renewal_candidates") as call:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403, response.text)
            call.assert_not_called()

    def test_followup_requires_customer_success_duty_and_never_claims_auto_renewal(self):
        from app.services import module_commerce_renewal_service as renewal
        with patch.object(renewal, "ensure_renewal_followup") as writer:
            denied = self.client.post(
                "/api/v1/platform/commercial/tenants/42/sources/9/renewal-followup",
                json={"dueAt":"2026-09-20T00:00:00Z","ownerName":"CS","note":"明确创建续费跟进"},
            )
            self.assertEqual(denied.status_code, 403, denied.text); writer.assert_not_called()
        self.actor.update(currentRoleCode="PLATFORM_CUSTOMER_SUCCESS", userType="PLATFORM_CUSTOMER_SUCCESS")
        with patch.object(renewal, "ensure_renewal_followup", return_value={
            "renewalTask":{"taskId":"1"},"automaticRenewalExecuted":False,
            "paymentExecuted":False,"entitlementChangeApplied":False,
        }) as writer:
            response = self.client.post(
                "/api/v1/platform/commercial/tenants/42/sources/9/renewal-followup",
                json={"dueAt":"2026-09-20T00:00:00Z","ownerName":"CS","note":"明确创建续费跟进"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            writer.assert_called_once_with(self.actor, 42, 9, due_at="2026-09-20T00:00:00Z", owner_name="CS", note="明确创建续费跟进")
            self.assertIn("未创建订单、未扣款、未修改模块授权", response.json()["message"])


if __name__ == "__main__": unittest.main()
