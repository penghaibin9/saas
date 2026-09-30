"""M8 after-sales/SLA/cost route contract on the real platform registrar."""
from __future__ import annotations

import unittest
from unittest.mock import patch


class M8OperationsRouterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi import APIRouter, FastAPI
        from app.api.v1.route_registration import register_platform_routes
        from app.core.exceptions import register_exception_handlers
        from app.modules.platform.routers import (
            module_commerce_finance_router,
            module_commerce_operations_router,
            module_commerce_router,
            platform_router,
        )
        from app.modules.platform.services import platform_access_governance_legacy

        cls.frozen = module_commerce_router
        cls.finance = module_commerce_finance_router
        cls.operations = module_commerce_operations_router
        cls.canonical = platform_router
        cls.pam = platform_access_governance_legacy
        cls.registered = APIRouter(); register_platform_routes(cls.registered)
        cls.app = FastAPI(); register_exception_handlers(cls.app); cls.app.include_router(cls.registered, prefix="/api/v1")

    def setUp(self):
        from fastapi.testclient import TestClient
        from app.core.security import get_current_user

        self.actor = {"userId": "42", "currentRoleCode": "PLATFORM_COMMERCIAL", "userType": "PLATFORM_COMMERCIAL", "permissions": []}
        self.app.dependency_overrides[get_current_user] = lambda: self.actor
        self.addCleanup(self.app.dependency_overrides.clear)
        handle = patch.object(self.pam, "_load_user_records", return_value=([], [])); self.records = handle.start(); self.addCleanup(handle.stop)
        self.client = TestClient(self.app); self.addCleanup(self.client.close)

    @staticmethod
    def _contexts(router):
        from app.core.commercial_surface_module_gate import iter_effective_route_contexts
        return list(iter_effective_route_contexts(router))

    @classmethod
    def _signatures(cls, router):
        return {(str(method).upper(), str(context.path)) for context in cls._contexts(router)
                for method in (getattr(context, "methods", None) or ())}

    def test_frozen_finance_and_operations_surfaces_are_disjoint(self):
        self.assertEqual(len(self.frozen.router.routes), 24)
        self.assertEqual(len(self.finance.router.routes), 10)
        self.assertEqual(len(self.operations.router.routes), 8)
        frozen = self._signatures(self.frozen.router); finance = self._signatures(self.finance.router); operations = self._signatures(self.operations.router)
        self.assertFalse(frozen & finance); self.assertFalse(frozen & operations); self.assertFalse(finance & operations)
        canonical = self._signatures(self.canonical.router)
        self.assertTrue(frozen.issubset(canonical)); self.assertTrue(finance.issubset(canonical)); self.assertTrue(operations.issubset(canonical))

    def test_repeat_operations_install_is_noop_and_collision_is_atomic(self):
        from fastapi import APIRouter

        before = tuple(self.canonical.router.routes)
        self.assertEqual(self.operations.install_into_platform_router(self.canonical.router), 0)
        self.assertEqual(tuple(self.canonical.router.routes), before)
        target = APIRouter(); first = self.operations.router.routes[0]
        target.add_api_route(first.path, lambda: {}, methods=list(first.methods)); untouched = tuple(target.routes)
        with self.assertRaisesRegex(RuntimeError, "operations route collision"):
            self.operations.install_into_platform_router(target)
        self.assertEqual(tuple(target.routes), untouched)

    def test_school_wildcard_cannot_enter_operations_routes(self):
        self.actor.update(currentRoleCode="SCHOOL_ADMIN", userType="ADMIN", permissions=["*"])
        for route in self.operations.router.routes:
            url = "/api/v1" + route.path.format(tenant_id=42, case_id=9)
            for method in route.methods:
                with self.subTest(method=method, path=route.path):
                    response = self.client.request(method, url, json={}, headers={"Idempotency-Key": "m8-operations-school-deny"})
                    self.assertEqual(response.status_code, 403, response.text)
                    self.assertEqual(response.json()["bizCode"], "NO_PERMISSION")
        self.records.assert_not_called()

    def test_read_routes_transport_to_operations_projection_and_sla_policy(self):
        from app.services import module_commerce_operations_service as operations
        from app.services import module_commerce_sla_policy_service as policy

        scenarios = [
            (operations, "/api/v1/platform/commercial/tenants/42/operations", "operations_overview", (42,), {}),
            (operations, "/api/v1/platform/commercial/tenants/42/after-sales?page=2&pageSize=7", "list_after_sales", (42,), {"page": 2, "page_size": 7}),
            (operations, "/api/v1/platform/commercial/tenants/42/service-costs?page=2&pageSize=7", "list_service_costs", (42,), {"page": 2, "page_size": 7}),
            (policy, "/api/v1/platform/commercial/tenants/42/sla-policy", "policy_editor", (42,), {}),
        ]
        for service, url, name, args, kwargs in scenarios:
            with self.subTest(url=url), patch.object(service, name, return_value={"items": []}) as call:
                response = self.client.get(url); self.assertEqual(response.status_code, 200, response.text)
                call.assert_called_once_with(*args, **kwargs)

    def test_after_sales_ticket_is_explicit_and_never_mutates_entitlement(self):
        from app.services import module_commerce_operations_service as operations

        with patch.object(operations, "ensure_refund_after_sales_ticket", return_value={"ticketCreated": True, "entitlementChangeApplied": False}) as call:
            response = self.client.post(
                "/api/v1/platform/commercial/tenants/42/refunds/9/after-sales-ticket",
                json={"severity": "P2", "reason": "退款后人工复核模块授权"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            call.assert_called_once_with(self.actor, 42, 9, severity="P2", reason="退款后人工复核模块授权")
            self.assertIn("没有自动修改模块授权", response.json()["message"])

    def test_actual_cost_preserves_idempotency_key_and_never_claims_conversion(self):
        from app.services import module_commerce_operations_service as operations

        body = {"costType": "SUPPORT", "amount": "10.00", "currency": "CNY", "occurredAt": "2026-09-09T12:00:00Z", "orderId": "11"}
        with patch.object(operations, "record_service_cost", return_value={"costId": "1", "currencyConverted": False}) as call:
            response = self.client.post(
                "/api/v1/platform/commercial/tenants/42/service-costs",
                json=body, headers={"Idempotency-Key": "m8-cost-route-0001"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            call.assert_called_once_with(self.actor, 42, body, idempotency_key="m8-cost-route-0001")
            self.assertIn("未进行币种换算或估算", response.json()["message"])

    def test_sla_write_and_reset_preserve_expected_version_and_commercial_manage(self):
        from app.services import module_commerce_sla_policy_service as policy

        body = {"expectedVersion": 3, "policyVersion": "SLA-2026-09", "targetsHours": {"P0": 1, "P1": 4, "P2": 12, "P3": 36}, "reason": "合同明确SLA"}
        with patch.object(policy, "update_tenant_policy", return_value={"effective": {"configured": True}}) as update:
            response = self.client.put("/api/v1/platform/commercial/tenants/42/sla-policy", json=body)
            self.assertEqual(response.status_code, 200, response.text)
            update.assert_called_once_with(self.actor, 42, body)
            self.assertIn("没有系统默认承诺", response.json()["message"])

        with patch.object(policy, "reset_tenant_policy", return_value={"effective": {"configured": False}}) as reset:
            response = self.client.post(
                "/api/v1/platform/commercial/tenants/42/sla-policy/reset",
                json={"expectedVersion": 4, "reason": "恢复平台合同默认政策"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            reset.assert_called_once_with(self.actor, 42, expected_version=4, reason="恢复平台合同默认政策")
            self.assertIn("无默认则保持未评估", response.json()["message"])

    def test_operations_source_contains_no_entitlement_or_external_execution_primitive(self):
        from pathlib import Path

        source = Path("app/modules/platform/routers/module_commerce_operations_router.py").read_text(encoding="utf-8")
        for marker in ("退款后授权复核", "现有客户成功工单", "不做币种换算", "sla-policy", "没有系统默认承诺"):
            self.assertIn(marker, source)
        for forbidden in ("cancel_subscription_source_now(", "execute_refund(", "payment_gateway", "execute_tenant_purge"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
